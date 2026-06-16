#!/usr/bin/env python3
"""Tests for /go review pass evidence."""

import json
import os
import pathlib
import subprocess
import sys


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "scripts" / "review-passes.py"


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_review_passes_block_forbidden_file_changes(tmp_path):
    repo = tmp_path / "repo"
    state_dir = tmp_path / "state"
    repo.mkdir()
    state_dir.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    repo.joinpath("README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "base")

    repo.joinpath("secrets.txt").write_text("do not touch\n", encoding="utf-8")
    run_id = "run-review"
    state_dir.joinpath(f"active-task_{run_id}.json").write_text(
        json.dumps(
            {
                "task": {
                    "id": "TASK-1",
                    "title": "Review forbidden file",
                    "objective": "Catch forbidden changes",
                    "scope_in": ["src/"],
                    "forbidden_files": ["secrets.txt"],
                    "acceptance_criteria": ["No forbidden file changes"],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["GO_STATE_DIR"] = str(state_dir)
    env["RUN_ID"] = run_id
    env["TERMINAL_ID"] = "test-terminal"

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    summary = json.loads(state_dir.joinpath(f"review-summary_{run_id}.json").read_text(encoding="utf-8"))
    assert summary["failed"] is True
    assert any("forbidden" in finding.lower() for finding in summary["findings"])
