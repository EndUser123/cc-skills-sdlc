"""
Scope Detection Priority for Unified Code Inspection

Implements priority order for detecting git scope:
1. User-specified scope
2. Feature branch → git diff main...HEAD
3. Staged changes → git diff --staged
4. Latest commit → git show HEAD
"""

import logging
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def detect_scope(
    user_scope: Optional[str] = None,
    main_branch: str = "main",
    master_branch: str = "master"
) -> Tuple[str, str]:
    """
    Detect git scope using priority order.

    Args:
        user_scope: User-specified scope (branch, commit, PR, files)
        main_branch: Primary branch name (default: "main")
        master_branch: Legacy branch name (default: "master")

    Returns:
        Tuple of (scope_type, scope_command):
        - scope_type: "user" | "feature_branch" | "staged" | "latest_commit"
        - scope_command: Git command to get the diff

    Examples:
        >>> detect_scope(user_scope="main...HEAD")
        ('user', 'main...HEAD')

        >>> detect_scope()  # On feature branch with no user scope
        ('feature_branch', 'git diff main...HEAD')

        >>> detect_scope()  # On main with staged changes
        ('staged', 'git diff --staged')
    """
    # Priority 1: User-specified scope takes precedence
    if user_scope:
        logger.info(f"Using user-specified scope: {user_scope}")
        return "user", user_scope

    # Priority 2: Feature branch detection
    branch_result = _get_current_branch()
    if branch_result:
        current_branch = branch_result.strip()

        # Check if we're on a feature branch (not main/master)
        if current_branch not in [main_branch, master_branch]:
            scope_cmd = f"git diff {main_branch}...HEAD"
            logger.info(f"Feature branch detected: {current_branch}, using: {scope_cmd}")
            return "feature_branch", scope_cmd

    # Priority 3: Staged changes
    if _has_staged_changes():
        logger.info("Staged changes detected, using: git diff --staged")
        return "staged", "git diff --staged"

    # Priority 4: Latest commit (fallback)
    logger.info("No staged changes, using latest commit: git show HEAD")
    return "latest_commit", "git show HEAD"


def _get_current_branch() -> Optional[str]:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"Failed to get current branch: {e}")
    return None


def _has_staged_changes() -> bool:
    """Check if there are staged changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True,
            timeout=5
        )
        # Return code 1 means there are staged changes
        return result.returncode == 1
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"Failed to check for staged changes: {e}")
        return False


def get_diff_content(scope_command: str) -> str:
    """
    Execute git command and return diff content.

    Args:
        scope_command: Git command to execute (e.g., "git diff main...HEAD")

    Returns:
        Raw diff output as string
    """
    try:
        # Handle both "git diff" and "git show" commands
        if scope_command.startswith("git diff"):
            cmd_parts = scope_command.split()
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=30
            )
        elif scope_command.startswith("git show"):
            cmd_parts = scope_command.split()
            # git show HEAD --format='' to avoid commit header
            result = subprocess.run(
                cmd_parts + ["--format="],
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            # Fallback: treat as git diff argument
            result = subprocess.run(
                ["git", "diff", scope_command],
                capture_output=True,
                text=True,
                timeout=30
            )

        if result.returncode == 0:
            return result.stdout
        else:
            logger.error(f"Git command failed: {result.stderr}")
            return ""

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error(f"Failed to get diff content: {e}")
        return ""


def parse_changed_files(diff_content: str) -> list[str]:
    """
    Parse changed files from git diff output.

    Args:
        diff_content: Raw git diff output

    Returns:
        List of changed file paths
    """
    changed_files = []
    for line in diff_content.split('\n'):
        if line.startswith('diff --git a/'):
            # Extract file path from diff header
            # Format: diff --git a/path/to/file b/path/to/file
            parts = line.split()
            if len(parts) >= 4:
                # Remove 'a/' prefix from the source file path
                file_path = parts[2][2:] if parts[2].startswith('a/') else parts[2]
                changed_files.append(file_path)
    return changed_files
