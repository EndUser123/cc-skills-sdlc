"""Integration test: invoke Stop_enforce_gate.main() via real subprocess with
real stdin payload, real pointer file, real state dir. After the broad
completion-authority reduction, main() must NOT block on overclaim terms in
the active-task summary — that classification now belongs to the
orchestrator-side completion_evidence_review.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

GATE_PY = Path(__file__).resolve().parent.parent / "hooks" / "Stop_enforce_gate.py"


def _setup_state(tmp_path: Path, session_id: str, run_id: str, active_task: dict) -> tuple[Path, Path]:
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


def test_main_does_not_block_on_overclaim_summary(tmp_path):
    """Regression: a worker summary containing 'fixed'/'complete' must NOT
    trigger a Stop-side completion-authority block. The old gate used to emit
    {"decision":"block","reason":"continue: ..."} here; the new gate must not."""
    sid = "11111111-2222-3333-4444-555555555555"
    rid = "run-int-1"
    active = {"task": {"summary": "Bug fixed in handler; migration complete"}}
    artifacts, _ = _setup_state(tmp_path, sid, rid, active)
    r = _run_gate(tmp_path, artifacts, {"session_id": sid, "stop_hook_active": False})
    # Downstream SDLC hard-gate may exit 2 + write stderr; that's expected and
    # out of scope here. What matters: no completion-authority block on stdout.
    stdout = r.stdout.decode().strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"unexpected non-JSON stdout: {stdout!r}")
        assert parsed.get("decision") != "block" or "completion" not in parsed.get("reason", "").lower(), (
            f"Stop-side completion-authority block fired on overclaim summary: {parsed}"
        )


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