#!/usr/bin/env python3
"""
Path resolution utilities for rca hooks.

Provides robust, cross-worktree-safe path resolution for hook scripts.
Resolves paths relative to this file's location, not CWD.
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_hook_root() -> Path:
    """Get the hooks directory containing this module.

    Always resolves from __file__, not from CWD.
    Works across worktrees and different installation locations.

    Returns:
        Path object pointing to the hooks directory.
    """
    # __file__ is always relative to the actual script location
    # This works whether:
    # - Installed in P:/.claude/skills/rca/hooks/
    # - In worktree at P:/worktrees/XXX/.claude/skills/rca/hooks/
    # - In package at P:/packages/rca/skill/hooks/
    return Path(__file__).parent.resolve()


def get_skill_root() -> Path:
    """Get the skill directory containing the hooks folder.

    Returns:
        Path object pointing to the skill directory.
    """
    return get_hook_root().parent


def resolve_hook_path(hook_filename: str) -> Path:
    """Resolve a hook filename to an absolute path.

    Args:
        hook_filename: Just the filename (e.g., "PostToolUse_rca_init.py")

    Returns:
        Absolute Path to the hook file.

    Raises:
        FileNotFoundError: If the resolved hook file doesn't exist.
    """
    hook_path = get_hook_root() / hook_filename
    if not hook_path.exists():
        raise FileNotFoundError(
            f"Hook file not found: {hook_path}\n"
            f"Hook root: {get_hook_root()}\n"
            f"CWD: {Path.cwd()}"
        )
    return hook_path


def verify_all_hooks(expected_hooks: list[str]) -> dict[str, bool]:
    """Verify that all expected hook files exist.

    Args:
        expected_hooks: List of hook filenames to verify.

    Returns:
        Dict mapping filename -> exists (bool).
    """
    results = {}
    for hook_name in expected_hooks:
        try:
            resolve_hook_path(hook_name)
            results[hook_name] = True
        except FileNotFoundError:
            results[hook_name] = False
    return results


# Expected hooks for this skill
EXPECTED_HOOKS = [
    "PostToolUse_rca_init.py",
    "PostToolUse_rca_phase_tracker.py",
    "SessionEnd_rca_cleanup.py",
    "StopHook_rca_enforcement.py",
    "hook_error_rca.py",
    "hook_path_utils.py",
]


def main() -> None:
    """CLI for testing path resolution."""

    print(f"Hooks root: {get_hook_root()}")
    print(f"Skill root: {get_skill_root()}")
    print(f"CWD: {Path.cwd()}")
    print()

    verification = verify_all_hooks(EXPECTED_HOOKS)
    print("Hook file verification:")
    all_exist = True
    for name, exists in verification.items():
        status = "✓" if exists else "✗"
        print(f"  {status} {name}")
        if not exists:
            all_exist = False

    if all_exist:
        print("\n✓ All hooks resolved successfully")
        sys.exit(0)
    else:
        print("\n✗ Some hooks are missing!")
        sys.exit(1)


if __name__ == "__main__":
    main()
