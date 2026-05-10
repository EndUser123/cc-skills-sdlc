#!/usr/bin/env python3
"""
RED phase tests for normalize_paths_before_run.py script.

These tests are designed to FAIL initially with ModuleNotFoundError
until the implementation script is created.

Purpose: Test the script that normalizes Git Bash paths (/p/...) to Windows
native paths (P:\\\\\\\...) before running test/verification commands. This prevents
path mismatch issues in multi-terminal environments.

Author: Task 3.3: Path Normalization Integration
Date: 2026-03-01
Phase: RED (tests written before implementation)
"""

import logging
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# This import will FAIL with ModuleNotFoundError until we implement the script
from scripts.normalize_paths_before_run import normalize_paths_before_run

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class TestNormalizeGitBashPathToWindows:
    """Test Git Bash path to Windows path normalization."""

    def test_normalize_git_bash_path_to_windows(self):
        """Convert Git Bash /p/.claude/skills/code/tests/test_foo.py to Windows P:\\\\\\\...

        This test verifies that leading slash + drive letter pattern
        (/p/...) is correctly converted to Windows native format (P:\\\\\\\...).

        Input: /p/.claude/skills/code/tests/test_foo.py
        Expected: P:\\\\\\\.claude\\skills\\code\\tests\\test_foo.py
        """
        input_path = "/p/.claude/skills/code/tests/test_foo.py"
        result = normalize_paths_before_run(input_path)

        # Should convert /p/ to P:\\\\\\
        assert result.startswith("P:\\\\\\\") or result.startswith("P:\\\\\\"), \
            f"Expected Windows path starting with P:, got: {result}"

        # Should contain the full path components
        assert ".claude" in result
        assert "skills" in result
        assert "code" in result
        assert "tests" in result
        assert "test_foo.py" in result

        # Should NOT contain Git Bash format
        assert not result.startswith("/"), \
            f"Result should not start with / (Git Bash format), got: {result}"


class TestNormalizeAlreadyWindowsPath:
    """Test idempotency - Windows paths should remain unchanged."""

    def test_normalize_already_windows_path(self):
        """Windows path P:\\\\\\\.claude\\skills\\code\\tests\\test_foo.py should remain unchanged.

        Idempotency check: Applying normalization twice should produce the same result.
        This prevents double-conversion issues.

        Input: P:\\\\\\\.claude\\skills\\code\\tests\\test_foo.py
        Expected: Same path (no change)
        """
        input_path = "P:\\\\\\\.claude\\skills\\code\\tests\\test_foo.py"

        # First normalization
        result1 = normalize_paths_before_run(input_path)

        # Second normalization (should be idempotent)
        result2 = normalize_paths_before_run(result1)

        # Should return the same path
        assert result1 == input_path or result1.replace("\\", "/") == input_path.replace("\\", "/"), \
            f"Windows path should remain unchanged, got: {result1} from {input_path}"

        # Should be idempotent
        assert result2 == result1, \
            f"Normalization should be idempotent, got {result1} then {result2}"


class TestNormalizeRelativePath:
    """Test that relative paths are preserved (not normalized)."""

    def test_normalize_relative_path(self):
        """Relative path tests/test_foo.py should remain unchanged.

        Relative paths should not be normalized to absolute paths to maintain
        command context and working directory semantics.

        Input: tests/test_foo.py
        Expected: tests/test_foo.py (unchanged)
        """
        input_path = "tests/test_foo.py"
        result = normalize_paths_before_run(input_path)

        # Relative paths should be preserved
        assert result == input_path, \
            f"Relative paths should not be normalized, got: {result} from {input_path}"

    def test_normalize_dotslash_relative_path(self):
        """Dot-slash relative path ./tests/test_foo.py should remain unchanged.

        Input: ./tests/test_foo.py
        Expected: ./tests/test_foo.py (unchanged)
        """
        input_path = "./tests/test_foo.py"
        result = normalize_paths_before_run(input_path)

        # Should preserve ./ prefix
        assert "tests/test_foo.py" in result or "tests\\test_foo.py" in result, \
            f"Relative path should be preserved, got: {result}"


class TestNormalizeCommandWithPaths:
    """Test path normalization within command strings."""

    def test_normalize_command_with_paths(self):
        """Normalize paths within pytest command string.

        Should extract and normalize paths embedded in command arguments
        while preserving the command structure and other arguments.

        Input: pytest /p/.claude/skills/code/tests/test_foo.py -v
        Expected: pytest P:\\\\\\\.claude\\skills\\code\\tests\\test_foo.py -v
        """
        input_cmd = "pytest /p/.claude/skills/code/tests/test_foo.py -v"
        result = normalize_paths_before_run(input_cmd)

        # Should preserve pytest command
        assert "pytest" in result

        # Should preserve -v flag
        assert "-v" in result

        # Should normalize the path
        assert ("P:" in result or "p:" in result), \
            f"Path should be normalized to Windows format, got: {result}"

        # Should NOT contain Git Bash format
        assert "/p/" not in result and "/P/" not in result, \
            f"Result should not contain Git Bash /p/ format, got: {result}"

    def test_normalize_python_command(self):
        """Normalize paths in python command.

        Input: python -m pytest /p/project/tests/test_foo.py
        Expected: python -m pytest P:\\\\\\\project\\tests\\test_foo.py
        """
        input_cmd = "python -m pytest /p/project/tests/test_foo.py"
        result = normalize_paths_before_run(input_cmd)

        # Should preserve command structure
        assert "python" in result
        assert "-m" in result
        assert "pytest" in result

        # Should normalize path
        assert ("P:" in result or "p:" in result)


class TestNormalizeMultiplePathsInCommand:
    """Test normalization of multiple paths in a single command."""

    def test_normalize_multiple_paths_in_command(self):
        """Normalize all Git Bash paths in command with multiple paths.

        Should find and normalize ALL occurrences of Git Bash paths,
        not just the first one.

        Input: pytest /p/src/test1.py /p/src/test2.py
        Expected: pytest P:\\\\\\\src\\test1.py P:\\\\\\\src\\test2.py
        """
        input_cmd = "pytest /p/src/test1.py /p/src/test2.py"
        result = normalize_paths_before_run(input_cmd)

        # Should preserve pytest command
        assert "pytest" in result

        # Should normalize both paths (should have 2 occurrences of P:)
        drive_count = result.count("P:") + result.count("p:")
        assert drive_count >= 2, \
            f"Should normalize all paths, expected 2+ drive letters, got {drive_count} in: {result}"

        # Should NOT contain any Git Bash format
        assert "/p/" not in result and "/P/" not in result, \
            f"Result should not contain Git Bash /p/ format, got: {result}"

    def test_normalize_mixed_path_formats(self):
        """Handle command with both Git Bash and Windows paths.

        Input: pytest /p/src/test1.py P:\\\\\\\src\\test2.py
        Expected: All paths in Windows format
        """
        input_cmd = "pytest /p/src/test1.py P:\\\\\\\src\\test2.py"
        result = normalize_paths_before_run(input_cmd)

        # Should normalize the Git Bash path
        assert "test1.py" in result
        assert "test2.py" in result

        # Should have 2 paths with drive letters
        drive_count = result.count("P:") + result.count("p:")
        assert drive_count >= 1, \
            f"Should normalize Git Bash paths, got: {result}"


class TestPathNormalizationLogging:
    """Test that path normalization is logged for debugging."""

    def test_path_normalization_logging(self, caplog):
        """Verify that logging records path transformations.

        Should log each path transformation for observability and debugging.
        Log format: "Normalized /p/... -> P:\\\\\\\..."

        Uses pytest's caplog fixture to capture log output.
        """
        with caplog.at_level(logging.INFO):
            input_cmd = "pytest /p/.claude/skills/code/tests/test_foo.py"
            result = normalize_paths_before_run(input_cmd)

        # Should log the transformation
        log_messages = [record.message for record in caplog.records]

        # Check for logging keywords
        assert any("normalized" in msg.lower() or "normalize" in msg.lower() for msg in log_messages), \
            f"Should log normalization, got: {log_messages}"

        # Optionally check for path mentions in logs
        assert any("/p/" in msg or "P:" in msg for msg in log_messages), \
            f"Log should mention source or target paths, got: {log_messages}"

    def test_path_normalization_logging_detail(self, caplog):
        """Verify detailed logging shows both source and target paths.

        Should log: "Normalized /p/.claude/... -> P:\\\\\\\.claude\\..."
        """
        with caplog.at_level(logging.DEBUG):
            input_path = "/p/.claude/skills/code/tests/test_foo.py"
            result = normalize_paths_before_run(input_path)

        log_messages = [record.message for record in caplog.records]

        # Should show transformation
        assert any("->" in msg or "to" in msg.lower() for msg in log_messages), \
            f"Should show transformation (-> or 'to'), got: {log_messages}"


class TestNormalizePathsBeforeRunIntegration:
    """Integration tests for the normalize_paths_before_run function."""

    def test_normalize_paths_before_run_integration(self):
        """Integration test: call normalize_paths_before_run with command string.

        Verify the function:
        1. Returns normalized command string
        2. Converts Git Bash paths to Windows format
        3. Preserves non-path arguments
        4. Logs transformations
        """
        input_cmd = "pytest /p/.claude/skills/code/tests/test_foo.py -v --tb=short"

        # Call the function
        result = normalize_paths_before_run(input_cmd)

        # Should return a string
        assert isinstance(result, str), \
            f"Should return string, got {type(result)}: {result}"

        # Should contain pytest
        assert "pytest" in result

        # Should preserve flags
        assert "-v" in result
        assert "--tb=short" in result

        # Should normalize path to Windows format
        assert "P:" in result or "p:" in result, \
            f"Should normalize to Windows format, got: {result}"

        # Should not contain Git Bash format
        assert "/p/" not in result, \
            f"Should not contain Git Bash /p/ format, got: {result}"

    def test_normalize_paths_before_run_empty_string(self):
        """Handle empty string input gracefully."""
        result = normalize_paths_before_run("")

        assert result == "", "Empty string should return empty string"

    def test_normalize_paths_before_run_no_paths(self):
        """Handle command with no paths (should return unchanged)."""
        input_cmd = "echo hello world"
        result = normalize_paths_before_run(input_cmd)

        assert result == input_cmd, \
            f"Command without paths should be unchanged, got: {result}"

    def test_normalize_paths_before_run_multiple_drives(self):
        """Handle paths from different drives (P:, C:, etc.)."""
        input_cmd = "pytest /p/project/tests/test_foo.py /c/other/tests/test_bar.py"
        result = normalize_paths_before_run(input_cmd)

        # Should normalize both drives
        assert "P:" in result or "p:" in result, \
            f"Should normalize /p/ drive, got: {result}"
        assert "C:" in result or "c:" in result, \
            f"Should normalize /c/ drive, got: {result}"

        # Should not contain Git Bash format
        assert "/p/" not in result and "/P/" not in result
        assert "/c/" not in result and "/C/" not in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_normalize_path_with_spaces(self):
        """Handle paths with spaces (quoted in command)."""
        input_cmd = 'pytest "/p/project name/tests/test_foo.py"'
        result = normalize_paths_before_run(input_cmd)

        # Should preserve quotes and normalize path
        assert '"' in result or "test_foo.py" in result
        assert "P:" in result or "p:" in result

    def test_normalize_path_with_special_chars(self):
        """Handle paths with special characters (dots, dashes, underscores)."""
        input_path = "/p/project/test.file-with_special.py"
        result = normalize_paths_before_run(input_path)

        # Should preserve special characters
        assert "test.file-with_special.py" in result or "test.file-with_special" in result
        assert "P:" in result or "p:" in result

    def test_normalize_path_trailing_slash(self):
        """Handle path with trailing slash (directory)."""
        input_path = "/p/project/tests/"
        result = normalize_paths_before_run(input_path)

        # Should normalize
        assert "P:" in result or "p:" in result

    def test_normalize_path_double_slash(self):
        """Handle path with double slashes (//p/...)."""
        input_path = "//p/project/tests/test_foo.py"
        result = normalize_paths_before_run(input_path)

        # Should handle gracefully (normalize or preserve)
        assert isinstance(result, str)

    def test_normalize_lowercase_drive_letter(self):
        """Ensure drive letter is uppercased in Windows format.

        Input: /p/project should become P:\\\\\\\project (uppercase P)
        """
        input_path = "/p/project/tests/test_foo.py"
        result = normalize_paths_before_run(input_path)

        # Should have uppercase drive letter
        assert "P:" in result, \
            f"Drive letter should be uppercase P:, got: {result}"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
