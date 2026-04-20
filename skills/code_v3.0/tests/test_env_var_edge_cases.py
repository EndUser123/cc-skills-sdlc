#!/usr/bin/env python3
"""Tests for environment variable edge case validation - GREEN phase.

This module tests environment variable validation for SKILL_FIRST_INTENT_TTL_SECONDS:
- Negative TTL values should use default 90s
- Zero TTL should use default 90s
- Non-numeric TTL should use default 90s
- Empty string should be treated as unset (use default 90s)
- Very large TTL (999999) should be accepted with warning
"""

import logging
import sys
from pathlib import Path

import pytest

# Add hooks directory to path for imports
hooks_dir = Path(__file__).parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(hooks_dir))

# Import the validation function from PreToolUse.py
# We need to test the actual implementation
import importlib.util

# Load PreToolUse module to test validation function
pretooluse_path = Path(__file__).parent.parent.parent.parent / "hooks" / "PreToolUse.py"
spec = importlib.util.spec_from_file_location("PreToolUse", pretooluse_path)
pretooluse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pretooluse)

_validate_intent_ttl = pretooluse._validate_intent_ttl


class TestTTLNegativeValue:
    """Test negative TTL values are rejected and use default 90s."""

    def test_negative_ttl_uses_default_90s(self):
        """Verify negative TTL falls back to default 90s.

        Tests that:
        - SKILL_FIRST_INTENT_TTL_SECONDS=-10 is rejected as invalid
        - Default TTL of 90 seconds is used instead
        - Implementation validates and rejects negative values
        """
        # Negative TTL should return default 90
        result = _validate_intent_ttl("-10")
        assert result == 90, f"Expected 90, got {result}"

    def test_negative_10_ttl_rejected(self):
        """Verify TTL=-10 is rejected."""
        result = _validate_intent_ttl("-10")
        assert result == 90, f"Expected 90 (default), got {result}"


class TestTTLZeroValue:
    """Test zero TTL values are rejected and use default 90s."""

    def test_zero_ttl_uses_default_90s(self):
        """Verify zero TTL falls back to default 90s.

        Tests that:
        - SKILL_FIRST_INTENT_TTL_SECONDS=0 is rejected as invalid
        - Default TTL of 90 seconds is used instead
        - Zero is not a valid TTL (must be positive)
        """
        result = _validate_intent_ttl("0")
        assert result == 90, f"Expected 90 (default), got {result}"


class TestTTLNonNumeric:
    """Test non-numeric TTL values are rejected and use default 90s."""

    def test_non_numeric_ttl_uses_default_90s(self):
        """Verify non-numeric TTL falls back to default 90s.

        Tests that:
        - SKILL_FIRST_INTENT_TTL_SECONDS="invalid" is rejected
        - Default TTL of 90 seconds is used instead
        - String values cannot be parsed as integers
        """
        result = _validate_intent_ttl("invalid")
        assert result == 90, f"Expected 90 (default), got {result}"

    def test_non_numeric_with_digits_uses_default(self):
        """Verify mixed alphanumeric values are rejected."""
        result = _validate_intent_ttl("90abc")
        assert result == 90, f"Expected 90 (default), got {result}"


class TTLEmptyString:
    """Test empty string is treated as unset and uses default 90s."""

    def test_empty_string_uses_default_90s(self):
        """Verify empty string falls back to default 90s.

        Tests that:
        - SKILL_FIRST_INTENT_TTL_SECONDS="" is treated as unset
        - Empty string means "not set", same as missing env var
        - Default TTL of 90 seconds is used
        """
        result = _validate_intent_ttl("")
        assert result == 90, f"Expected 90 (default), got {result}"

    def test_empty_string_treated_same_as_unset(self):
        """Verify empty string behaves same as missing env var."""
        # Empty string
        result_empty = _validate_intent_ttl("")
        # None (missing env var)
        result_none = _validate_intent_ttl(None)

        assert result_empty == result_none == 90, "Empty string and None should both return 90"


class TestTVeryLargeTTL:
    """Test very large TTL values are accepted with warning."""

    def test_very_large_ttl_accepted_with_warning(self, caplog):
        """Verify very large TTL (999999) is accepted but logs warning.

        Tests that:
        - SKILL_FIRST_INTENT_TTL_SECONDS=999999 is accepted
        - Warning is logged about unusually large TTL
        - Large TTL values don't crash the system
        - Warning message indicates potential issues with long TTL
        """
        with caplog.at_level(logging.WARNING):
            result = _validate_intent_ttl("999999")

        # Value should be accepted (not rejected)
        assert result == 999999, f"Expected 999999 (accepted), got {result}"

        # Warning should be logged
        assert len(caplog.records) > 0, "Expected warning log for large TTL"
        log_message = caplog.text
        assert "unusually large" in log_message.lower(), "Warning should mention 'unusually large'"
        assert (
            "stale intent files" in log_message.lower()
        ), "Warning should mention stale data concerns"

    def test_large_ttl_warning_message_content(self, caplog):
        """Verify warning message contains useful information."""
        with caplog.at_level(logging.WARNING):
            result = _validate_intent_ttl("100000")  # > 1 day

        # Value should be accepted
        assert result == 100000, f"Expected 100000 (accepted), got {result}"

        # Warning should mention:
        # - Unusually large TTL value
        # - Potential stale data concerns
        # - Recommendation to use shorter TTL
        assert len(caplog.records) > 0, "Expected warning log"
        log_message = caplog.text
        assert "unusually large" in log_message.lower(), "Warning should mention 'unusually large'"
        assert (
            "stale intent files" in log_message.lower()
        ), "Warning should mention stale data concerns"


class TestTTLDefaultBehavior:
    """Test default TTL behavior when env var is unset."""

    def test_unset_env_var_uses_default_90s(self):
        """Verify missing env var uses default 90 seconds.

        Tests that:
        - SKILL_FIRST_INTENT_TTL_SECONDS not set uses default
        - Default TTL of 90 seconds is used
        - No errors or warnings for unset env var
        """
        # None represents missing env var
        result = _validate_intent_ttl(None)
        assert result == 90, f"Expected 90 (default), got {result}"


class TestTTLValidationIntegration:
    """Integration tests for TTL validation with actual intent lifecycle."""

    def test_valid_ttl_60_works_correctly(self):
        """Verify valid TTL=60 is accepted and used."""
        result = _validate_intent_ttl("60")
        assert result == 60, f"Expected 60, got {result}"

    def test_valid_ttl_120_works_correctly(self):
        """Verify valid TTL=120 is accepted and used."""
        result = _validate_intent_ttl("120")
        assert result == 120, f"Expected 120, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
