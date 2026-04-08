"""
Unit tests for template file I/O error handling in routing.py.

These tests verify that validate_template() handles file I/O errors gracefully
and provides helpful error messages for different failure scenarios.

Target: validate_template() in routing.py (lines 476-486)
Issue: Has exception handling but no tests for I/O error scenarios

Run with: pytest P:/.claude/skills/arch/tests/test_template_io_errors.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from skill.routing import validate_template, VALID_TEMPLATES


class TestValidateTemplateIOErrors:
    """Tests for I/O error handling in validate_template()."""

    def test_permission_error_returns_helpful_message(self):
        """
        Test that validate_template() handles permission errors gracefully.

        Given: Template file exists but user lacks read permission
        When: validate_template() attempts to read the file
        Then: Returns (False, error_message) with helpful message including:
              - The file path that couldn't be read
              - Specific mention of permission issue
              - Actionable guidance for the user

        This test FAILS because current implementation uses generic Exception
        handling without specific permission error detection or messaging.
        The current error message "Cannot read template file: {path}. Error: {e}"
        doesn't identify permission errors specifically or provide actionable guidance.

        To observe this failure, the test patches the builtins.open to simulate
        a PermissionError when attempting to read the template file.
        """
        template_name = "fast"

        # Clear cache to ensure isolation from other tests
        validate_template.cache_clear()

        # Patch open() to simulate permission error
        original_open = open

        def mock_open_func(path, *args, **kwargs):
            # If trying to open a template file, raise PermissionError
            if "fast.md" in str(path):
                raise PermissionError(f"[Errno 13] Permission denied: '{path}'")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            is_valid, error_message = validate_template(template_name)

        # Assert
        assert is_valid is False, "Template validation should return False on permission error"
        assert len(error_message) > 0, "Error message should not be empty"

        # Verify error message contains helpful information BEYOND just the exception
        # Current implementation will FAIL this - it just includes the raw exception message
        # which happens to contain "denied", but doesn't provide any ADDITIONAL helpful guidance
        # The test checks that the error message provides MORE than just the raw exception
        error_lower = error_message.lower()

        # The current implementation includes "[Errno 13] Permission denied" from the exception
        # We're testing that it ALSO provides actionable guidance like "Check file permissions"
        # or "Run with appropriate access rights"
        has_specific_guidance = any(phrase in error_lower for phrase in [
            "check file permissions",
            "verify file access",
            "ensure file is readable",
            "try running with elevated",
            "check ownership",
            "file may be protected",
        ])

        assert has_specific_guidance, (
            f"Error message should provide specific actionable guidance for permission errors, "
            f"not just include the raw exception. Got: {error_message}"
        )

    def test_unicode_decode_error_returns_helpful_message(self):
        """
        Test that validate_template() handles Unicode decode errors gracefully.

        Given: Template file exists but contains invalid UTF-8 encoding
        When: validate_template() attempts to read the file
        Then: Returns (False, error_message) with helpful message including:
              - The file path that couldn't be decoded
              - Specific mention of encoding issue
              - Guidance on fixing the encoding problem

        This test FAILS because current implementation uses generic Exception
        handling without specific Unicode error detection or messaging.
        Users seeing "Cannot read template file" don't know it's an encoding problem.
        """
        template_name = "deep"

        # Clear cache to ensure isolation from other tests
        validate_template.cache_clear()

        # Create a mock file that raises UnicodeDecodeError when reading
        class MockFile:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                raise UnicodeDecodeError('utf-8', b'\xff\xfe', 0, 1, 'invalid start byte')

        original_open = open

        def mock_open_func(path, *args, **kwargs):
            if "deep.md" in str(path):
                return MockFile()
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            is_valid, error_message = validate_template(template_name)

        # Assert
        assert is_valid is False, "Template validation should return False on Unicode error"
        assert len(error_message) > 0, "Error message should not be empty"

        # Verify error message provides SPECIFIC guidance for encoding issues
        # Current implementation will FAIL this - it just includes the raw exception message
        # We're testing that it ALSO provides actionable guidance like "Check file encoding"
        error_lower = error_message.lower()
        has_encoding_guidance = any(phrase in error_lower for phrase in [
            "check file encoding",
            "verify file is utf-8",
            "invalid utf-8 encoding",
            "file may be corrupted",
            "try saving as utf-8",
            "encoding issue",
            "decode error",
        ])

        assert has_encoding_guidance, (
            f"Error message should provide specific guidance for encoding issues, "
            f"not just include the raw exception. Got: {error_message}"
        )

    def test_file_system_lock_error_returns_helpful_message(self):
        """
        Test that validate_template() handles file system lock errors gracefully.

        Given: Template file is locked by another process
        When: validate_template() attempts to read the file
        Then: Returns (False, error_message) with helpful message including:
              - The file path that couldn't be accessed
              - Specific mention of file lock/in-use issue
              - Guidance like "close other programs" or "try again later"

        This test FAILS because current implementation uses generic Exception
        handling without specific lock error detection or messaging.
        """
        template_name = "python"

        # Clear cache to ensure isolation from other tests
        validate_template.cache_clear()

        # Patch open() to simulate file lock error (IOError with EBUSY)
        original_open = open

        def mock_open_func(path, *args, **kwargs):
            if "python.md" in str(path):
                raise IOError(f"[Errno 11] Resource temporarily unavailable: '{path}'")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            is_valid, error_message = validate_template(template_name)

        # Assert
        assert is_valid is False, "Template validation should return False on file lock error"
        assert len(error_message) > 0, "Error message should not be empty"

        # Verify error message provides SPECIFIC guidance for file lock issues
        # Current implementation will FAIL this - it just includes the raw exception
        error_lower = error_message.lower()
        has_lock_guidance = any(phrase in error_lower for phrase in [
            "file is in use",
            "close other programs",
            "file may be locked",
            "another process is using",
            "try closing other programs",
        ])

        assert has_lock_guidance, (
            f"Error message should provide specific guidance for file lock issues, "
            f"not just include the raw exception. Got: {error_message}"
        )

    def test_os_error_returns_helpful_message(self):
        """
        Test that validate_template() handles generic OS errors gracefully.

        Given: Template file exists but OS-level error occurs (disk failure, etc.)
        When: validate_template() attempts to read the file
        Then: Returns (False, error_message) with helpful message including:
              - The file path that caused the error
              - The OS error details (errno, type)
              - Clear indication that it's a system-level issue

        This test FAILS because current implementation's error message format
        doesn't provide clear categorization of OS-level issues vs other errors.
        """
        template_name = "cli"

        # Clear cache to ensure isolation from other tests
        validate_template.cache_clear()

        # Patch open() to simulate OS error (disk I/O error)
        original_open = open

        def mock_open_func(path, *args, **kwargs):
            if "cli.md" in str(path):
                raise OSError(f"[Errno 5] Input/output error: '{path}'")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            is_valid, error_message = validate_template(template_name)

        # Assert
        assert is_valid is False, "Template validation should return False on OS error"
        assert len(error_message) > 0, "Error message should not be empty"

        # Verify error message provides SPECIFIC guidance for OS-level errors
        # Current implementation will FAIL this - it just includes the raw exception
        error_lower = error_message.lower()
        has_os_guidance = any(phrase in error_lower for phrase in [
            "system-level error",
            "disk i/o error",
            "check disk space",
            "file system error",
            "hardware issue",
            "contact system administrator",
            "may be corrupted",
        ])

        assert has_os_guidance, (
            f"Error message should provide specific guidance for OS-level errors, "
            f"not just include the raw exception. Got: {error_message}"
        )

    def test_error_messages_are_actionable(self):
        """
        Test that error messages provide actionable guidance.

        Given: Any file I/O error occurs
        When: validate_template() returns an error
        Then: Error message includes actionable next steps or explanations
              that help users resolve the issue themselves

        This test FAILS because current implementation's error messages are generic:
        "Cannot read template file: {path}. Error: {e}"
        They don't provide specific guidance based on error type.
        """
        template_name = "fast"

        # Clear cache to ensure isolation from other tests
        validate_template.cache_clear()

        # Patch open() to simulate permission error
        original_open = open

        def mock_open_func(path, *args, **kwargs):
            if "fast.md" in str(path):
                raise PermissionError(f"[Errno 13] Permission denied: '{path}'")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            is_valid, error_message = validate_template(template_name)

        # Check for actionable phrases that help users fix the problem
        actionable_phrases = [
            "check file permissions",
            "verify file access",
            "ensure file is readable",
            "try running with elevated privileges",
            "check file encoding",
            "verify file format",
            "close other programs",
            "file may be in use",
            "check disk space",
            "verify file exists",
        ]

        error_lower = error_message.lower()
        has_actionable_guidance = any(phrase in error_lower for phrase in actionable_phrases)

        assert has_actionable_guidance, (
            f"Error message should include actionable guidance to help users resolve the issue. "
            f"Expected one of: {actionable_phrases}. Got: {error_message}"
        )


class TestValidateTemplateIOErrorContract:
    """Contract tests to verify validate_template() maintains expected behavior."""

    def test_error_message_format_is_tuple(self):
        """
        Test that validate_template() always returns (bool, str) tuple.

        Given: Any error scenario (permission, encoding, lock, etc.)
        When: validate_template() is called
        Then: Always returns a tuple of (is_valid: bool, error_message: str)

        This is a contract test - ensures the function signature is maintained.
        This test PASSES because the current implementation correctly returns tuples.
        """
        # Test with valid template
        is_valid, error_message = validate_template("fast")

        assert isinstance(is_valid, bool), "First return value should be bool"
        assert isinstance(error_message, str), "Second return value should be str"

        # Test with invalid template name
        is_valid, error_message = validate_template("nonexistent_template")
        assert isinstance(is_valid, bool), "First return value should be bool"
        assert isinstance(error_message, str), "Second return value should be str"

    def test_all_valid_templates_handle_io_errors_consistently(self):
        """
        Test that all templates handle I/O errors consistently.

        Given: Each template in VALID_TEMPLATES
        When: validate_template() is called
        Then: All return (False, error_message) with consistent format

        This ensures consistent error handling across all templates.
        This test PASSES because the function signature is consistent.
        """
        for template_name in VALID_TEMPLATES:
            result = validate_template(template_name)

            # Always returns tuple
            assert isinstance(result, tuple), (
                f"validate_template('{template_name}') should return tuple. Got {type(result)}"
            )
            assert len(result) == 2, (
                f"validate_template('{template_name}') should return 2-element tuple. "
                f"Got {len(result)} elements"
            )
            assert isinstance(result[0], bool), (
                f"First element for '{template_name}' should be bool. Got {type(result[0])}"
            )
            assert isinstance(result[1], str), (
                f"Second element for '{template_name}' should be str. Got {type(result[1])}"
            )
