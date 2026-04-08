#!/usr/bin/env python3
r"""
Path normalization script for TRACE verification commands.

Auto-normalizes Git Bash paths (/p/...) to Windows native (P:\...)
before running pytest/test commands to prevent path mismatch issues.

Integrates with utils.normalize_paths.normalize_paths_in_command().
"""

import logging
import re

from utils.normalize_paths import (
    normalize_path,
    normalize_paths_in_command,
)

# Configure logging
logger = logging.getLogger(__name__)


def normalize_paths_before_run(command: str) -> str:
    """Normalize all paths in a command string before execution.

    This function:
    1. Finds all Git Bash paths (/p/...) in the command
    2. Converts them to Windows native format (P:\\...)
    3. Logs each transformation for debugging
    4. Returns the normalized command

    Args:
        command: Command string that may contain paths (e.g., "pytest /p/src/test.py")

    Returns:
        Command string with all paths normalized to Windows format

    Example:
        >>> normalize_paths_before_run("pytest /p/.claude/skills/code/tests/test_foo.py -v")
        "pytest P:\\.claude\\skills\\code\\tests\\test_foo.py -v"
        # Log: "Normalized /p/.claude/skills/code/tests/test_foo.py -> P:\\.claude\\skills\\code\tests\test_foo.py"
    """
    if not command:
        return command

    # Track original command for comparison
    original_command = command

    # Normalize all paths in command
    normalized_command = normalize_paths_in_command(command)

    # Log transformations if command changed
    if normalized_command != original_command:
        # Find all Git Bash paths that were normalized
        git_bash_pattern = r'/[a-z]/[\w/\-.]+'
        git_bash_paths = re.findall(git_bash_pattern, original_command)

        for git_bash_path in git_bash_paths:
            normalized = normalize_path(git_bash_path)
            logger.info("Normalized %s -> %s", git_bash_path, normalized)

    return normalized_command


if __name__ == "__main__":
    import sys

    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python normalize_paths_before_run.py '<command>'")
        print("\nExamples:")
        print('  python normalize_paths_before_run.py "pytest /p/src/test.py"')
        print('  python normalize_paths_before_run.py "python -m pytest /p/src/test.py -v"')
        sys.exit(1)

    command_to_normalize = sys.argv[1]
    normalized = normalize_paths_before_run(command_to_normalize)

    print(f"Original:  {command_to_normalize}")
    print(f"Normalized: {normalized}")
