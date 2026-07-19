"""Worktree Lifecycle — repo-portable policy + safe-delete helpers.

Companion module to worktree_safety.py. Extracted as part of PR 2 of
P:/docs/worktree-lifecycle-design.md so the lifecycle logic can be reused
without dragging in the rest of worktree_safety.py (CLI, registry, integration-sensitive checks).

Provides:
- RepoPolicy: per-repo configuration (naming pattern, main branch, etc.)
- load_policy: load policy from worktree-policy.toml (PR 5 adds the file); returns defaults if absent
- validate_name: validate a worktree/branch name against the policy
- safe_delete_branch: reachability-check + auto_tag fallback (extracted from worktree_safety.lifecycle_clean_worktree)

Pure library; no CLI. CLI surface lives in PR 4 (worktree_cleanup.py).
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# Conservative default: alphanumeric, dots, dashes, underscores; must contain at least one dash
# (worktree naming convention "<package>-<purpose>-<terminal-id>" always has multiple dashes).
DEFAULT_NAMING_PATTERN = r"^[a-zA-Z0-9_.-]+$"


@dataclass
class RepoPolicy:
    """Per-repo worktree lifecycle policy.

    Loaded from worktree-policy.toml (added in PR 5). Defaults are
    safe-for-most-repos. The naming pattern is intentionally permissive
    by default — package-specific policy files can tighten it.
    """

    package_name: str = "yt-is"
    main_branch: str = "main"
    naming_pattern: str = DEFAULT_NAMING_PATTERN
    worktree_root: Path = field(default_factory=lambda: Path(".worktrees"))
    backup_tag_prefix: str = "backup"

    def validate_name(self, name: str) -> tuple[bool, str]:
        """Validate a worktree/branch name against the policy.

        Returns (valid, message). Message is empty when valid.
        """
        if not name:
            return False, "name is empty"
        if not re.match(self.naming_pattern, name):
            return False, f"name {name!r} does not match pattern {self.naming_pattern!r}"
        return True, ""


def validate_name(name: str, policy: RepoPolicy | None = None) -> tuple[bool, str]:
    """Standalone wrapper for validating a name against a policy.

    Convenience for callers that don't want to instantiate RepoPolicy
    themselves; defaults to RepoPolicy() when no policy is given.
    """
    p = policy or RepoPolicy()
    return p.validate_name(name)


def load_policy(policy_path: Path | None = None) -> RepoPolicy:
    """Load RepoPolicy from a worktree-policy.toml file.

    Returns defaults if policy_path is None, doesn't exist, can't be read,
    or has a different schema. Never raises — graceful fallback to defaults
    is the contract, since the absence of a policy file shouldn't block
    lifecycle operations (the hook gates the raw commands; this module
    provides policy for the managed CLI).
    """
    if policy_path is None or not policy_path.exists():
        return RepoPolicy()

    # Python 3.11+ has tomllib in stdlib; older Pythons need tomli.
    try:
        import tomllib  # type: ignore
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return RepoPolicy()

    try:
        with open(policy_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return RepoPolicy()

    worktree_cfg = data.get("worktree", {})
    return RepoPolicy(
        package_name=data.get("package", {}).get("name", "yt-is"),
        main_branch=worktree_cfg.get("main_branch", "main"),
        naming_pattern=worktree_cfg.get("naming_pattern", DEFAULT_NAMING_PATTERN),
        worktree_root=Path(worktree_cfg.get("worktree_root", ".worktrees")),
        backup_tag_prefix=worktree_cfg.get("backup_tag_prefix", "backup"),
    )


def safe_delete_branch(
    repo_root: Path,
    branch_name: str,
    *,
    auto_tag: bool = False,
) -> tuple[bool, str]:
    """Delete a branch with reachability check.

    Returns (deleted, status_string). The status string is one of:
      - "merged_deleted"            — branch reachable from main, deleted via -d
      - "backup_tag_deleted:<tag>"  — branch was unreachable; auto_tag=True created backup tag and force-deleted
      - "unreachable_preserved"     — branch was unreachable; auto_tag=False; NOT deleted (caller should escalate)
      - "git_error:<details>"      — a git command failed

    Refuses to delete unreachable branches unless auto_tag=True. With
    auto_tag=True, creates a backup tag (e.g., `backup/<branch>-<timestamp>`)
    that preserves the commit before force-deleting — so the commit is
    never silently lost. The "don't destroy code" principle: a silent
    -D on unreachable work would lose commits that aren't in main.

    Extracted from worktree_safety.lifecycle_clean_worktree (PR 1 fix).
    """
    rr = Path(repo_root)

    # 1. Reachability check against main
    check = subprocess.run(
        ["git", "-C", str(rr), "merge-base", "--is-ancestor", branch_name, "main"],
        capture_output=True, text=True,
    )
    if check.returncode == 0:
        # Reachable -> safe delete via -d (only-merged)
        p = subprocess.run(
            ["git", "-C", str(rr), "branch", "-d", branch_name],
            capture_output=True, text=True,
        )
        if p.returncode == 0:
            return True, "merged_deleted"
        return False, f"git_error: {p.stderr.strip()}"

    # 2. Unreachable branch
    if not auto_tag:
        return False, "unreachable_preserved"

    # 3. Unreachable + auto_tag=True: backup, then force-delete
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    safe_name = branch_name.replace("/", "-")
    tag_name = f"backup/{safe_name}-{stamp}"
    tag = subprocess.run(
        ["git", "-C", str(rr), "tag", "-a", tag_name, branch_name, "-m",
         f"Pre-delete backup of {branch_name}"],
        capture_output=True, text=True,
    )
    if tag.returncode != 0:
        return False, f"git_error_tagging: {tag.stderr.strip()}"

    p = subprocess.run(
        ["git", "-C", str(rr), "branch", "-D", branch_name],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        return False, f"git_error: {p.stderr.strip()}"

    return True, f"backup_tag_deleted:{tag_name}"