"""Worktree Cleanup CLI - the policy-validated worktree management surface.

PR 4 of P:/docs/worktree-lifecycle-design.md (combined with PR 3 per
Claude review). The hook blocks raw `git worktree` invocations and
points at this CLI. The CLI runs preflight + safe_delete_branch +
state registry updates atomically.

Subcommands:
  list       — list worktrees with state (delegates to worktree_safety.cmd_status)
  preflight  — run preflight checks for a worktree; report findings + blocked status
  remove     — remove a worktree after preflight passes (calls preflight_run first)

Exit codes: 0 = success, 1 = blocked or refused, 2 = internal error.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Make sibling modules importable when invoked directly
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import preflight  # noqa: E402
import worktree_lifecycle  # noqa: E402
import worktree_safety  # noqa: E402


# --- Subcommands --------------------------------------------------------------


def cmd_list(args) -> int:
    """List worktrees with state (delegates to worktree_safety.cmd_status)."""
    worktree_safety.cmd_status(args)
    return 0


def cmd_preflight(args) -> int:
    """Run preflight checks for a worktree.

    Returns 1 if blocked, 0 if clear (with optional WARN/INFO findings).
    """
    wt = Path(args.worktree).resolve()
    repo = Path(args.repo).resolve() if args.repo else _find_repo_root(wt)
    branch = args.branch or _branch_for_worktree(wt, repo)

    report = preflight.preflight_run(wt, repo, branch_name=branch)

    print(f"Preflight for {wt}")
    print(f"  repo:   {repo}")
    print(f"  branch: {branch}")
    print(f"  blocked: {report.blocked}")
    print(f"  summary: {report.summary()}")
    print()
    if report.findings:
        print("Findings:")
        for f in report.findings:
            detail_str = f" — {f.detail}" if f.detail else ""
            print(f"  [{f.severity.value:5}] {f.code}: {f.message}{detail_str}")
    return 1 if report.blocked else 0


def cmd_remove(args) -> int:
    """Remove a worktree after preflight passes.

    Order of operations:
      1. preflight_run (refuses to proceed on BLOCK unless --force)
      2. safe_delete_branch (with --auto-tag if requested)
      3. git worktree remove --force
    """
    wt = Path(args.worktree).resolve()
    repo = Path(args.repo).resolve() if args.repo else _find_repo_root(wt)
    branch = args.branch or _branch_for_worktree(wt, repo)

    # 1. Preflight
    report = preflight.preflight_run(wt, repo, branch_name=branch)
    if report.blocked and not args.force:
        print("Preflight BLOCKED. Refusing to remove.", file=sys.stderr)
        for f in report.findings:
            if f.severity == preflight.Severity.BLOCK:
                print(f"  [{f.severity.value:5}] {f.code}: {f.message}", file=sys.stderr)
        print("Re-run with --force to override (not recommended).", file=sys.stderr)
        return 1

    # Surface WARN findings even when proceeding
    for f in report.warnings:
        print(f"  [WARN] {f.code}: {f.message}", file=sys.stderr)

    # 2. Branch delete (with reachability check + optional backup tag)
    if branch:
        deleted, status = worktree_lifecycle.safe_delete_branch(
            repo, branch, auto_tag=args.auto_tag
        )
        print(f"Branch {branch}: {status}")
        if not deleted and not status.startswith("unreachable_preserved"):
            # Genuine error (not just "preserved by policy")
            print(f"Branch delete failed: {status}", file=sys.stderr)
            return 2
    else:
        print("No branch name provided; skipping branch delete", file=sys.stderr)

    # 3. Worktree remove
    r = subprocess.run(
        ["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"Worktree remove failed: {r.stderr.strip()}", file=sys.stderr)
        return 2
    print(f"Removed: {wt}")
    return 0


# --- Helpers ------------------------------------------------------------------


def _find_repo_root(worktree_path: Path) -> Path:
    """Find the git repo root for a given worktree path."""
    r = subprocess.run(
        ["git", "-C", str(worktree_path), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"not a git worktree: {worktree_path} ({r.stderr.strip()})")
    # For a worktree, --show-toplevel returns the worktree path itself.
    # Use --git-common-dir to get the main repo root.
    r2 = subprocess.run(
        ["git", "-C", str(worktree_path), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
    )
    if r2.returncode == 0:
        # --git-common-dir returns the .git dir of the main repo; resolve to its parent
        git_dir = Path(r2.stdout.strip())
        if git_dir.name == ".git":
            return git_dir.parent
        # Bare repo case
        return git_dir
    # Fallback: just return the worktree path
    return worktree_path


def _branch_for_worktree(worktree_path: Path, repo_root: Path) -> str:
    """Find the branch name for a worktree (empty string if detached)."""
    r = subprocess.run(
        ["git", "-C", str(worktree_path), "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return ""  # detached HEAD
    return r.stdout.strip()


# --- CLI entry -----------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="worktree_cleanup",
        description="Policy-validated worktree management CLI.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list
    p_list = sub.add_parser("list", help="List worktrees with state")
    p_list.set_defaults(func=cmd_list)

    # preflight
    p_pf = sub.add_parser("preflight", help="Run preflight checks")
    p_pf.add_argument("worktree", help="Path to the worktree")
    p_pf.add_argument("--repo", help="Path to the main repo (auto-detect if omitted)")
    p_pf.add_argument("--branch", help="Branch name (auto-detect if omitted)")
    p_pf.set_defaults(func=cmd_preflight)

    # remove
    p_rm = sub.add_parser("remove", help="Remove a worktree after preflight passes")
    p_rm.add_argument("worktree", help="Path to the worktree")
    p_rm.add_argument("--repo", help="Path to the main repo (auto-detect if omitted)")
    p_rm.add_argument("--branch", help="Branch name (auto-detect if omitted)")
    p_rm.add_argument(
        "--force", action="store_true",
        help="Override BLOCK findings (not recommended)",
    )
    p_rm.add_argument(
        "--auto-tag", action="store_true",
        help="Create a backup tag before force-deleting unreachable branches",
    )
    p_rm.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())