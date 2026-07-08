"""Subprocess-level test: review_transcript.main() writes discovery-evidence on blind write.

This catches the path-resolution bug that unit tests on `extract_discovery_findings`
could not: the importlib path (`parents[N]`) inside main() only runs when the script
is invoked as a subprocess (the real pi-dispatch path). A unit test that imports
the module directly never exercises that code.

Reproduces the failure mode: if `_scripts_dir` resolves to the wrong parent,
`importlib.import_module("preflight_propose")` raises ModuleNotFoundError, the
writer is skipped (best-effort try/except), and discovery-evidence is NOT written.
This test asserts the file IS written when a blind-write transcript exists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_REVIEW_SCRIPT = SCRIPTS / "adapters" / "pi" / "review_transcript.py"


def _make_blind_write_transcript(path: Path) -> None:
    """A pi --mode json transcript where the worker writes a file with no prior read."""
    events = [
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "write", "arguments": {"path": "src/auth.py",
              "content": "x"}, "id": "w1"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolName": "write",
            "isError": False, "content": [{"type": "text", "text": "ok"}], "toolCallId": "w1"}},
    ]
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_review_main_writes_discovery_evidence_on_blind_write(tmp_path: Path) -> None:
    """Subprocess invoke review_transcript.main(); assert discovery-evidence file written.

    Regression for the parents[N] path-resolution bug: if the path is wrong, the
    import fails, the writer is skipped, and this file is never created.
    """
    run_id = "subproc-001"
    state_dir = tmp_path
    transcript = state_dir / f"pi-transcript_{run_id}.jsonl"
    _make_blind_write_transcript(transcript)

    env = {**os.environ, "GO_STATE_DIR": str(state_dir), "RUN_ID": run_id}
    # Active task with no forbidden_files, broad scope so BLIND_WRITE is the only warning.
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"title": "T", "scope_in": [], "forbidden_files": []}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_REVIEW_SCRIPT)],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"review_transcript failed: {result.stderr}"

    # The pi-review summary must exist.
    assert (state_dir / f"pi-review_{run_id}.json").exists()

    # The discovery-evidence file must exist (writer succeeded via correct path).
    de_file = state_dir / f"discovery-evidence_{run_id}.json"
    assert de_file.exists(), (
        "discovery-evidence not written -- path resolution or import failed silently. "
        f"stderr: {result.stderr}"
    )
    de = json.loads(de_file.read_text(encoding="utf-8"))
    assert de["run_id"] == run_id
    assert any(f["structural_issues"] == ["wrong_layer_ownership"] for f in de["findings"])


def test_review_main_no_warnings_no_discovery_file(tmp_path: Path) -> None:
    """Clean transcript (read then write) -> no discovery-evidence file."""
    run_id = "subproc-002"
    state_dir = tmp_path
    transcript = state_dir / f"pi-transcript_{run_id}.jsonl"
    events = [
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "read", "arguments": {"path": "src/auth.py"}, "id": "r1"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolName": "read",
            "isError": False, "content": [{"type": "text", "text": "y"}], "toolCallId": "r1"}},
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "write", "arguments": {"path": "src/auth.py",
              "content": "z"}, "id": "w1"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolName": "write",
            "isError": False, "content": [{"type": "text", "text": "ok"}], "toolCallId": "w1"}},
    ]
    with transcript.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"title": "T", "scope_in": [], "forbidden_files": []}}),
        encoding="utf-8",
    )
    env = {**os.environ, "GO_STATE_DIR": str(state_dir), "RUN_ID": run_id}
    subprocess.run([sys.executable, str(_REVIEW_SCRIPT)], env=env,
                   capture_output=True, text=True, timeout=30)
    assert not (state_dir / f"discovery-evidence_{run_id}.json").exists()
