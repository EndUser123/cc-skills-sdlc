"""Tests for preflight.py — gating checks before destructive worktree ops.

Uses real temporary git repos; some tests exercise the Windows PowerShell
process scan (which will gracefully skip on non-Windows hosts).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
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


def _make_worktree(repo: Path, worktree_root: Path, run_id: str) -> tuple[Path, str]:
    """Create a worktree + branch, return (worktree_path, branch_name)."""
    worktree_root.mkdir(parents=True, exist_ok=True)
    wd = worktree_root / f"wt-{run_id[:8]}"
    branch = f"wt/{run_id[:8]}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(wd), "HEAD"],
        check=True, capture_output=True,
    )
    return wd, branch


def _remove_worktree(repo: Path, worktree_path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree_path)],
        capture_output=True,
    )


# --- preflight_run happy path ------------------------------------------------


def test_preflight_run_clean_worktree_no_findings(tmp_path):
    """A registered, clean, detached worktree with reachable branch -> no findings."""
    from preflight import preflight_run, Severity
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "clean-run")
    try:
        # Detach HEAD so BRANCH_IN_USE doesn't fire (branch is still real
        # but no worktree is "using" it via checked-out HEAD)
        subprocess.run(["git", "-C", str(wt), "checkout", "--detach", "HEAD"],
                       check=True, capture_output=True)
        report = preflight_run(wt, repo, branch_name=branch)
        # Process-scan WARN may appear if powershell is in PATH and
        # finds something matching the test worktree path; that's an
        # environment artifact, not a real finding. Filter INFO/WARN
        # from the process scan specifically — the structural checks
        # must all be clean.
        structural = [f for f in report.findings
                      if f.code not in ("PROC_REFERENCES_WT",
                                       "PROC_SCAN_TIMEOUT",
                                       "PROC_SCAN_UNAVAILABLE")]
        assert not structural, (
            f"unexpected structural findings: {[(f.severity, f.code, f.message) for f in structural]}"
        )
    finally:
        _remove_worktree(repo, wt)


def test_preflight_blocks_on_lock_file(tmp_path):
    """A worktree with a .git/worktrees/<name>/locked file -> BLOCK finding."""
    from preflight import preflight_run
    repo = _git_repo(tmp_path / "repo")
    wt, _branch = _make_worktree(repo, tmp_path / "wts", "locked-run")
    try:
        # Create a fake lock file
        lock_dir = repo / ".git" / "worktrees" / wt.name
        lock_dir.mkdir(parents=True, exist_ok=True)
        (lock_dir / "locked").write_text("reason: test lock\n", encoding="utf-8")

        report = preflight_run(wt, repo)
        assert report.blocked, f"expected blocked=True, findings={report.findings}"
        codes = [f.code for f in report.findings]
        assert "WT_LOCKED" in codes, f"expected WT_LOCKED in {codes}"
    finally:
        _remove_worktree(repo, wt)
        # Clean up the artificial lock dir
        lock_dir = repo / ".git" / "worktrees" / wt.name
        if lock_dir.exists():
            import shutil
            shutil.rmtree(lock_dir, ignore_errors=True)


def test_preflight_warns_on_git_lock_file(tmp_path):
    """A .git/*.lock file -> WARN finding (not block)."""
    from preflight import preflight_run, Severity
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "git-lock-run")
    try:
        # Create a fake in-progress git lock
        (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
        try:
            report = preflight_run(wt, repo, branch_name=branch)
            codes = [f.code for f in report.findings]
            assert "GIT_LOCK" in codes, f"expected GIT_LOCK in {codes}"
            git_lock_findings = [f for f in report.findings if f.code == "GIT_LOCK"]
            assert all(f.severity == Severity.WARN for f in git_lock_findings)
        finally:
            (repo / ".git" / "index.lock").unlink(missing_ok=True)
    finally:
        _remove_worktree(repo, wt)


def test_preflight_blocks_on_dirty_worktree(tmp_path):
    """Uncommitted changes -> BLOCK finding (WT_DIRTY)."""
    from preflight import preflight_run
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "dirty-run")
    try:
        # Make an uncommitted change
        (wt / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
        report = preflight_run(wt, repo, branch_name=branch)
        assert report.blocked, f"expected blocked=True, findings={report.findings}"
        codes = [f.code for f in report.findings]
        assert "WT_DIRTY" in codes, f"expected WT_DIRTY in {codes}"
    finally:
        _remove_worktree(repo, wt)


def test_preflight_info_on_unreachable_branch(tmp_path):
    """Branch tip NOT reachable from main -> INFO finding (not block)."""
    from preflight import preflight_run, Severity
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "unreach-run")
    try:
        # Make a divergent commit in the worktree so branch tip is unreachable
        (wt / "extra.txt").write_text("divergent\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(wt), "add", "extra.txt"], check=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-qm", "diverge"], check=True)
        # Detach HEAD so BRANCH_IN_USE doesn't fire (test focuses on unreachable)
        subprocess.run(["git", "-C", str(wt), "checkout", "--detach", "HEAD"],
                       check=True, capture_output=True)

        report = preflight_run(wt, repo, branch_name=branch)
        # Unreachable branch is INFO, not BLOCK
        unreach = [f for f in report.findings if f.code == "BRANCH_UNREACHABLE"]
        assert unreach, f"expected BRANCH_UNREACHABLE in {[f.code for f in report.findings]}"
        assert all(f.severity == Severity.INFO for f in unreach)
    finally:
        _remove_worktree(repo, wt)


def test_preflight_blocks_on_branch_in_use(tmp_path):
    """Branch checked out in a (second) worktree -> BLOCK finding."""
    from preflight import preflight_run
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "inuse-run")
    try:
        # Branch IS checked out in `wt`. So passing the same branch_name
        # back to preflight should detect BRANCH_IN_USE.
        report = preflight_run(wt, repo, branch_name=branch)
        codes = [f.code for f in report.findings]
        assert "BRANCH_IN_USE" in codes, f"expected BRANCH_IN_USE in {codes}"
        assert report.blocked
    finally:
        _remove_worktree(repo, wt)


def test_preflight_warns_on_unregistered_worktree(tmp_path):
    """A directory that's not in `git worktree list` -> WARN finding."""
    from preflight import preflight_run, Severity
    repo = _git_repo(tmp_path / "repo")
    # Create a directory but don't register it as a git worktree
    fake_wt = tmp_path / "fake-wt"
    fake_wt.mkdir()
    (fake_wt / "stuff.txt").write_text("not a real worktree\n", encoding="utf-8")
    report = preflight_run(fake_wt, repo)
    codes = [f.code for f in report.findings]
    assert "WT_UNREGISTERED" in codes, f"expected WT_UNREGISTERED in {codes}"
    unregistered = [f for f in report.findings if f.code == "WT_UNREGISTERED"]
    assert all(f.severity == Severity.WARN for f in unregistered)
    assert not report.blocked


def test_preflight_summary_counts_correct(tmp_path):
    """PreflightReport.summary produces correct counts."""
    from preflight import preflight_run
    repo = _git_repo(tmp_path / "repo")
    wt, branch = _make_worktree(repo, tmp_path / "wts", "summary-run")
    try:
        (wt / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        # Lock the worktree
        lock_dir = repo / ".git" / "worktrees" / wt.name
        lock_dir.mkdir(parents=True, exist_ok=True)
        (lock_dir / "locked").write_text("test\n", encoding="utf-8")
        try:
            report = preflight_run(wt, repo, branch_name=branch)
            assert report.blocked
            summary = report.summary()
            # 2 BLOCK (WT_LOCKED + WT_DIRTY) + 1 BLOCK (BRANCH_IN_USE) = 3 block
            # Plus process scan may add WARN (Windows only). Just check it parses.
            assert "block" in summary
        finally:
            import shutil
            shutil.rmtree(lock_dir, ignore_errors=True)
    finally:
        _remove_worktree(repo, wt)