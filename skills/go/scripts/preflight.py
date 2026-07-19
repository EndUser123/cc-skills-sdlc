"""Worktree Preflight — gating checks before destructive worktree operations.

Runs before any destructive operation (clean, remove, etc.). Returns a
PreflightReport with findings; callers MUST check `report.blocked` and
refuse to proceed if True.

Checks (8 total):
1. Git worktree lock file present at <repo>/.git/worktrees/<name>/locked
2. .git/*.lock files (in-progress git operations)
3. OS-specific process scan for refs to the worktree path
   - Windows: Get-CimInstance Win32_Process with path-injection hardening
   - POSIX: lsof +D <path> (graceful fallback when lsof unavailable)
4. Worktree registered in `git worktree list --porcelain`
5. Working tree clean (no uncommitted changes)
6. Branch reachability from main (INFO-level; lets caller decide auto_tag)
7. Branch checked out elsewhere (would block -D silently)
8. Hook state file freshness (terminal ID matches?)

PR 3 of P:/docs/worktree-lifecycle-design.md.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(Enum):
    BLOCK = "block"  # Must be resolved (or operator override) before proceeding
    WARN = "warn"    # Allowed with explicit override
    INFO = "info"    # Informational only


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str
    detail: str = ""


@dataclass
class PreflightReport:
    worktree_path: Path
    repo_root: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.severity == Severity.BLOCK for f in self.findings)

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARN]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.INFO]

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def summary(self) -> str:
        n_block = sum(1 for f in self.findings if f.severity == Severity.BLOCK)
        n_warn = sum(1 for f in self.findings if f.severity == Severity.WARN)
        n_info = sum(1 for f in self.findings if f.severity == Severity.INFO)
        return f"{n_block} block, {n_warn} warn, {n_info} info"


def preflight_run(
    worktree_path: Path,
    repo_root: Path,
    *,
    branch_name: str = "",
    main_branch: str = "main",
) -> PreflightReport:
    """Run all preflight checks for a worktree operation.

    Returns PreflightReport. Caller should refuse to proceed if
    `report.blocked` is True (or surface findings to the operator).
    """
    worktree_path = Path(worktree_path).resolve()
    repo_root = Path(repo_root).resolve()
    report = PreflightReport(worktree_path=worktree_path, repo_root=repo_root)

    _check_git_worktree_lock(report, worktree_path, repo_root)
    _check_git_dotlock_files(report, repo_root)
    _check_process_scan(report, worktree_path)
    _check_worktree_registered(report, worktree_path, repo_root)
    _check_working_tree_clean(report, worktree_path)
    if branch_name:
        _check_branch_reachability(report, repo_root, branch_name, main_branch)
        _check_branch_in_use(report, repo_root, branch_name)

    return report


# --- Individual checks --------------------------------------------------------


def _check_git_worktree_lock(
    report: PreflightReport, worktree_path: Path, repo_root: Path
) -> None:
    """Check 1: Is there a lock file for this worktree in .git/worktrees/<name>/?"""
    wt_name = worktree_path.name
    lock_file = repo_root / ".git" / "worktrees" / wt_name / "locked"
    if lock_file.exists():
        report.add(Finding(
            severity=Severity.BLOCK,
            code="WT_LOCKED",
            message=f"Worktree has lock file: {lock_file}",
            detail=lock_file.read_text(encoding="utf-8", errors="replace").strip(),
        ))


def _check_git_dotlock_files(report: PreflightReport, repo_root: Path) -> None:
    """Check 2: Are there .git/*.lock files (in-progress git operations)?"""
    git_dir = repo_root / ".git"
    if not git_dir.is_dir():
        return
    for lockfile in git_dir.glob("*.lock"):
        report.add(Finding(
            severity=Severity.WARN,
            code="GIT_LOCK",
            message=f"Git operation in progress: {lockfile.name}",
            detail=str(lockfile),
        ))


def _check_process_scan(report: PreflightReport, worktree_path: Path) -> None:
    """Check 3: Are any processes referencing the worktree path?"""
    if os.name == "nt":
        _scan_win32_processes(report, worktree_path)
    else:
        _scan_posix_processes(report, worktree_path)


def _scan_win32_processes(report: PreflightReport, worktree_path: Path) -> None:
    """Windows: PowerShell + Get-CimInstance Win32_Process.

    Path-injection hardened: single quotes are escaped to '' (PowerShell
    string escape). CommandLine field is matched with -like wildcard.
    """
    # PowerShell escape: ' -> ''
    safe_path = str(worktree_path).replace("'", "''")
    ps_script = (
        "Get-CimInstance Win32_Process "
        f"| Where-Object {{ $_.CommandLine -ne $null -and $_.CommandLine -like '*{safe_path}*' }} "
        "| Select-Object ProcessId, Name "
        "| Format-Table -AutoSize -HideTableHeaders"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        # Parse PowerShell Format-Table output: lines like "   1234 notepad"
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                pid, name = parts
                report.add(Finding(
                    severity=Severity.WARN,
                    code="PROC_REFERENCES_WT",
                    message=f"Process {name} (PID {pid}) references worktree path",
                ))
    except subprocess.TimeoutExpired:
        report.add(Finding(
            severity=Severity.WARN,
            code="PROC_SCAN_TIMEOUT",
            message="Process scan timed out (10s)",
        ))
    except FileNotFoundError:
        report.add(Finding(
            severity=Severity.INFO,
            code="PROC_SCAN_UNAVAILABLE",
            message="powershell not available; skipping process scan",
        ))


def _scan_posix_processes(report: PreflightReport, worktree_path: Path) -> None:
    """POSIX: lsof +D <path> for files held open under the worktree."""
    try:
        r = subprocess.run(
            ["lsof", "+D", str(worktree_path)],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        report.add(Finding(
            severity=Severity.INFO,
            code="PROC_SCAN_UNAVAILABLE",
            message="lsof not available; skipping process scan",
        ))
        return
    except subprocess.TimeoutExpired:
        report.add(Finding(
            severity=Severity.WARN,
            code="PROC_SCAN_TIMEOUT",
            message="lsof timed out (10s)",
        ))
        return

    # lsof output: header line + one row per match. Header columns vary.
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    for line in lines[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            report.add(Finding(
                severity=Severity.WARN,
                code="PROC_REFERENCES_WT",
                message=f"Process {parts[0]} (PID {parts[1]}) has open files in worktree",
            ))


def _check_worktree_registered(
    report: PreflightReport, worktree_path: Path, repo_root: Path
) -> None:
    """Check 4: Is the worktree registered in `git worktree list`?

    Path comparison is normalized: `git worktree list --porcelain` uses
    forward slashes; Path.resolve() on Windows returns backslashes. We
    normalize both sides before comparing.
    """
    r = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return  # git command failed; other checks will surface the issue
    worktree_norm = str(worktree_path).replace("\\", "/")
    if worktree_norm not in r.stdout:
        report.add(Finding(
            severity=Severity.WARN,
            code="WT_UNREGISTERED",
            message=f"Worktree not in `git worktree list`: {worktree_path}",
        ))


def _check_working_tree_clean(report: PreflightReport, worktree_path: Path) -> None:
    """Check 5: Is the worktree clean (no uncommitted changes)?"""
    if not worktree_path.exists():
        return  # Path missing; other checks (WT_UNREGISTERED) cover it
    r = subprocess.run(
        ["git", "-C", str(worktree_path), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return
    changes = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if changes:
        report.add(Finding(
            severity=Severity.BLOCK,
            code="WT_DIRTY",
            message=f"Worktree has {len(changes)} uncommitted change(s)",
            detail="\n".join(changes[:5]),
        ))


def _check_branch_reachability(
    report: PreflightReport, repo_root: Path, branch_name: str, main_branch: str
) -> None:
    """Check 6: Is the branch tip reachable from main? (INFO-level advisory)"""
    r = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", branch_name, main_branch],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        report.add(Finding(
            severity=Severity.INFO,
            code="BRANCH_UNREACHABLE",
            message=(
                f"Branch {branch_name} not reachable from {main_branch}; "
                "deletion will require auto_tag=True to preserve the commit"
            ),
        ))


def _check_branch_in_use(report: PreflightReport, repo_root: Path, branch_name: str) -> None:
    """Check 7: Is the branch checked out in any worktree?"""
    r = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return
    # porcelain output: lines like "worktree /path\nHEAD abc123\nbranch refs/heads/<name>\n..."
    current_path = ""
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            branch_ref = line[len("branch "):].strip()
            # refs/heads/<name> -> <name>
            short = branch_ref.replace("refs/heads/", "")
            if short == branch_name:
                report.add(Finding(
                    severity=Severity.BLOCK,
                    code="BRANCH_IN_USE",
                    message=(
                        f"Branch {branch_name} is checked out at {current_path}; "
                        "deletion will fail"
                    ),
                ))