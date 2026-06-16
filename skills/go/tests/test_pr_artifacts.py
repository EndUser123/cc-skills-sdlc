#!/usr/bin/env python3
"""Tests for /go PR artifact generation."""

import json
import os
import pathlib
import subprocess
import sys

import jsonschema


PACKAGE = pathlib.Path(__file__).resolve().parents[1]


def test_pr_artifacts_marks_verification_result_pr_ready(tmp_path):
    run_id = "run-pr-ready"
    state_dir = tmp_path
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"id": "TASK-1", "title": "Ship it", "objective": "finish"}}) + "\n",
        encoding="utf-8",
    )
    (state_dir / f"verification-result_{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "terminal_id": "term-1",
                "task_id": "TASK-1",
                "status": "passed",
                "pr_ready": False,
                "generated_at": "2026-06-16T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["GO_STATE_DIR"] = str(state_dir)
    env["RUN_ID"] = run_id

    result = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts" / "pr-artifacts.py")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    verification = json.loads((state_dir / f"verification-result_{run_id}.json").read_text(encoding="utf-8"))
    assert verification["status"] == "passed"
    assert verification["pr_ready"] is True
    assert verification["artifact_paths"]["pr_ready"].endswith(f"pr-ready_{run_id}.md")
    schema = json.loads((PACKAGE / "schemas" / "verification-result.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(verification)
