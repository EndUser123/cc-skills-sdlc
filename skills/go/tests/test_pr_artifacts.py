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
    (state_dir / f"verification-summary_{run_id}.json").write_text(
        json.dumps({"verified": True}) + "\n",
        encoding="utf-8",
    )
    (state_dir / f"review-summary_{run_id}.json").write_text(
        json.dumps({"failed": False, "findings": []}) + "\n",
        encoding="utf-8",
    )
    (state_dir / f"qa-verdict-{run_id}.json").write_text(
        json.dumps({"qa_status": "accept"}) + "\n",
        encoding="utf-8",
    )
    (state_dir / f"mutation-gate-{run_id}.json").write_text(
        json.dumps({"status": "skipped"}) + "\n",
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


def test_pr_artifacts_fail_closed_without_required_gate_evidence(tmp_path):
    run_id = "run-pr-missing-evidence"
    state_dir = tmp_path
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"id": "TASK-1", "title": "Do not stamp", "objective": "fail closed"}}) + "\n",
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

    assert result.returncode == 1
    assert "missing required gate evidence" in result.stderr.lower()
    assert not (state_dir / f"task-result_{run_id}.json").exists()
