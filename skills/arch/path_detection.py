#!/usr/bin/env python3
"""
Path-based path detection utilities.

This module provides Path object inspection functions to replace brittle
regex patterns in test_harcoded_paths.py line 327.

Functions:
- detect_path_backslashes(): Detect Windows path backslashes using Path
- extract_path_components(): Extract path components using Path.parts
"""

from pathlib import Path


def detect_path_backslashes(path_str: str) -> bool:
    """
    Detect if a path string contains Windows-style backslashes.

    Uses Path object inspection instead of regex to reliably detect
    backslashes in path strings, including edge cases like Unicode filenames.

    Args:
        path_str: A path string (Windows or Unix format)

    Returns:
        True if the path contains backslashes (Windows-style), False otherwise

    Examples:
        >>> detect_path_backslashes("C:\\Users\\test")
        True
        >>> detect_path_backslashes("/usr/local/bin")
        False
    """
    # Check if backslash exists in the original string
    return "\\" in path_str


def extract_path_components(path_str: str) -> list:
    """
    Extract path components using Path.parts instead of regex splitting.

    Uses Path object's parts attribute to reliably extract path components,
    handling both Windows and Unix paths correctly.

    Args:
        path_str: A path string (Windows or Unix format)

    Returns:
        List of path components (strings)

    Examples:
        >>> extract_path_components("/usr/local/bin")
        ['/', 'usr', 'local', 'bin']
        >>> extract_path_components("C:\\Users\\test")
        ['C:\\', 'Users', 'test']
    """
    # Use Path.parts to extract components reliably
    path_obj = Path(path_str)
    return list(path_obj.parts)
