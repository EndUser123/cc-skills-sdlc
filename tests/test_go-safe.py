"""Happy-path integration test for go_safe.py — verifies the full dispatch pipeline."""

import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def isolated_worktree(tmp_path):
    """Create a bare git repo with one committed file, then add a worktree branch."""
    # Init repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    result = subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"git init failed: {result.stderr}"

    # Commit something on main
    readme = repo_dir / "README.md"
    readme.write_text("test\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir)
    subprocess.run(
        ["git", "-c", "user.email=test@test", "-c", "user.name=test", "commit", "-m", "init"],
        cwd=repo_dir,
    )

    # Create a worktree on a non-main branch
    wt_dir = tmp_path / "worktree"
    subprocess.run(
        ["git", "worktree", "add", "-b", "test-task-branch", str(wt_dir), "HEAD"],
        cwd=repo_dir,
    )

    # Write a valid plan.md in the worktree
    plan = wt_dir / "plan.md"
    plan.write_text(
        """# Test Plan

## Task TEST-001: Add a feature
- **Objective**: Implement the foo bar feature
- **Scope (in)**: src/foo.py, tests/foo_test.py
- **Acceptance**: Tests pass; ruff clean
- **Verification**: pytest -q; ruff check src/foo.py
- **Type**: implementation
- **Routes**: code
"""
    )

    # Make the go skill reachable via a worktree-local junction at skills/go
    # (go_safe.py resolves $root_dir/skills/go/scripts/init_go_run.py)
    skills_link = wt_dir / "skills" / "go"
    skills_link.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["powershell", "-Command", f"New-Item -ItemType Junction -Path '{skills_link}' -Target 'P:\\packages\\cc-skills-sdlc\\skills\\go' -Force"],
        cwd=repo_dir,
    )

    return wt_dir


def test_go_safe_happy_path(isolated_worktree):
    """go_safe.py exits 0, writes 4 JSONs + .dispatched_ flag, prints GO_DISPATCHED."""
    wt_dir = isolated_worktree
    terminal_id = "test-terminal-001"
    go_run_id = "test-run-001"

    result = subprocess.run(
        [
            sys.executable,
            str(Path("P:/packages/cc-skills-sdlc/skills/go/scripts/go_safe.py")),
            "--root-dir", str(wt_dir),
            "--terminal-id", terminal_id,
            "--go-run-id", go_run_id,
        ],
        cwd=str(wt_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"go_safe.py failed (exit {result.returncode})\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "<promise>GO_DISPATCHED</promise>" in result.stdout, (
        f"Missing GO_DISPATCHED in output:\n{result.stdout}"
    )

    # Locate artifact dir
    artifact_dir = wt_dir / ".claude" / ".artifacts" / terminal_id / "go"
    assert artifact_dir.is_dir(), f"artifact dir not created: {artifact_dir}"

    # Verify 4 required JSON files
    required = [
        f"run_{go_run_id}.json",
        f"selected-task_{go_run_id}.json",
        f"dispatch-decision_{go_run_id}.json",
        f"dispatch-result_{go_run_id}.json",
    ]
    for fname in required:
        fpath = artifact_dir / fname
        assert fpath.is_file(), f"missing artifact: {fname}"
        # Validate it's parseable JSON
        with open(fpath) as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{fname} is not a JSON object"
        assert "go_run_id" in data, f"{fname} missing go_run_id"

    # Verify .dispatched_ flag
    dispatched = artifact_dir / f".dispatched_{go_run_id}"
    assert dispatched.is_file(), f"missing .dispatched_ flag"

    # Verify worktree-ready flag
    ready = artifact_dir / f".worktree-ready_{go_run_id}"
    assert ready.is_file(), f"missing .worktree-ready_ flag"

    # Verify no .blocked_ flag was written
    blocked = artifact_dir / f".blocked_{go_run_id}"
    assert not blocked.is_file(), "unexpected .blocked_ flag — go_safe reported failure"
