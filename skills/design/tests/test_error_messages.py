"""
Unit tests for error message quality in architecture configuration module.

These tests verify that error messages are:
- Helpful and actionable
- Contain sufficient context for users to fix the issue
- Include lists of valid options where applicable
- User-friendly and not cryptic

Run with: pytest P:/.claude/skills/arch/tests/test_error_messages.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLoadArchConfigErrorMessages:
    """Tests for error message quality in load_arch_config()."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_invalid_domain_error_message_contains_fix_guidance(
        self, mock_read, mock_exists
    ):
        """
        Test that ValueError for invalid domain includes actionable fix guidance.

        Given: A config file with an invalid domain value
        When: load_arch_config() is called
        Then: ValueError message should include:
              - The invalid value that was provided
              - A list of all valid domain options
              - Clear guidance on how to fix the issue (actionable)

        This test FAILS because the current error message in config.py:
        "Invalid default_domain: 'ruby'. Valid domains are: cli, data-pipeline,
        precedent, python"

        Does NOT include explicit fix guidance like "Use one of:" or "Change to:"
        or "Did you mean?" - making it less actionable for users.
        """
        # Arrange
        mock_exists.return_value = True
        invalid_domain = "ruby"
        mock_read.return_value = json.dumps(
            {
                "default_domain": invalid_domain,
                "output_size": "normal",
                "evidence_level": "standard",
            }
        )

        # Act & Assert
        from config import load_arch_config, VALID_DOMAINS

        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        error_message = str(exc_info.value)

        # Verify error message contains the invalid domain value
        assert invalid_domain in error_message, (
            f"Error message should contain the invalid domain '{invalid_domain}'. "
            f"Got: {error_message}"
        )

        # Verify error message contains list of valid domains
        # This is the KEY assertion missing from test_config_validation.py
        for valid_domain in VALID_DOMAINS:
            assert valid_domain in error_message, (
                f"Error message should list valid domain '{valid_domain}' "
                f"to help users fix the issue. Got: {error_message}"
            )

        # NEW REQUIREMENT: Error message should include explicit fix guidance
        # This will FAIL because current implementation doesn't include phrases like:
        # "Use one of:", "Change to:", "Did you mean?", "Fix by:"
        fix_guidance_phrases = [
            "use one of",
            "change to",
            "did you mean",
            "fix by",
            "try one of",
            "please use",
            "must be one of",
        ]
        has_fix_guidance = any(
            phrase in error_message.lower() for phrase in fix_guidance_phrases
        )
        assert has_fix_guidance, (
            f"Error message should include explicit fix guidance like "
            f"'Use one of:', 'Change to:', 'Did you mean?' to make it actionable. "
            f"Got: {error_message}"
        )

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_invalid_domain_error_message_is_actionable(self, mock_read, mock_exists):
        """
        Test that ValueError for invalid domain provides actionable guidance.

        Given: A config file with an invalid domain value
        When: load_arch_config() is called
        Then: Error message should enable users to fix the issue without
              additional research (actionable).

        This test FAILS because the current error message shows valid domains
        but doesn't help the user identify which domain to use based on
        common misspellings or similar-sounding names (no fuzzy matching).
        """
        # Arrange
        mock_exists.return_value = True
        invalid_domain = "javascrip"  # Misspelled, close to nothing in valid list
        mock_read.return_value = json.dumps({"default_domain": invalid_domain})

        # Act & Assert
        from config import load_arch_config

        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        error_message = str(exc_info.value)

        # Error should show the invalid value (what the user provided)
        assert invalid_domain in error_message, (
            f"Error message must show the invalid value to help user identify mistake. "
            f"Got: {error_message}"
        )

        # Error should show valid alternatives (what the user SHOULD use)
        assert (
            "valid" in error_message.lower()
            or "allowed" in error_message.lower()
            or "expected" in error_message.lower()
        ), (
            f"Error message must indicate valid/allowed/expected values. "
            f"Got: {error_message}"
        )

        # NEW REQUIREMENT: Error should include "Did you mean?" suggestion
        # This will FAIL because current implementation doesn't do fuzzy matching
        # or suggest similar domain names when the user makes a typo
        assert (
            "did you mean" in error_message.lower()
            or "suggestion" in error_message.lower()
        ), (
            f"Error message should include 'Did you mean?' suggestions for typos. "
            f"Got: {error_message}"
        )

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_missing_required_field_error_is_specific(self, mock_read, mock_exists):
        """
        Test that ValueError for missing required field is specific.

        Given: A config file missing required field
        When: load_arch_config() is called
        Then: Error message should specify which field is missing AND
              provide guidance on how to fix it.

        This test FAILS because the current error message shows which
        field is missing but doesn't provide the fix (e.g., an example
        of a valid value or where to find documentation).
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                # Missing: default_domain (required field)
                "output_size": "normal",
                "evidence_level": "standard",
            }
        )

        # Act & Assert
        from config import load_arch_config

        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        error_message = str(exc_info.value)

        # Error should specify which field is missing
        assert "default_domain" in error_message.lower(), (
            f"Error message should specify which field is missing. "
            f"Expected 'default_domain' in message. Got: {error_message}"
        )

        # Error should indicate it's required
        assert (
            "required" in error_message.lower()
            or "missing" in error_message.lower()
            or "must" in error_message.lower()
        ), (
            f"Error message should indicate the field is required/missing. "
            f"Got: {error_message}"
        )

        # NEW REQUIREMENT: Error should include example or documentation reference
        # This will FAIL because current implementation doesn't include examples
        has_example = (
            "example" in error_message.lower()
            or "e.g." in error_message.lower()
            or "see " in error_message.lower()
            or "documentation" in error_message.lower()
        )
        assert has_example, (
            f"Error message should include an example value or documentation "
            f"reference to help users fix the missing field. "
            f"Got: {error_message}"
        )
