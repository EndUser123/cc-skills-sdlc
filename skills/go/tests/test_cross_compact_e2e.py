#!/usr/bin/env python3
"""TASK-005 cross-compact e2e harness (#898).

Simulates the session-compaction process boundary: a first "/go step" seeds
disk state at the canonical default path; a second step is invoked in a FRESH
subprocess (RUN_ID/GO_RUN_ID/CLAUDE_GO_RUN_ID + GO_STATE_DIR all UNSET — these
do not survive compaction), with terminal_id still set (A1: survives). Asserts
the second step re-derives the same state dir from terminal_id+cwd, binds to
the SAME run_id, and produces no KeyError.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

PACKAGE = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"

RUN_ID = "run-cross-compact-898"
TERMINAL_ID = "console_e2e_898"


def _canonical_state_dir(project_root: pathlib.Path) -> pathlib.Path:
    """The default path resolve() re-derives post-compaction (go.resume.v1)."""
    return project_root / ".claude" / ".artifacts" / TERMINAL_ID / "go"


def _seed_disk_state(project_root: pathlib.Path) -> pathlib.Path:
    """Mimic orchestrate.write_current_run + active-task at the canonical path."""
    state_dir = _canonical_state_dir(project_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    cr = {
        "schema_version": "go.current-run.v1",
        "run_id": RUN_ID,
        "terminal_id": TERMINAL_ID,
        "go_state_dir": str(state_dir.resolve()),
        "dispatch": "local",
        "status": "running",
        "updated_at": "2026-06-28T00:00:00Z",
    }
    (state_dir / f"current-run_{TERMINAL_ID}.json").write_text(json.dumps(cr), encoding="utf-8")
    (state_dir / "env.json").write_text(json.dumps({
        "TERMINAL_ID": TERMINAL_ID, "RUN_ID": RUN_ID,
        "GO_STATE_DIR": str(state_dir.resolve()), "GO_TASKS_FILE": "tasks.json",
    }), encoding="utf-8")
    (state_dir / f"active-task_{RUN_ID}.json").write_text(json.dumps({
        "run_id": RUN_ID, "terminal_id": TERMINAL_ID,
        "task": {"id": "TASK-898", "title": "cross-compact", "objective": "e2e",
                 "verification_commands": [], "scope_in": [], "forbidden_files": []},
    }), encoding="utf-8")
    return state_dir


def _fresh_env_without_run_identity(project_root: pathlib.Path) -> dict[str, str]:
    """Post-compaction env: RUN_ID family + GO_STATE_DIR stripped; terminal_id set."""
    env = {k: v for k, v in os.environ.items()
           if k not in {"RUN_ID", "GO_RUN_ID", "CLAUDE_GO_RUN_ID", "GO_STATE_DIR"}}
    env["CLAUDE_TERMINAL_ID"] = TERMINAL_ID  # A1: terminal_id env signal survives
    env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def test_post_compact_step_binds_to_pre_compact_run(tmp_path):
    _seed_disk_state(tmp_path)
    env = _fresh_env_without_run_identity(tmp_path)
    probe = subprocess.run(
        [sys.executable, "-c",
         "from run_context import resolve; c=resolve(); "
         "print(c.resolved, c.run_id, c.source)"],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
    )
    assert probe.returncode == 0, f"post-compact resolve crashed: {probe.stderr}"
    assert "Traceback" not in probe.stderr, probe.stderr
    resolved, run_id, source = probe.stdout.strip().split()
    assert resolved == "True", f"expected resolved=True, got {resolved} (re-orphaned!)"
    assert run_id == RUN_ID, f"expected {RUN_ID}, got {run_id}"
    assert source in {"current-run", "env.json"}, f"unexpected source {source}"


def test_post_compact_verify_task_no_keyerror(tmp_path):
    """verify-task.py post-compaction must not KeyError and must bind to on-disk run."""
    _seed_disk_state(tmp_path)
    env = _fresh_env_without_run_identity(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify-task.py")],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
    )
    combined = result.stdout + result.stderr
    assert "KeyError" not in combined, f"regression: KeyError on compaction:\n{combined}"
    assert "no active task" not in combined, f"did not bind to on-disk run:\n{combined}"


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_post_compact_step_binds_to_pre_compact_run(pathlib.Path(td))
        test_post_compact_verify_task_no_keyerror(pathlib.Path(td))
    print("OK cross-compact e2e harness passed")