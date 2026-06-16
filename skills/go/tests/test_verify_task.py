#!/usr/bin/env python3
"""Tests for /go verification behavior."""

import json
import os
import pathlib
import subprocess
import sys


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
VERIFY = PACKAGE / "scripts" / "verify-task.py"


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_scope_drift_uses_current_worktree_diff(tmp_path):
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

    repo.joinpath("src").mkdir()
    repo.joinpath("src", "touched.py").write_text("print('changed')\n", encoding="utf-8")
    run_id = "run-scope"
    state_dir.joinpath(f"active-task_{run_id}.json").write_text(
        json.dumps(
            {
                "task": {
                    "id": "TASK-1",
                    "title": "Scope drift",
                    "objective": "Detect scope drift",
                    "scope_in": ["src/expected.py"],
                    "verification_commands": [f"{sys.executable} -c \"import sys; sys.exit(0)\""],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["GO_STATE_DIR"] = str(state_dir)
    env["RUN_ID"] = run_id
    env["WORKTREE"] = str(repo)

    result = subprocess.run(
        [sys.executable, str(VERIFY)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 4, result.stderr
    results = state_dir.joinpath(f"verification-results_{run_id}.txt").read_text(encoding="utf-8")
    assert "src/expected.py" in results
    assert "possible spec drift" in results
    summary = json.loads(state_dir.joinpath(f"verification-summary_{run_id}.json").read_text(encoding="utf-8"))
    assert summary["verified"] is False
    assert summary["scope_drift_findings"]


def test_scope_drift_blocks_when_scope_declared_but_no_files_changed(tmp_path):
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

    run_id = "run-no-change"
    state_dir.joinpath(f"active-task_{run_id}.json").write_text(
        json.dumps(
            {
                "task": {
                    "id": "TASK-1",
                    "title": "No change",
                    "objective": "Detect no changes",
                    "scope_in": ["src/expected.py"],
                    "verification_commands": [f"{sys.executable} -c \"import sys; sys.exit(0)\""],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["GO_STATE_DIR"] = str(state_dir)
    env["RUN_ID"] = run_id
    env["WORKTREE"] = str(repo)

    result = subprocess.run(
        [sys.executable, str(VERIFY)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 4, result.stderr
    summary = json.loads(state_dir.joinpath(f"verification-summary_{run_id}.json").read_text(encoding="utf-8"))
    assert summary["verified"] is False
    assert "no files changed" in summary["scope_drift_findings"][0]
