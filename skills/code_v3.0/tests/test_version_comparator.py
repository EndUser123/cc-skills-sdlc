#!/usr/bin/env python3
"""Unit tests for version_comparator utility.

These tests verify semantic version parsing, comparison, and version bump detection.
Run with: pytest tests/test_version_comparator.py -v
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.version_comparator import (
    SemanticVersion,
    parse_version,
    compare_versions,
    detect_version_bump,
)


class TestSemanticVersionDataclass:
    """Test SemanticVersion dataclass structure and initialization."""

    def test_semantic_version_creation_full(self):
        """
        Test creating SemanticVersion with major, minor, and patch.

        Given: Major, minor, and patch version numbers
        When: SemanticVersion is created
        Then: All three components are stored correctly
        """
        # Arrange & Act
        version = SemanticVersion(major=1, minor=2, patch=3)

        # Assert
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3

    def test_semantic_version_creation_partial(self):
        """
        Test creating SemanticVersion with only major and minor.

        Given: Major and minor version numbers (no patch)
        When: SemanticVersion is created
        Then: Major and minor are stored, patch defaults to 0
        """
        # Arrange & Act
        version = SemanticVersion(major=1, minor=2)

        # Assert
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 0

    def test_semantic_version_creation_major_only(self):
        """
        Test creating SemanticVersion with only major.

        Given: Only major version number
        When: SemanticVersion is created
        Then: Major is stored, minor and patch default to 0
        """
        # Arrange & Act
        version = SemanticVersion(major=1)

        # Assert
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0


class TestVersionStringParsing:
    """Test version string parsing functionality."""

    def test_parse_full_semantic_version(self):
        """
        Test parsing full semantic version string "1.2.3".

        Given: A semantic version string "1.2.3"
        When: parse_version() is called
        Then: Returns SemanticVersion(major=1, minor=2, patch=3)
        """
        # Arrange
        version_string = "1.2.3"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 3

    def test_parse_major_minor_only(self):
        """
        Test parsing version string with only major.minor "1.2".

        Given: A version string "1.2"
        When: parse_version() is called
        Then: Returns SemanticVersion(major=1, minor=2, patch=0)
        """
        # Arrange
        version_string = "1.2"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 0

    def test_parse_major_only(self):
        """
        Test parsing version string with only major "1".

        Given: A version string "1"
        When: parse_version() is called
        Then: Returns SemanticVersion(major=1, minor=0, patch=0)
        """
        # Arrange
        version_string = "1"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 1
        assert result.minor == 0
        assert result.patch == 0

    def test_parse_non_semantic_version(self):
        """
        Test graceful handling of non-semantic version strings.

        Given: A non-semantic version string like "v1.2.3-beta" or "latest"
        When: parse_version() is called
        Then: Returns None or a placeholder SemanticVersion
        """
        # Arrange
        version_string = "v1.2.3-beta"

        # Act
        result = parse_version(version_string)

        # Assert - Should handle gracefully, either None or placeholder
        # This test documents current behavior - adjust based on implementation choice
        assert result is None or isinstance(result, SemanticVersion)

    def test_parse_empty_string(self):
        """
        Test parsing empty version string.

        Given: An empty string
        When: parse_version() is called
        Then: Returns None
        """
        # Arrange
        version_string = ""

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is None

    def test_parse_none_input(self):
        """
        Test parsing None input.

        Given: None as input
        When: parse_version() is called
        Then: Returns None
        """
        # Act
        result = parse_version(None)

        # Assert
        assert result is None

    def test_parse_version_with_metadata(self):
        """
        Test parsing version with build metadata.

        Given: A version string like "1.2.3+build123"
        When: parse_version() is called
        Then: Returns SemanticVersion(major=1, minor=2, patch=3), ignoring metadata
        """
        # Arrange
        version_string = "1.2.3+build123"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 3


class TestVersionBumpDetection:
    """Test version bump detection between two versions."""

    def test_detect_major_version_bump(self):
        """
        Test detecting MAJOR version bump (1.x → 2.x).

        Given: Current version "1.5.10", latest version "2.0.0"
        When: detect_version_bump() is called
        Then: Returns "MAJOR" (major version increased)
        """
        # Arrange
        current = "1.5.10"
        latest = "2.0.0"

        # Act
        result = detect_version_bump(current, latest)

        # Assert
        assert result == "MAJOR"

    def test_detect_minor_version_bump(self):
        """
        Test detecting MINOR version bump.

        Given: Current version "1.2.3", latest version "1.3.0"
        When: detect_version_bump() is called
        Then: Returns "MINOR" (minor version increased, major same)
        """
        # Arrange
        current = "1.2.3"
        latest = "1.3.0"

        # Act
        result = detect_version_bump(current, latest)

        # Assert
        assert result == "MINOR"

    def test_detect_patch_version_bump(self):
        """
        Test detecting PATCH version bump.

        Given: Current version "1.2.3", latest version "1.2.4"
        When: detect_version_bump() is called
        Then: Returns "PATCH" (patch version increased, major and minor same)
        """
        # Arrange
        current = "1.2.3"
        latest = "1.2.4"

        # Act
        result = detect_version_bump(current, latest)

        # Assert
        assert result == "PATCH"

    def test_detect_no_version_bump(self):
        """
        Test when versions are identical.

        Given: Current version "1.2.3", latest version "1.2.3"
        When: detect_version_bump() is called
        Then: Returns "NONE" or "SAME" (no version change)
        """
        # Arrange
        current = "1.2.3"
        latest = "1.2.3"

        # Act
        result = detect_version_bump(current, latest)

        # Assert
        assert result in ("NONE", "SAME")

    def test_detect_version_bump_with_partial_versions(self):
        """
        Test version bump detection with partial version strings.

        Given: Current version "1.2", latest version "2.0"
        When: detect_version_bump() is called
        Then: Returns "MAJOR" (correctly detects major bump)
        """
        # Arrange
        current = "1.2"
        latest = "2.0"

        # Act
        result = detect_version_bump(current, latest)

        # Assert
        assert result == "MAJOR"

    def test_detect_version_bump_invalid_versions(self):
        """
        Test graceful handling of invalid version strings.

        Given: Current version "invalid", latest version "also-invalid"
        When: detect_version_bump() is called
        Then: Returns None or handles gracefully
        """
        # Arrange
        current = "invalid"
        latest = "also-invalid"

        # Act
        result = detect_version_bump(current, latest)

        # Assert - Should handle gracefully
        assert result is None or result in ("MAJOR", "MINOR", "PATCH", "NONE", "SAME")


class TestVersionComparisonOperators:
    """Test version comparison operators."""

    def test_version_equal(self):
        """
        Test version equality comparison (==).

        Given: Two identical versions "1.2.3" and "1.2.3"
        When: compare_versions() is called
        Then: Returns 0 (versions are equal)
        """
        # Arrange
        v1 = "1.2.3"
        v2 = "1.2.3"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result == 0

    def test_version_not_equal_greater(self):
        """
        Test version greater than comparison (>).

        Given: Version "2.0.0" and "1.9.9"
        When: compare_versions() is called with (v1, v2)
        Then: Returns positive value (v1 > v2)
        """
        # Arrange
        v1 = "2.0.0"
        v2 = "1.9.9"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result > 0

    def test_version_not_equal_less(self):
        """
        Test version less than comparison (<).

        Given: Version "1.0.0" and "2.0.0"
        When: compare_versions() is called with (v1, v2)
        Then: Returns negative value (v1 < v2)
        """
        # Arrange
        v1 = "1.0.0"
        v2 = "2.0.0"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result < 0

    def test_version_major_determines_order(self):
        """
        Test that major version determines order even if minor/patch differ.

        Given: Version "2.0.0" and "1.99.99"
        When: compare_versions() is called
        Then: "2.0.0" is greater (major version wins)
        """
        # Arrange
        v1 = "2.0.0"
        v2 = "1.99.99"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result > 0

    def test_version_minor_determines_order_when_major_equal(self):
        """
        Test that minor version determines order when major equal.

        Given: Version "1.2.0" and "1.1.99"
        When: compare_versions() is called
        Then: "1.2.0" is greater (minor version wins when major equal)
        """
        # Arrange
        v1 = "1.2.0"
        v2 = "1.1.99"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result > 0

    def test_version_patch_determines_order_when_major_minor_equal(self):
        """
        Test that patch version determines order when major and minor equal.

        Given: Version "1.2.3" and "1.2.2"
        When: compare_versions() is called
        Then: "1.2.3" is greater (patch version wins when major and minor equal)
        """
        # Arrange
        v1 = "1.2.3"
        v2 = "1.2.2"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result > 0

    def test_version_comparison_with_partial_versions(self):
        """
        Test comparison with partial version strings.

        Given: Version "1.2" and "1.2.0"
        When: compare_versions() is called
        Then: Returns 0 (treated as equal when normalized)
        """
        # Arrange
        v1 = "1.2"
        v2 = "1.2.0"

        # Act
        result = compare_versions(v1, v2)

        # Assert
        assert result == 0

    def test_version_comparison_invalid_versions(self):
        """
        Test graceful handling of invalid version strings in comparison.

        Given: Invalid version strings
        When: compare_versions() is called
        Then: Returns None or handles gracefully without crashing
        """
        # Arrange
        v1 = "invalid"
        v2 = "1.2.3"

        # Act
        result = compare_versions(v1, v2)

        # Assert - Should handle gracefully
        # Implementation choice: could return None, raise exception, or use fallback
        assert result is None or isinstance(result, int)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_large_version_numbers(self):
        """
        Test handling of very large version numbers.

        Given: Version string "999.999.999"
        When: parse_version() is called
        Then: Successfully parses without overflow errors
        """
        # Arrange
        version_string = "999.999.999"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 999
        assert result.minor == 999
        assert result.patch == 999

    def test_version_with_leading_zeros(self):
        """
        Test handling of leading zeros in version numbers.

        Given: Version string "01.02.03"
        When: parse_version() is called
        Then: Correctly parses as 1.2.3 (leading zeros ignored)
        """
        # Arrange
        version_string = "01.02.03"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 3

    def test_version_with_spaces(self):
        """
        Test handling of version strings with spaces.

        Given: Version string " 1.2.3 " or "1 . 2 . 3"
        When: parse_version() is called
        Then: Correctly parses by stripping/ignoring spaces
        """
        # Arrange
        version_string = " 1.2.3 "

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 3

    def test_zero_version(self):
        """
        Test handling of 0.0.0 version.

        Given: Version string "0.0.0"
        When: parse_version() is called
        Then: Successfully parses as SemanticVersion(0, 0, 0)
        """
        # Arrange
        version_string = "0.0.0"

        # Act
        result = parse_version(version_string)

        # Assert
        assert result is not None
        assert result.major == 0
        assert result.minor == 0
        assert result.patch == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
