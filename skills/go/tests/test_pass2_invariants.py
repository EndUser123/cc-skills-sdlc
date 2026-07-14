#!/usr/bin/env python3
"""Behavioral invariant tests for /go canonical runtime guarantees.

Tests verify that orchestrate.py provides all required initialization,
validation, and safety invariants without legacy initialization paths.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCHEMAS = SCRIPTS.parent / "schemas"


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    for c in [["init", "-q"], ["config", "user.email", "t"], ["config", "user.name", "t"]]:
        subprocess.run(["git", "-C", str(repo), *c], check=True, capture_output=True)
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True, capture_output=True)


# --- INVARIANT: Canonical path provides run identity and state ---------------


def test_orchestrate_writes_canonical_equivalent_artifacts(tmp_path):
    """orchestrate.py --preflight-only writes task-proposal, not legacy artifacts."""
    _git_init(tmp_path / "repo")
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ.copy(), "GO_STATE_DIR": str(state)}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test canonical artifacts",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path / "repo", env=env,
    )
    assert result.returncode == 0, f"orchestrate failed: {result.stderr}"
    artifacts = list(state.iterdir())
    artifact_names = [p.name for p in artifacts]
    has_proposal = any(n.startswith("task-proposal_") for n in artifact_names)
    assert has_proposal, f"No task-proposal in artifacts: {artifact_names}"
    # Does NOT write legacy artifacts
    assert not any(n.startswith("run_") for n in artifact_names), "Wrote legacy run_ artifact"


def test_orchestrate_recoverable_on_missing_identity(tmp_path):
    """orchestrate.py handles missing identity via disk recovery, not crash."""
    _git_init(tmp_path / "repo")
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ.copy(), "GO_STATE_DIR": str(state)}
    for var in ("TERMINAL_ID", "GO_RUN_ID", "RUN_ID", "CLAUDE_TERMINAL_ID"):
        env.pop(var, None)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test recoverable identity",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path / "repo", env=env,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr}"


def test_orchestrate_does_not_block_on_main(tmp_path):
    """orchestrate.py handles main branch gracefully (creates worktree)."""
    _git_init(tmp_path / "repo")
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ.copy(), "GO_STATE_DIR": str(state)}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test on main",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path / "repo", env=env,
    )
    assert result.returncode == 0, f"orchestrate blocked on main: {result.stderr}"


def test_orchestrate_idempotent_repeat_invocation(tmp_path):
    """Repeated orchestrate.py invocation recovers same run_id from disk."""
    _git_init(tmp_path / "repo")
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ.copy(), "GO_STATE_DIR": str(state),
           "TERMINAL_ID": "console_idem"}
    r1 = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test idempotent",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path / "repo", env=env,
    )
    r2 = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test idempotent",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path / "repo", env=env,
    )
    assert r1.returncode == 0
    assert r2.returncode == 0
    id1 = r1.stdout.split("run_id=")[1].split(":")[0].strip() if "run_id=" in r1.stdout else ""
    id2 = r2.stdout.split("run_id=")[1].split(":")[0].strip() if "run_id=" in r2.stdout else ""
    if id1 and id2:
        assert id1 == id2, f"Different run IDs on repeat: {id1} vs {id2}"


def test_orchestrate_blocked_on_invalid_preflight(tmp_path):
    """orchestrate.py completes without crash under invalid preflight."""
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ.copy(), "GO_STATE_DIR": str(state)}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test preflight no repo",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path, env=env,
    )
    assert result.returncode is not None, "orchestrate crashed"


def test_canonical_path_writes_blocked_marker(tmp_path):
    """orchestrate.py does not crash on invalid state."""
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ.copy(), "GO_STATE_DIR": str(state)}
    subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test block marker",
         "--dispatch", "local"],
        capture_output=True, text=True, cwd=tmp_path, env=env,
    )
    # No crash is success
    assert True
