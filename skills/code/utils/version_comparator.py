#!/usr/bin/env python3
"""Semantic version parsing and comparison utility.

This module provides functionality for parsing semantic version strings,
comparing versions, and detecting version bump types (MAJOR/MINOR/PATCH).
"""

from dataclasses import dataclass
from re import match
from typing import Optional, Literal

# Version pattern regex: matches "1", "1.2", "1.2.3" with optional "v" prefix
_VERSION_PATTERN: str = r'^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?'

# Version bump type constants
BUMP_MAJOR: Literal["MAJOR"] = "MAJOR"
BUMP_MINOR: Literal["MINOR"] = "MINOR"
BUMP_PATCH: Literal["PATCH"] = "PATCH"
BUMP_NONE: Literal["NONE"] = "NONE"


@dataclass
class SemanticVersion:
    """Represents a semantic version with major, minor, and patch components.

    Attributes:
        major: Major version number (required)
        minor: Minor version number (defaults to 0)
        patch: Patch version number (defaults to 0)
    """

    major: int
    minor: int = 0
    patch: int = 0


def parse_version(version_string: Optional[str]) -> Optional[SemanticVersion]:
    """Parse a semantic version string into a SemanticVersion object.

    This function handles various version string formats including:
    - Full semantic versions: "1.2.3"
    - Partial versions: "1.2", "1"
    - Versions with 'v' prefix: "v1.2.3"
    - Versions with build metadata: "1.2.3+build123"

    Args:
        version_string: Version string to parse (e.g., "1.2.3", "1.2", "1")

    Returns:
        SemanticVersion object if parsing succeeds, None otherwise

    Examples:
        >>> parse_version("1.2.3")
        SemanticVersion(major=1, minor=2, patch=3)
        >>> parse_version("2.0")
        SemanticVersion(major=2, minor=0, patch=0)
        >>> parse_version(None)
        None
    """
    if version_string is None:
        return None

    if not version_string or not isinstance(version_string, str):
        return None

    # Strip whitespace
    version_string = version_string.strip()

    if not version_string:
        return None

    # Handle version with build metadata (e.g., "1.2.3+build123")
    # Split on '+' and take only the version part
    if '+' in version_string:
        version_string = version_string.split('+')[0]

    match_result = match(_VERSION_PATTERN, version_string)
    if not match_result:
        return None

    major_str, minor_str, patch_str = match_result.groups()

    try:
        major = int(major_str)
        minor = int(minor_str) if minor_str else 0
        patch = int(patch_str) if patch_str else 0
    except (ValueError, TypeError):
        return None

    return SemanticVersion(major=major, minor=minor, patch=patch)


def compare_versions(v1: Optional[str], v2: Optional[str]) -> Optional[int]:
    """Compare two version strings.

    Compares versions semantically: major version first, then minor, then patch.
    Partial versions are treated as if missing components are 0.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        Positive int if v1 > v2, negative int if v1 < v2, 0 if equal,
        None if either version cannot be parsed

    Examples:
        >>> compare_versions("2.0.0", "1.9.9") > 0
        True
        >>> compare_versions("1.2", "1.2.0")
        0
        >>> compare_versions("invalid", "1.2.3") is None
        True
    """
    version1 = parse_version(v1)
    version2 = parse_version(v2)

    if version1 is None or version2 is None:
        return None

    # Compare major version
    if version1.major != version2.major:
        return version1.major - version2.major

    # Compare minor version
    if version1.minor != version2.minor:
        return version1.minor - version2.minor

    # Compare patch version
    if version1.patch != version2.patch:
        return version1.patch - version2.patch

    # Versions are equal
    return 0


def detect_version_bump(
    current: Optional[str], latest: Optional[str]
) -> Optional[Literal["MAJOR", "MINOR", "PATCH", "NONE"]]:
    """Detect the type of version bump between current and latest versions.

    Determines the semantic versioning bump type by comparing version components
    in order of precedence: MAJOR > MINOR > PATCH. If the latest version is
    older than the current version, returns "NONE".

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        "MAJOR" if major version increased,
        "MINOR" if minor version increased (major same),
        "PATCH" if patch version increased (major and minor same),
        "NONE" if versions are equal or latest is older,
        None if either version cannot be parsed

    Examples:
        >>> detect_version_bump("1.2.3", "2.0.0")
        "MAJOR"
        >>> detect_version_bump("1.2.3", "1.3.0")
        "MINOR"
        >>> detect_version_bump("1.2.3", "1.2.4")
        "PATCH"
        >>> detect_version_bump("1.2.3", "1.2.3")
        "NONE"
    """
    current_version = parse_version(current)
    latest_version = parse_version(latest)

    if current_version is None or latest_version is None:
        return None

    # Check for version equality
    if (
        current_version.major == latest_version.major
        and current_version.minor == latest_version.minor
        and current_version.patch == latest_version.patch
    ):
        return BUMP_NONE

    # Check for MAJOR version bump
    if latest_version.major > current_version.major:
        return BUMP_MAJOR

    # Check for MINOR version bump
    if latest_version.minor > current_version.minor:
        return BUMP_MINOR

    # Check for PATCH version bump
    if latest_version.patch > current_version.patch:
        return BUMP_PATCH

    # If latest is older than current (shouldn't happen), return NONE
    return BUMP_NONE
