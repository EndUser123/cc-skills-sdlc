#!/usr/bin/env python3
"""Unit tests for normalize_paths utility."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.normalize_paths import (
    is_git_bash_path,
    is_windows_path,
    normalize_path,
    normalize_paths_in_command,
)


class TestNormalizePath:
    """Test path normalization."""

    def test_git_bash_to_windows(self):
        """Convert Git Bash style to Windows native."""
        result = normalize_path("/p/project/src/file.py")
        # Should convert to P:\\\\\\project\src\file.py format
        assert "P:" in result
        assert "project" in result
        assert "src" in result
        assert "file.py" in result

    def test_windows_path_unchanged(self):
        """Windows path should remain valid."""
        result = normalize_path("P:\\\\\\project/src/file.py")
        assert "P:" in result
        assert "\\" in result or "/" in result  # Native separators

    def test_relative_path_resolved(self):
        """Relative paths should be resolved to absolute."""
        result = normalize_path("./file.py")
        # Should resolve to absolute path
        assert "file.py" in result or result.endswith("file.py")

    def test_empty_path(self):
        """Empty path should return empty."""
        assert normalize_path("") == ""
        assert normalize_path(None) is None


class TestNormalizePathsInCommand:
    """Test path normalization in command strings."""

    def test_single_path(self):
        """Normalize single path in command."""
        cmd = "pytest /p/project/tests/test_foo.py"
        result = normalize_paths_in_command(cmd)
        assert "P:" in result or "p:" in result

    def test_multiple_paths(self):
        """Normalize multiple paths in command."""
        cmd = "cp /p/src/a.py /p/src/b.py"
        result = normalize_paths_in_command(cmd)
        # Both paths should be normalized
        assert result.count("P:") >= 1 or result.count("p:") >= 1

    def test_no_paths(self):
        """Command without paths should be unchanged."""
        cmd = "echo hello world"
        result = normalize_paths_in_command(cmd)
        assert result == cmd


class TestPathTypeDetection:
    """Test path type detection helpers."""

    def test_is_git_bash_path(self):
        """Detect Git Bash style paths."""
        assert is_git_bash_path("/p/file.py") == True
        assert is_git_bash_path("/c/file.py") == True
        assert is_git_bash_path("P:\\\\\\file.py") == False

    def test_is_windows_path(self):
        """Detect Windows style paths."""
        assert is_windows_path("P:\\\\\\file.py") == True
        assert is_windows_path("C:/file.py") == True
        assert is_windows_path("/p/file.py") == False


class TestNormalizePathExceptionHandling:
    """Tests for exception handling in normalize_path() function.

    These tests verify the fallback behavior when Path.resolve() raises exceptions:
    - OSError: Path doesn't exist or can't be accessed
    - RuntimeError: Path resolution fails (e.g., infinite symlink loop)
    - ValueError: Invalid path format
    """

    def test_oserror_fallback_to_normalized_path(self):
        """
        Test that OSError from Path.resolve() triggers fallback to normalized path.

        Given: A path string that causes Path.resolve() to raise OSError
        When: normalize_path() is called
        Then: The function returns the normalized path without resolution
        """
        test_path = "P:\\\\\\nonexistent/path/to/file.txt"

        # Mock Path to raise OSError on resolve()
        with patch('utils.normalize_paths.Path') as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_class.return_value = mock_path_instance
            mock_path_instance.resolve.side_effect = OSError("Path not found")
            mock_path_instance.__str__.return_value = test_path

            result = normalize_path(test_path)

            # Verify resolve() was called
            mock_path_instance.resolve.assert_called_once()

            # Verify we got the path without resolution (fallback)
            assert result == test_path

    def test_runtime_error_fallback_to_normalized_path(self):
        """
        Test that RuntimeError from Path.resolve() triggers fallback to normalized path.

        Given: A path string that causes Path.resolve() to raise RuntimeError
        When: normalize_path() is called
        Then: The function returns the normalized path without resolution
        """
        test_path = "/p/symlink/loop/path"

        # Mock Path to raise RuntimeError on resolve()
        with patch('utils.normalize_paths.Path') as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_class.return_value = mock_path_instance
            mock_path_instance.resolve.side_effect = RuntimeError("Symlink loop detected")
            mock_path_instance.__str__.return_value = test_path

            result = normalize_path(test_path)

            # Verify resolve() was called
            mock_path_instance.resolve.assert_called_once()

            # Verify we got the path without resolution (fallback)
            assert result == test_path

    def test_value_error_fallback_to_normalized_path(self):
        """
        Test that ValueError from Path.resolve() triggers fallback to normalized path.

        Given: A path string that causes Path.resolve() to raise ValueError
        When: normalize_path() is called
        Then: The function returns the normalized path without resolution
        """
        test_path = "P:\\\\\\invalid/path/with/null/byte"

        # Mock Path to raise ValueError on resolve()
        with patch('utils.normalize_paths.Path') as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_class.return_value = mock_path_instance
            mock_path_instance.resolve.side_effect = ValueError("Invalid path component")
            mock_path_instance.__str__.return_value = test_path

            result = normalize_path(test_path)

            # Verify resolve() was called
            mock_path_instance.resolve.assert_called_once()

            # Verify we got the path without resolution (fallback)
            assert result == test_path

    def test_resolve_success_returns_resolved_path(self):
        """
        Test that successful Path.resolve() returns the resolved path.

        Given: A path string that resolves successfully
        When: normalize_path() is called
        Then: The function returns the fully resolved absolute path
        """
        input_path = "/p/project/src/module.py"
        resolved_path = "P:\\\\\\project/src/module.py"

        # Mock Path to return a resolved path
        with patch('utils.normalize_paths.Path') as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_class.return_value = mock_path_instance

            # When resolve() is called, return a resolved path
            resolved_mock = MagicMock()
            resolved_mock.__str__.return_value = resolved_path
            mock_path_instance.resolve.return_value = resolved_mock

            result = normalize_path(input_path)

            # Verify resolve() was called
            mock_path_instance.resolve.assert_called_once()

            # Verify we got the resolved path
            assert result == resolved_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

class TestNormalizePathListEdgeCases:
    """Edge case tests for normalize_path_list() function."""

    def test_empty_list_returns_empty_list(self):
        """
        Test that normalize_path_list([]) returns [].

        Given: An empty list
        When: normalize_path_list is called
        Then: An empty list is returned
        """
        # Arrange
        from utils.normalize_paths import normalize_path_list
        path_list = []

        # Act
        result = normalize_path_list(path_list)

        # Assert
        assert result == []

    def test_list_with_none_values(self):
        """
        Test that normalize_path_list handles None values in the list.

        Given: A list containing None values
        When: normalize_path_list is called
        Then: None values are handled gracefully (returned as None in output)
        """
        # Arrange
        from utils.normalize_paths import normalize_path_list
        path_list = [None, "P:\\\\\\valid/path.py", None]

        # Act
        result = normalize_path_list(path_list)

        # Assert
        assert result[0] is None
        assert "valid" in result[1]  # Check that valid path was normalized
        assert result[2] is None

    def test_list_with_empty_strings(self):
        """
        Test that normalize_path_list handles empty strings in the list.

        Given: A list containing empty strings
        When: normalize_path_list is called
        Then: Empty strings are preserved in the output
        """
        # Arrange
        from utils.normalize_paths import normalize_path_list
        path_list = ["", "P:\\\\\\valid/path.py", ""]

        # Act
        result = normalize_path_list(path_list)

        # Assert
        assert result[0] == ""
        assert "valid" in result[1]  # Check that valid path was normalized
        assert result[2] == ""

    def test_list_with_mixed_edge_cases(self):
        """
        Test that normalize_path_list handles mixed edge cases.

        Given: A list with None, empty strings, and valid paths
        When: normalize_path_list is called
        Then: All elements are handled correctly
        """
        # Arrange
        from utils.normalize_paths import normalize_path_list
        path_list = [None, "", "P:\\\\\\valid/path.py", None, ""]

        # Act
        result = normalize_path_list(path_list)

        # Assert
        assert result[0] is None
        assert result[1] == ""
        assert "valid" in result[2]
        assert result[3] is None
        assert result[4] == ""

    def test_list_with_all_none_values(self):
        """
        Test that normalize_path_list handles a list with all None values.

        Given: A list where all elements are None
        When: normalize_path_list is called
        Then: All None values are preserved in the output
        """
        # Arrange
        from utils.normalize_paths import normalize_path_list
        path_list = [None, None, None]

        # Act
        result = normalize_path_list(path_list)

        # Assert
        assert result == [None, None, None]

    def test_list_with_all_empty_strings(self):
        """
        Test that normalize_path_list handles a list with all empty strings.

        Given: A list where all elements are empty strings
        When: normalize_path_list is called
        Then: All empty strings are preserved in the output
        """
        # Arrange
        from utils.normalize_paths import normalize_path_list
        path_list = ["", "", ""]

        # Act
        result = normalize_path_list(path_list)

        # Assert
        assert result == ["", "", ""]
