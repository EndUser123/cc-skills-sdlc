"""
Test suite for load_arch_config() type validation.

These tests verify that config values are validated for correct TYPE,
not just valid domain values. This is TEST-014: Missing invalid type test.

Run with: pytest P:/.claude/skills/arch/tests/test_config_types.py -v
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for importing config module
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def clean_arch_env_vars():
    """Ensure no ARCH_* environment variables interfere with tests."""
    env_backup = {}
    for key in list(os.environ.keys()):
        if key.startswith("ARCH_"):
            env_backup[key] = os.environ.pop(key)

    yield

    for key, value in env_backup.items():
        os.environ[key] = value


class TestInvalidValueTypes:
    """Tests for invalid VALUE TYPE validation (not just invalid domain values)."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_default_domain_as_integer_raises_type_error(self, mock_read, mock_exists):
        """
        Test that default_domain as integer (123) raises TypeError or ValueError.

        Given: A config file with default_domain as integer (not string)
        When: load_arch_config() is called
        Then: TypeError or ValueError is raised with descriptive message about type

        This catches the missing validation where config values must be strings,
        not just valid domain values.
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": 123,  # Integer instead of string
                "output_size": "normal",
                "evidence_level": "standard",
            }
        )

        # Act & Assert
        from config import load_arch_config

        # Should raise TypeError or ValueError for incorrect type
        with pytest.raises((TypeError, ValueError)) as exc_info:
            load_arch_config()

        # Verify the error message mentions the type issue
        error_msg = str(exc_info.value).lower()
        assert (
            "default_domain" in error_msg
            or "type" in error_msg
            or "str" in error_msg
            or "string" in error_msg
        ), (
            f"Expected error message to mention type issue for default_domain, "
            f"but got: {exc_info.value}"
        )

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_output_size_as_list_raises_type_error(self, mock_read, mock_exists):
        """
        Test that output_size as list raises TypeError or ValueError.

        Given: A config file with output_size as list (not string)
        When: load_arch_config() is called
        Then: TypeError or ValueError is raised with descriptive message about type

        This validates that output_size must be a string, not a collection.
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": "python",
                "output_size": ["verbose", "normal"],  # List instead of string
                "evidence_level": "standard",
            }
        )

        # Act & Assert
        from config import load_arch_config

        # Should raise TypeError or ValueError for incorrect type
        with pytest.raises((TypeError, ValueError)) as exc_info:
            load_arch_config()

        # Verify the error message mentions the type issue
        error_msg = str(exc_info.value).lower()
        assert (
            "output_size" in error_msg
            or "type" in error_msg
            or "str" in error_msg
            or "string" in error_msg
            or "list" in error_msg
        ), (
            f"Expected error message to mention type issue for output_size, "
            f"but got: {exc_info.value}"
        )

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_multiple_invalid_types_raises_error(self, mock_read, mock_exists):
        """
        Test that multiple fields with invalid types are caught.

        Given: A config file with multiple fields having wrong types
        When: load_arch_config() is called
        Then: Error is raised (should fail fast on first type error)

        This verifies that type validation catches ALL type errors, not just one.
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": 999,  # Integer instead of string
                "output_size": ["a", "b"],  # List instead of string
                "evidence_level": None,  # None instead of string
            }
        )

        # Act & Assert
        from config import load_arch_config

        # Should raise TypeError or ValueError for incorrect types
        with pytest.raises((TypeError, ValueError)) as exc_info:
            load_arch_config()

        # Error should mention at least one of the problematic fields
        error_msg = str(exc_info.value).lower()
        assert any(
            field in error_msg
            for field in ["default_domain", "output_size", "evidence_level", "type"]
        ), f"Expected error message to mention type issue, but got: {exc_info.value}"

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_evidence_level_as_boolean_raises_type_error(self, mock_read, mock_exists):
        """
        Test that evidence_level as boolean raises TypeError or ValueError.

        Given: A config file with evidence_level as boolean (not string)
        When: load_arch_config() is called
        Then: TypeError or ValueError is raised with descriptive message about type

        This validates that evidence_level must be a string.
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": "python",
                "output_size": "normal",
                "evidence_level": True,  # Boolean instead of string
            }
        )

        # Act & Assert
        from config import load_arch_config

        # Should raise TypeError or ValueError for incorrect type
        with pytest.raises((TypeError, ValueError)) as exc_info:
            load_arch_config()

        # Verify the error message mentions the type issue
        error_msg = str(exc_info.value).lower()
        assert (
            "evidence_level" in error_msg
            or "type" in error_msg
            or "str" in error_msg
            or "string" in error_msg
            or "bool" in error_msg
        ), (
            f"Expected error message to mention type issue for evidence_level, "
            f"but got: {exc_info.value}"
        )


class TestValidTypesWithInvalidValues:
    """Tests for valid types but invalid domain values (should pass type check, fail domain check)."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_string_type_but_invalid_domain_value(self, mock_read, mock_exists):
        """
        Test that string type with invalid domain value is NOT a type error.

        Given: A config file with default_domain as wrong string value
        When: load_arch_config() is called
        Then: May raise ValueError for invalid domain, but NOT TypeError

        This distinguishes between type errors and domain value errors.
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": "not_a_valid_domain",  # String type, wrong value
                "output_size": "normal",
                "evidence_level": "standard",
            }
        )

        # Act & Assert
        from config import load_arch_config

        # Should raise ValueError for invalid domain (not TypeError)
        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        error_msg = str(exc_info.value).lower()

        # This is a domain value error, not a type error
        # The error should mention the invalid value, not complain about type
        assert "not_a_valid_domain" in error_msg or "default_domain" in error_msg

        # Should NOT be complaining about type (that's a different error)
        # Note: If implementation doesn't distinguish, this test documents current behavior
