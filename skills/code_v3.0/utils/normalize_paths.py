#!/usr/bin/env python3
"""
Path normalization utility for /code skill (Windows-only).

Ensures all paths use Windows native format (P:\\...) to prevent
verification failures between Git Bash (/p/...) and PowerShell (P:\\...).

Author: /code skill improvement document
Date: 2026-03-01
"""

import re
from pathlib import Path


def normalize_path(path_str: str) -> str:
    """Normalize any path format to Windows native (P:\\...).

    Handles:
    - Git Bash style: /p/path/to/file -> P:/path/to/file
    - Relative paths: ./file -> P:/project/file
    - Forward slashes: P:/path/to/file -> P:\\path\\to\\file

    Args:
        path_str: Path string in any format.

    Returns:
        Normalized path string in Windows native format, or None if input is None.
    """
    if path_str is None:
        return None

    if not path_str:
        return path_str

    # Handle Git Bash style: /p/path/to/file -> P:/path/to/file
    if re.match(r'^/[a-z]/', path_str):
        drive_letter = path_str[1].upper()
        rest = path_str[2:]
        path_str = f"{drive_letter}:{rest}"

    # Convert to Path object and back to string (uses native format)
    try:
        return str(Path(path_str).resolve())
    except (OSError, RuntimeError, ValueError):
        # If path doesn't exist or can't be resolved,
        # return the normalized version without resolution
        return str(Path(path_str))


def normalize_paths_in_command(command: str) -> str:
    """Find and normalize all paths in a command string.

    Matches common path patterns:
    - Git Bash style: /p/path/to/file
    - Windows style: P:\\path\\to\\file
    - Relative paths: ./file or ../file

    Args:
        command: Command string that may contain paths.

    Returns:
        Command string with all paths normalized to Windows format.
    """
    if not command:
        return command

    # Match common path patterns
    # Pattern matches: /p/... OR P:\... OR ./file OR ../file
    path_pattern = r'(?:/[a-z]/[\w/\-.]+|[A-Z]:[/\\][\w/\\\-.]+|\.\.?/[\w/\\\-.]+)'

    def replace_path(match):
        return normalize_path(match.group(0))

    return re.sub(path_pattern, replace_path, command)


def normalize_path_list(path_list: list[str]) -> list[str]:
    """Normalize a list of paths.

    Args:
        path_list: List of path strings.

    Returns:
        List of normalized path strings.
    """
    return [normalize_path(p) for p in path_list]


def is_git_bash_path(path_str: str) -> bool:
    """Check if path is in Git Bash format.

    Args:
        path_str: Path string to check.

    Returns:
        True if path matches Git Bash format (/p/...), False otherwise.
    """
    return bool(re.match(r'^/[a-z]/', path_str))


def is_windows_path(path_str: str) -> bool:
    """Check if path is in Windows format.

    Args:
        path_str: Path string to check.

    Returns:
        True if path matches Windows format (P:\\... or P:/...), False otherwise.
    """
    return bool(re.match(r'^[A-Z]:', path_str))


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Test mode: normalize paths from command line
        for arg in sys.argv[1:]:
            normalized = normalize_path(arg)
            print(f"{arg} -> {normalized}")
    else:
        # Demo mode
        test_paths = [
            "/p/project/src/auth.py",
            "P:/project/src/auth.py",
            "./tests/test_auth.py",
            "../config/settings.json"
        ]

        print("Path normalization examples:")
        for path in test_paths:
            normalized = normalize_path(path)
            print(f"  {path:30} -> {normalized}")
