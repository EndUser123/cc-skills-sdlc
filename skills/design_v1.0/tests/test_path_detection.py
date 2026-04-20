#!/usr/bin/env python3
"""
Failing tests for Path-based path detection (TEST-008).

These tests verify that path detection should use Path object inspection
(instead of brittle regex) to detect path separators and components.

The current implementation in test_harcoded_paths.py line 327 uses a complex
regex pattern that is brittle and can miss edge cases.

This regex approach has issues:
1. Can miss edge cases (Unicode filenames, special characters)
2. Can match false positives (escaped characters in code blocks)
3. Brittle to maintain across different path formats

These tests FAIL in RED phase because the new Path-based detection
functions do not exist yet.

Run with: pytest P:/.claude/skills/arch/tests/test_path_detection.py -v
"""

from pathlib import Path
import pytest
import sys

# Add parent directory to path for importing the new module
module_dir = Path(__file__).parent.parent
if str(module_dir) not in sys.path:
    sys.path.insert(0, str(module_dir))


class TestDetectPathBackslashesUsingPath:
    """
    Tests for detect_path_backslashes() function.

    This function should replace the brittle regex in test_harcoded_paths.py
    with Path-based detection using Path.as_posix().
    """

    def test_function_exists(self):
        """
        Test that detect_path_backslashes() function exists.

        Given: The path_detection module
        When: Importing detect_path_backslashes
        Then: Function should exist

        This test FAILS in RED phase because the function doesn't exist.
        """
        # Arrange & Act - Try to import the new function
        try:
            from path_detection import detect_path_backslashes

            function_exists = True
        except ImportError:
            function_exists = False

        # Assert - Function should exist (will FAIL in RED phase)
        assert function_exists, (
            "detect_path_backslashes() function should exist in path_detection module. "
            "This function replaces the brittle regex in test_harcoded_paths.py line 327."
        )

    def test_detect_windows_path_backslashes(self):
        """
        Test that detect_path_backslashes() detects Windows backslashes.

        Given: A Windows path string with backslashes
        When: Calling detect_path_backslashes()
        Then: Should return True (has path backslashes)

        This test FAILS in RED phase because the function doesn't exist.
        """
        # Arrange
        from path_detection import detect_path_backslashes

        test_cases = [
            "P:\\data\\file.txt",
            "C:\\Users\\test\\document.md",
            ".\\relative\\path",
        ]

        # Act & Assert
        for test_path in test_cases:
            result = detect_path_backslashes(test_path)
            assert result is True, (
                f"detect_path_backslashes('{test_path}') should return True "
                f"for Windows paths with backslashes. Got: {result}"
            )

    def test_no_backslashes_in_unix_paths(self):
        """
        Test that detect_path_backslashes() returns False for Unix paths.

        Given: A Unix path string with forward slashes
        When: Calling detect_path_backslashes()
        Then: Should return False (no path backslashes)

        This test FAILS in RED phase because the function doesn't exist.
        """
        # Arrange
        from path_detection import detect_path_backslashes

        test_cases = [
            "/usr/local/bin",
            "/home/user/document.md",
            "relative/path/to/file",
        ]

        # Act & Assert
        for test_path in test_cases:
            result = detect_path_backslashes(test_path)
            assert result is False, (
                f"detect_path_backslashes('{test_path}') should return False "
                f"for Unix paths with forward slashes. Got: {result}"
            )

    def test_handles_unicode_filenames(self):
        """
        Test that detect_path_backslashes() handles Unicode filenames.

        Given: A path with Unicode characters
        When: Calling detect_path_backslashes()
        Then: Should correctly detect backslashes without regex issues

        This test FAILS in RED phase because the function doesn't exist.
        Edge case that regex struggles with.
        """
        # Arrange
        from path_detection import detect_path_backslashes

        test_cases = [
            "C:\\Users\\café\\document.md",
            "P:\\data\\文件\\readme.txt",
            "/home/user/тест/file.py",  # Unix with Unicode, no backslash
        ]

        # Act & Assert
        windows_results = [
            detect_path_backslashes(test_cases[0]),
            detect_path_backslashes(test_cases[1]),
        ]
        unix_result = detect_path_backslashes(test_cases[2])

        assert all(windows_results), (
            "Should detect backslashes in Windows paths with Unicode filenames"
        )
        assert unix_result is False, (
            "Should not detect backslashes in Unix paths with Unicode filenames"
        )


class TestExtractPathComponentsUsingParts:
    """
    Tests for extract_path_components() function.

    This function should use Path.parts instead of regex splitting
    to extract path components reliably.
    """

    def test_function_exists(self):
        """
        Test that extract_path_components() function exists.

        Given: The path_detection module
        When: Importing extract_path_components
        Then: Function should exist

        This test FAILS in RED phase because the function doesn't exist.
        """
        # Arrange & Act - Try to import the new function
        try:
            from path_detection import extract_path_components

            function_exists = True
        except ImportError:
            function_exists = False

        # Assert - Function should exist (will FAIL in RED phase)
        assert function_exists, (
            "extract_path_components() function should exist in path_detection module. "
            "This function uses Path.parts instead of regex for component extraction."
        )

    def test_extract_components_from_unix_path(self):
        """
        Test that extract_path_components() extracts Unix path parts.

        Given: A Unix path string
        When: Calling extract_path_components()
        Then: Should return list of path components using Path.parts

        This test FAILS in RED phase because the function doesn't exist.
        """
        # Arrange
        from path_detection import extract_path_components

        test_path = "/.claude/skills/arch/resources/fast.md"

        # Act
        components = extract_path_components(test_path)

        # Assert
        assert isinstance(components, list), (
            f"extract_path_components() should return list. Got: {type(components)}"
        )
        assert "fast.md" in components, (
            f"Filename should be in components. Got: {components}"
        )
        assert ".claude" in components, (
            f"Directory should be in components. Got: {components}"
        )

    def test_extract_components_from_windows_path(self):
        """
        Test that extract_path_components() extracts Windows path parts.

        Given: A Windows path string
        When: Calling extract_path_components()
        Then: Should return list of path components using Path.parts

        This test FAILS in RED phase because the function doesn't exist.
        """
        # Arrange
        from path_detection import extract_path_components

        test_path = "P:\\__csf\\data\\cks.db"

        # Act
        components = extract_path_components(test_path)

        # Assert
        assert isinstance(components, list), (
            f"extract_path_components() should return list. Got: {type(components)}"
        )
        assert "cks.db" in components, (
            f"Filename should be in components. Got: {components}"
        )
        assert "__csf" in components or "data" in components, (
            f"Directory should be in components. Got: {components}"
        )

    def test_handles_special_chars_in_filenames(self):
        """
        Test that extract_path_components() handles special characters.

        Given: Paths with special characters (dots, spaces, dashes)
        When: Calling extract_path_components()
        Then: Should correctly preserve special characters in components

        This test FAILS in RED phase because the function doesn't exist.
        Edge case that regex struggles with.
        """
        # Arrange
        from path_detection import extract_path_components

        test_cases = [
            "/data/file.with.dots.txt",
            "/data/file-with-dash.txt",
            "/data/file_with_underscore.txt",
            "/data/file with spaces.txt",
        ]

        # Act & Assert
        for test_path in test_cases:
            components = extract_path_components(test_path)
            # Extract just the filename from the test path
            expected_filename = test_path.split("/")[-1]
            assert expected_filename in components, (
                f"Filename '{expected_filename}' should be preserved in components. "
                f"Got: {components}"
            )


class TestPathDetectionModuleExists:
    """
    Tests that the new path_detection module exists.
    """

    def test_path_detection_module_exists(self):
        """
        Test that path_detection.py module exists.

        Given: The arch skill directory
        When: Importing path_detection module
        Then: Module should be importable

        This test FAILS in RED phase because the module doesn't exist.
        """
        # Arrange & Act - Try to import the module
        try:
            import path_detection

            module_exists = True
        except ImportError:
            module_exists = False

        # Assert - Module should exist (will FAIL in RED phase)
        assert module_exists, (
            "path_detection.py module should exist at "
            f"{module_dir / 'path_detection.py'}. "
            "This module provides Path-based path detection functions to replace "
            "the brittle regex in test_harcoded_paths.py line 327."
        )


if __name__ == "__main__":
    # Run tests with pytest
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"], cwd=Path(__file__).parent
    )
    sys.exit(result.returncode)
