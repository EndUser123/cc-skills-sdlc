"""Integration test: invoke Stop_enforce_gate.main() via real subprocess with
real stdin payload, real pointer file, real state dir. Proves the wiring in
main() actually invokes evaluate_completion_authority and emits the documented
JSON block shape on stdout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

GATE_PY = Path(__file__).resolve().parent.parent / "hooks" / "Stop_enforce_gate.py"


def _setup_state(tmp_path: Path, session_id: str, run_id: str, active_task: dict) -> tuple[Path, Path]:
    """Create pointer + state dir + active-task. Returns (artifacts_root, state_dir)."""
    state_dir = tmp_path / "go-state" / run_id
    state_dir.mkdir(parents=True)
    (state_dir / f"active-task_{run_id}.json").write_text(json.dumps(active_task), encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    pointer = artifacts / "go-sessions" / f"{session_id}.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text(json.dumps({
        "go_state_dir": str(state_dir),
        "run_id": run_id,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }), encoding="utf-8")
    return artifacts, state_dir


def _run_gate(tmp_path: Path, artifacts: Path, payload: dict) -> subprocess.CompletedProcess:
    """Run the gate as a subprocess, patching _ARTIFACTS_ROOT to the tmp artifacts dir."""
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, r'{GATE_PY.parent}'); "
        f"import Stop_enforce_gate as g; "
        f"g._ARTIFACTS_ROOT = Path(r'{artifacts}'); "
        "g.main()",
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(wrapper)],
        input=json.dumps(payload).encode(),
        capture_output=True,
        timeout=15,
    )


def test_main_blocks_on_overclaim_without_evidence(tmp_path):
    """End-to-end: main() reads payload, resolves pointer, runs completion-authority,
    emits {"decision":"block","reason":"continue: ..."} on stdout, exits 0."""
    sid = "11111111-2222-3333-4444-555555555555"
    rid = "run-int-1"
    active = {"task": {"summary": "Bug fixed in handler"}}
    artifacts, _ = _setup_state(tmp_path, sid, rid, active)
    r = _run_gate(tmp_path, artifacts, {"session_id": sid, "stop_hook_active": False})
    assert r.returncode == 0, f"unexpected exit code; stderr: {r.stderr.decode()}"
    out = r.stdout.decode().strip()
    assert out, f"expected block JSON on stdout, got empty. stderr={r.stderr.decode()}"
    parsed = json.loads(out)
    assert parsed["decision"] == "block"
    assert parsed["reason"].startswith("continue:")


def test_main_silent_on_no_session_id(tmp_path):
    """No session_id in payload -> fail-silent exit 0, no stdout."""
    r = _run_gate(tmp_path, tmp_path, {"stop_hook_active": False})
    assert r.returncode == 0
    assert r.stdout.decode().strip() == ""


def test_main_silent_on_stop_hook_active(tmp_path):
    """Recursive stop (stop_hook_active=True) -> fail-silent exit 0, no stdout."""
    sid = "22222222-3333-4444-5555-666666666666"
    rid = "run-int-2"
    active = {"task": {"summary": "Bug fixed"}}
    artifacts, _ = _setup_state(tmp_path, sid, rid, active)
    r = _run_gate(tmp_path, artifacts, {"session_id": sid, "stop_hook_active": True})
    assert r.returncode == 0
    assert r.stdout.decode().strip() == ""


def test_main_allows_when_no_overclaim(tmp_path):
    """Active-task with no overclaim terms -> no block, silent exit 0."""
    sid = "33333333-4444-5555-6666-777777777777"
    rid = "run-int-3"
    active = {"task": {"summary": "Implementation in progress"}}
    artifacts, _ = _setup_state(tmp_path, sid, rid, active)
    r = _run_gate(tmp_path, artifacts, {"session_id": sid, "stop_hook_active": False})
    assert r.returncode == 0
    # No block output because "in progress" has no overclaim terms
    out = r.stdout.decode().strip()
    if out:
        parsed = json.loads(out)
        assert parsed.get("decision") != "block"
