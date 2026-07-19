"""Tests for worktree_cleanup.py — the policy-validated CLI surface.

PR 4 of P:/docs/worktree-lifecycle-design.md. Verifies that cmd_remove
runs preflight first and respects BLOCK findings unless --force is given.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _git_repo(dst: Path) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for c in [("init", "-q"), ("config", "user.email", "t"), ("config", "user.name", "t")]:
        subprocess.run(["git", "-C", str(dst), *c], check=True)
    (dst / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(dst), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(dst), "commit", "-qm", "base"], check=True)
    return dst


def _make_worktree(repo: Path, worktree_root: Path, run_id: str):
    worktree_root.mkdir(parents=True, exist_ok=True)
    wd = worktree_root / f"wt-{run_id[:8]}"
    branch = f"wt/{run_id[:8]}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(wd), "HEAD"],
        check=True, capture_output=True,
    )
    return wd, branch


def test_cmd_preflight_returns_0_for_clean_worktree(tmp_path, capsys):
    """cmd_preflight returns 0 (and prints report) for a clean detached worktree."""
    from worktree_cleanup import cmd_preflight
    import argparse
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "clean-rc")
    # Detach so BRANCH_IN_USE doesn't fire
    subprocess.run(["git", "-C", str(wt), "checkout", "--detach", "HEAD"],
                   check=True, capture_output=True)
    try:
        args = argparse.Namespace(worktree=str(wt), repo=str(repo), branch=branch)
        rc = cmd_preflight(args)
        # Process scan on Windows may add WARN; we only care that BLOCK isn't set
        assert rc == 0, f"expected rc=0, got {rc}"
        out = capsys.readouterr().out
        assert "blocked: False" in out
        assert branch in out
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
                       check=False, capture_output=True)


def test_cmd_preflight_returns_1_for_dirty_worktree(tmp_path, capsys):
    """cmd_preflight returns 1 for a worktree with uncommitted changes."""
    from worktree_cleanup import cmd_preflight
    import argparse
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "dirty-rc")
    try:
        # Make an uncommitted change
        (wt / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
        args = argparse.Namespace(worktree=str(wt), repo=str(repo), branch=branch)
        rc = cmd_preflight(args)
        assert rc == 1, f"expected rc=1 (blocked), got {rc}"
        out = capsys.readouterr().out
        assert "blocked: True" in out
        assert "WT_DIRTY" in out
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
                       check=False, capture_output=True)


def test_cmd_remove_refuses_on_blocked_preflight(tmp_path, capsys):
    """cmd_remove with no --force refuses when preflight blocks (worktree not removed)."""
    from worktree_cleanup import cmd_remove
    import argparse
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "block-rm")
    try:
        (wt / "dirty.txt").write_text("x\n", encoding="utf-8")
        args = argparse.Namespace(
            worktree=str(wt), repo=str(repo), branch=branch,
            force=False, auto_tag=False,
        )
        rc = cmd_remove(args)
        assert rc == 1, f"expected rc=1 (refused), got {rc}"
        out_err = capsys.readouterr().err
        assert "BLOCKED" in out_err or "blocked" in out_err.lower()
        # Worktree should still exist
        assert wt.exists(), "worktree should still exist after refused remove"
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
                       check=False, capture_output=True)


def test_cmd_remove_succeeds_on_clean_worktree(tmp_path, capsys):
    """cmd_remove on a clean detached worktree removes it successfully."""
    from worktree_cleanup import cmd_remove
    import argparse
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "clean-rm")
    # Detach so BRANCH_IN_USE doesn't block
    subprocess.run(["git", "-C", str(wt), "checkout", "--detach", "HEAD"],
                   check=True, capture_output=True)
    args = argparse.Namespace(
        worktree=str(wt), repo=str(repo), branch=branch,
        force=False, auto_tag=False,
    )
    rc = cmd_remove(args)
    assert rc == 0, f"expected rc=0, got {rc}, stderr={capsys.readouterr().err}"
    assert not wt.exists(), "worktree directory should be gone after successful remove"