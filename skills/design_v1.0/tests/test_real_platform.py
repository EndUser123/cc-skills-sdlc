#!/usr/bin/env python3
"""
Real platform detection and behavior tests for cross_platform_paths module.

These tests verify that the cross_platform_paths functions work correctly
on the ACTUAL platform detected via platform.system().

This addresses TEST-009: Missing cross-platform execution test.

Run with: pytest P:/.claude/skills/arch/tests/test_real_platform.py -v

NOTE: This is the RED phase - tests are written to FAIL initially to
verify the expected behavior before implementation.
"""

import pytest
import platform
from pathlib import Path
from typing import Literal

# Import the module under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from cross_platform_paths import (
    resolve_cks_db_path,
    resolve_template_path,
    _detect_platform,
)

# Type alias for platform names
PlatformName = Literal["Windows", "Linux", "Darwin", "Unknown"]


class TestRealPlatformDetection:
    """
    Tests for actual platform detection using platform.system().

    These tests verify that the _detect_platform() function correctly
    identifies the actual operating system.
    """

    def test_detect_platform_returns_valid_value(self):
        """
        Test that _detect_platform() returns a valid platform name.

        Given: The current operating system
        When: Calling _detect_platform()
        Then: Should return one of: Windows, Linux, Darwin, or Unknown
        """
        # Act
        detected = _detect_platform()

        # Assert
        valid_platforms = {"Windows", "Linux", "Darwin", "Unknown"}
        assert detected in valid_platforms, (
            f"_detect_platform() returned invalid value: {detected}. "
            f"Expected one of: {valid_platforms}"
        )

    def test_detect_platform_matches_platform_system(self):
        """
        Test that _detect_platform() correctly maps platform.system() output.

        Given: The platform.system() function returns the OS name
        When: Calling _detect_platform()
        Then: Should correctly map to our PlatformName type

        This test ensures the internal platform detection is consistent
        with the standard library's platform detection.
        """
        # Arrange
        system_platform = platform.system()

        # Act
        detected = _detect_platform()

        # Assert - Verify the mapping is correct
        if system_platform == "Windows":
            assert detected == "Windows", (
                f"platform.system() is '{system_platform}' but "
                f"_detect_platform() returned '{detected}'"
            )
        elif system_platform == "Linux":
            assert detected == "Linux", (
                f"platform.system() is '{system_platform}' but "
                f"_detect_platform() returned '{detected}'"
            )
        elif system_platform == "Darwin":
            assert detected == "Darwin", (
                f"platform.system() is '{system_platform}' but "
                f"_detect_platform() returned '{detected}'"
            )
        else:
            # Unknown platform - should map to "Unknown"
            assert detected == "Unknown", (
                f"platform.system() returned '{system_platform}' (unrecognized) "
                f"but _detect_platform() returned '{detected}' instead of 'Unknown'"
            )


class TestRealPlatformPathBehavior:
    """
    Tests for Path() behavior on the real detected platform.

    These tests verify that Path objects behave correctly based on
    the actual platform detected.
    """

    def test_path_behavior_matches_detected_platform(self):
        """
        Test that Path() behavior is consistent with detected platform.

        Given: A platform detected by _detect_platform()
        When: Creating Path objects
        Then: Path behavior should match the detected platform

        This is a CHARACTERIZATION TEST - it documents how Path behaves
        on the current platform, which may differ across platforms.
        """
        # Arrange
        detected_platform = _detect_platform()
        system_platform = platform.system()

        # Act - Create various path types and observe behavior
        p_drive_path = Path("P:/__csf/data/cks.db")
        posix_path = Path("/home/user/__csf/data/cks.db")
        relative_path = Path("relative/path/file.txt")

        # Assert - Document behavior on this platform
        # This test characterizes actual behavior rather than prescribing it
        if detected_platform == "Windows":
            # On Windows, P:/ should be absolute
            assert p_drive_path.is_absolute(), (
                f"On {detected_platform}, P:/ paths should be absolute: {p_drive_path}"
            )
            # Path string representation on Windows may use backslashes
            # but the path object should still recognize it as absolute
        elif detected_platform in ("Linux", "Darwin"):
            # On Unix-like systems, /home/user should be absolute
            assert posix_path.is_absolute(), (
                f"On {detected_platform}, /home/user paths should be absolute: {posix_path}"
            )

        # Relative paths should never be absolute on any platform
        assert not relative_path.is_absolute(), (
            f"On {detected_platform}, relative paths should not be absolute: {relative_path}"
        )

    def test_current_platform_path_separators(self):
        """
        Test that Path uses correct separators for the detected platform.

        Given: A platform detected by _detect_platform()
        When: Creating Path objects
        Then: Path parts should use appropriate separators

        This CHARACTERIZES the actual separator behavior on the current platform.
        """
        # Arrange
        detected_platform = _detect_platform()

        # Act - Create a path with multiple components
        test_path = Path("directory") / "subdirectory" / "file.txt"

        # Assert - Verify separator usage
        path_string = str(test_path)

        if detected_platform == "Windows":
            # On Windows, paths typically use backslashes
            # Note: pathlib on Windows may normalize separators
            assert "\\" in path_string or "/" in path_string, (
                f"On {detected_platform}, path should contain separators: {path_string}"
            )
        elif detected_platform in ("Linux", "Darwin"):
            # On Unix-like systems, paths use forward slashes
            assert "/" in path_string, (
                f"On {detected_platform}, path should contain forward slashes: {path_string}"
            )
            assert "\\" not in path_string, (
                f"On {detected_platform}, path should not contain backslashes: {path_string}"
            )


class TestRealPlatformCrossPlatformFunctions:
    """
    Tests for cross_platform_paths functions on the actual platform.

    These tests verify that the module functions work correctly on the
    real detected platform.
    """

    def test_resolve_cks_db_path_returns_valid_path(self):
        """
        Test that resolve_cks_db_path() returns a valid Path object.

        Given: The current platform detected by _detect_platform()
        When: Calling resolve_cks_db_path()
        Then: Should return a Path object pointing to cks.db

        This test FAILS if the function doesn't exist or doesn't return
        the expected result.
        """
        # Act
        result = resolve_cks_db_path()

        # Assert
        assert isinstance(result, Path), (
            f"resolve_cks_db_path() should return Path object, got: {type(result)}"
        )
        assert result.name == "cks.db", (
            f"resolve_cks_db_path() should return path to cks.db, got: {result.name}"
        )

    def test_resolve_cks_db_path_matches_detected_platform(self):
        """
        Test that resolve_cks_db_path() returns appropriate path for platform.

        Given: A platform detected by _detect_platform()
        When: Calling resolve_cks_db_path()
        Then: Should return path appropriate for that platform

        This test verifies that the path matches the expected format
        for the detected platform.
        """
        # Arrange
        detected_platform = _detect_platform()

        # Act
        result = resolve_cks_db_path()

        # Assert - Verify path matches platform expectations
        result_str = str(result)

        if detected_platform == "Windows":
            # Windows should use P:/ drive
            assert result_str.startswith("P:"), (
                f"On {detected_platform}, path should start with P:: {result_str}"
            )
            assert result.is_absolute(), (
                f"On {detected_platform}, path should be absolute: {result}"
            )
        elif detected_platform == "Linux":
            # Linux should use /home/user
            assert result_str.startswith("/home/user"), (
                f"On {detected_platform}, path should start with /home/user: {result_str}"
            )
            assert result.is_absolute(), (
                f"On {detected_platform}, path should be absolute: {result}"
            )
        elif detected_platform == "Darwin":
            # Mac should use /Users/user
            assert result_str.startswith("/Users/user"), (
                f"On {detected_platform}, path should start with /Users/user: {result_str}"
            )
            assert result.is_absolute(), (
                f"On {detected_platform}, path should be absolute: {result}"
            )
        else:
            # Unknown platform - may return relative path
            # Just verify it's a Path object pointing to cks.db
            assert result.name == "cks.db", (
                f"On {detected_platform}, path should still point to cks.db: {result}"
            )

    def test_resolve_template_path_uses_forward_slashes(self):
        """
        Test that resolve_template_path() always uses forward slashes.

        Given: Any platform (Windows, Linux, Mac, etc.)
        When: Calling resolve_template_path() with a template name
        Then: Should return path with forward slashes only

        This test verifies the cross-platform consistency guarantee.
        """
        # Arrange
        template_name = "fast"

        # Act
        result = resolve_template_path(template_name)

        # Assert
        assert isinstance(result, str), (
            f"resolve_template_path() should return str, got: {type(result)}"
        )
        assert "fast.md" in result, (
            f"resolve_template_path('fast') should contain 'fast.md': {result}"
        )
        assert result.startswith("/"), (
            f"resolve_template_path() should return absolute path: {result}"
        )
        assert "\\" not in result, (
            f"resolve_template_path() should not contain backslashes: {result}"
        )
        assert "/" in result, (
            f"resolve_template_path() should use forward slashes: {result}"
        )

    def test_resolve_template_path_validates_input(self):
        """
        Test that resolve_template_path() validates input.

        Given: Invalid input (empty string, whitespace)
        When: Calling resolve_template_path()
        Then: Should raise ValueError

        This test verifies input validation behavior.
        """
        # Arrange & Act & Assert - Empty string
        with pytest.raises(ValueError, match="must be a non-empty string"):
            resolve_template_path("")

        # Arrange & Act & Assert - Whitespace only
        with pytest.raises(ValueError, match="must be a non-empty string"):
            resolve_template_path("   ")

        # Arrange & Act & Assert - Valid input should not raise
        try:
            result = resolve_template_path("deep")
            assert "deep.md" in result
        except ValueError:
            pytest.fail("resolve_template_path('deep') should not raise ValueError")


class TestRealPlatformIntegration:
    """
    Integration tests for real platform behavior.

    These tests verify end-to-end behavior on the actual platform.
    """

    def test_full_workflow_on_real_platform(self):
        """
        Test complete cross-platform workflow on detected platform.

        Given: The actual detected platform
        When: Using cross_platform_paths functions in a workflow
        Then: All operations should work correctly together

        This is an integration test that verifies the functions work
        together correctly on the real platform.
        """
        # Arrange - Detect platform
        detected_platform = _detect_platform()
        system_platform = platform.system()

        # Act - Use the functions
        cks_path = resolve_cks_db_path()
        template_path = resolve_template_path("python")

        # Assert - Verify results are consistent
        # CKS path should be a Path object
        assert isinstance(cks_path, Path), (
            f"resolve_cks_db_path() should return Path on {detected_platform}"
        )

        # Template path should be a string with forward slashes
        assert isinstance(template_path, str), (
            f"resolve_template_path() should return str on {detected_platform}"
        )
        assert "\\" not in template_path, (
            f"Template path should use forward slashes on {detected_platform}"
        )

        # Document platform-specific behavior
        if detected_platform == "Windows":
            assert str(cks_path).startswith("P:"), (
                f"On Windows, CKS path should use P:/ drive: {cks_path}"
            )
        elif detected_platform == "Linux":
            assert str(cks_path).startswith("/home/user"), (
                f"On Linux, CKS path should use /home/user: {cks_path}"
            )
        elif detected_platform == "Darwin":
            assert str(cks_path).startswith("/Users/user"), (
                f"On Mac, CKS path should use /Users/user: {cks_path}"
            )

    def test_platform_consistency(self):
        """
        Test that platform detection is consistent across multiple calls.

        Given: Multiple calls to _detect_platform()
        When: Calling the function multiple times
        Then: Should return the same result each time

        This test verifies that platform detection is deterministic.
        """
        # Act - Call detection multiple times
        result1 = _detect_platform()
        result2 = _detect_platform()
        result3 = _detect_platform()

        # Assert - All results should be identical
        assert result1 == result2 == result3, (
            f"_detect_platform() should return consistent results: "
            f"{result1}, {result2}, {result3}"
        )

        # Should also match platform.system()
        system_platform = platform.system()
        if system_platform == "Windows":
            assert result1 == "Windows"
        elif system_platform == "Linux":
            assert result1 == "Linux"
        elif system_platform == "Darwin":
            assert result1 == "Darwin"


# -------------------------------------------------------------------------
# Summary of Platform Coverage
# -------------------------------------------------------------------------

"""
PLATFORM COVERAGE ANALYSIS:

This test suite provides coverage for real platform execution:

1. TestRealPlatformDetection:
   - Verifies _detect_platform() returns valid platform names
   - Verifies _detect_platform() matches platform.system()

2. TestRealPlatformPathBehavior:
   - Characterizes Path() behavior on detected platform
   - Documents path separator usage on current platform

3. TestRealPlatformCrossPlatformFunctions:
   - Tests resolve_cks_db_path() on actual platform
   - Tests resolve_template_path() for forward slash consistency
   - Tests input validation behavior

4. TestRealPlatformIntegration:
   - End-to-end workflow tests on real platform
   - Platform consistency verification

RED PHASE NOTES:
- These tests are designed to PASS if cross_platform_paths.py is implemented
- They verify ACTUAL platform behavior, not mocked behavior
- They address TEST-009: Missing cross-platform execution test

EXPECTED TEST RESULTS:
- On Windows: Tests should pass (P:/ paths, Windows detection)
- On Linux: Tests should pass (/home/user paths, Linux detection)
- On Mac: Tests should pass (/Users/user paths, Darwin detection)
- On other platforms: Tests may pass with "Unknown" detection
"""
