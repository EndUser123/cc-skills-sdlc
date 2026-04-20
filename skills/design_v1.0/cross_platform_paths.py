#!/usr/bin/env python3
"""
Cross-platform path resolution utilities for the arch skill.

This module provides cross-platform path resolution functions that work
correctly across Windows (P:/), Linux (/home/user), and Mac (/Users/user).

Functions:
    resolve_cks_db_path(): Returns cross-platform path to CKS database
    resolve_template_path(): Returns template path with forward slashes

Example:
    >>> from pathlib import Path
    >>> cks_path = resolve_cks_db_path()
    >>> print(cks_path)
    P:/__csf/data/cks.db  # On Windows
    >>> template = resolve_template_path("fast")
    >>> print(template)
    /.claude/skills/arch/resources/fast.md
"""

from pathlib import Path
import platform
import logging
import os
from typing import Literal

# Configure module-level logger
logger = logging.getLogger(__name__)

# Type alias for platform names
PlatformName = Literal["Windows", "Linux", "Darwin", "Unknown"]

__all__ = [
    "resolve_cks_db_path",
    "resolve_template_path",
    "_detect_platform",
]


def _detect_platform() -> PlatformName:
    """
    Detect the current operating system platform.

    Returns:
        PlatformName: The detected platform name ("Windows", "Linux", "Darwin", or "Unknown")

    Example:
        >>> platform_name = _detect_platform()
        >>> print(f"Running on: {platform_name}")
        Running on: Windows
    """
    system = platform.system()

    if system == "Windows":
        return "Windows"
    elif system == "Linux":
        return "Linux"
    elif system == "Darwin":
        return "Darwin"
    else:
        return "Unknown"


def resolve_cks_db_path() -> Path:
    """
    Resolve the CKS database path across platforms.

    This function returns the absolute path to the CKS database (cks.db)
    based on the current operating system platform. The path is constructed
    as follows:
    - Windows: P:/__csf/data/cks.db
    - Linux: /home/user/__csf/data/cks.db
    - Mac: /Users/user/__csf/data/cks.db
    - Other (fallback): __csf/data/cks.db (relative path)

    Returns:
        Path: Absolute path to CKS database (cks.db)

    Raises:
        None: This function does not raise exceptions; it returns a Path object
              with a fallback for unknown platforms.

    Example:
        >>> from pathlib import Path
        >>> cks_path = resolve_cks_db_path()
        >>> print(cks_path)
        P:/__csf/data/cks.db
        >>> print(cks_path.is_absolute())
        True
        >>> print(cks_path.name)
        cks.db

    Note:
        The path is resolved at runtime based on the detected platform.
        On Windows, this uses the P:/ drive. On Unix-like systems (Linux/Mac),
        it uses the standard user home directory structure.
    """
    detected_platform = _detect_platform()

    if detected_platform == "Windows":
        # Windows: P:/ drive
        cks_path = Path("P:/__csf/data/cks.db")
    elif detected_platform == "Linux":
        # Linux: /home/user
        cks_path = Path("/home/user/__csf/data/cks.db")
    elif detected_platform == "Darwin":
        # Mac: /Users/user
        cks_path = Path("/Users/user/__csf/data/cks.db")
    else:
        # Fallback for other platforms
        cks_path = Path("__csf/data/cks.db")

    logger.debug(f"Resolved CKS DB path for platform '{detected_platform}': {cks_path}")

    return cks_path


def resolve_template_path(template_name: str) -> str:
    """
    Resolve template path with forward slashes.

    This function constructs a template resource path that always uses forward
    slashes regardless of the current platform. This ensures consistency when
    loading template resources across different operating systems.

    Args:
        template_name: Name of the template without file extension.
                      Must be a non-empty string.
                      Examples: "fast", "deep", "python", "cli"

    Returns:
        str: Template path with forward slashes in the format:
             "/.claude/skills/arch/resources/{template_name}.md"

    Raises:
        ValueError: If template_name is empty or contains only whitespace.

    Example:
        >>> resolve_template_path("fast")
        '/.claude/skills/arch/resources/fast.md'
        >>> resolve_template_path("deep")
        '/.claude/skills/arch/resources/deep.md'
        >>> resolve_template_path("python")
        '/.claude/skills/arch/resources/python.md'

    Note:
        The returned path always starts with a forward slash and uses
        forward slashes as path separators, even on Windows systems.
        This ensures consistent path handling for template resources
        across all platforms.

    Edge cases:
        - Empty template_name: Raises ValueError
        - Whitespace-only template_name: Raises ValueError
        - Backslashes in template_name: Converted to forward slashes
    """
    # Validate input
    if not template_name or not template_name.strip():
        raise ValueError(
            f"template_name must be a non-empty string. Got: '{template_name}'"
        )

    # Strip leading/trailing whitespace from template name
    template_name = template_name.strip()

    # Security validation: Detect and reject path traversal patterns (SEC-001)
    # Check for null bytes (potential string truncation attacks)
    if "\x00" in template_name:
        raise ValueError(
            f"template_name contains null byte which is unsafe. Got: '{template_name}'"
        )

    # Check for path traversal sequences (../ or ..\)
    if ".." in template_name:
        raise ValueError(
            f"template_name contains path traversal sequence ('..') which is unsafe. Got: '{template_name}'"
        )

    # Check for absolute paths (Unix-style / or Windows-style drive letters)
    # Unix absolute paths start with /
    if template_name.startswith("/"):
        raise ValueError(
            f"template_name contains absolute path which is unsafe. Got: '{template_name}'"
        )

    # Windows absolute paths with drive letters (e.g., C:, P:, etc.)
    if len(template_name) >= 2 and template_name[1] == ":":
        raise ValueError(
            f"template_name contains absolute path with drive letter which is unsafe. Got: '{template_name}'"
        )

    # Check for URL-encoded path traversal sequences
    # %2e%2e%2f is URL-encoded "../"
    # %252e%252e%252f is double-encoded "../"
    if "%2e" in template_name.lower() or "%25" in template_name.lower():
        raise ValueError(
            f"template_name contains url-encoded path traversal which is unsafe. Got: '{template_name}'"
        )

    # SEC-001 FIX: Use os.path.basename to extract only the filename component
    # This ensures that even if validation has edge cases, only the basename is used
    # Defense-in-depth: prevents path traversal even if validation is bypassed
    safe_name = os.path.basename(template_name)

    # After basename extraction, re-validate that safe_name doesn't contain path separators
    # If basename changed the value, it means path components were present
    if safe_name != template_name:
        raise ValueError(
            f"template_name must be a simple filename without path components. Got: '{template_name}'"
        )

    # Construct path with forward slashes using the validated, sanitized name
    template_path = f"/.claude/skills/arch/resources/{safe_name}.md"

    # Ensure no backslashes in the path (even on Windows)
    # This handles cases where template_name might contain backslashes
    template_path = template_path.replace("\\", "/")

    logger.debug(f"Resolved template path for '{template_name}': {template_path}")

    return template_path
