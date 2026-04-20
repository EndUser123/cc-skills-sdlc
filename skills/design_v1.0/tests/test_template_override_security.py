"""
SEC-002: Template override allowlist validation - VERIFIED FIXED

These tests verify that extract_template_override() properly validates
template values against VALID_TEMPLATES allowlist.

Security Fix: The function now uses two-layer validation:
1. Restrictive regex r"template=([a-zA-Z0-9-]+)" - only alphanumeric + dash
2. Allowlist validation - checks if template in VALID_TEMPLATES

Run with: pytest P:/.claude/skills/arch/tests/test_template_override_security.py -v
"""

import sys
from pathlib import Path

# Add the .claude directory to path for package imports
claude_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(claude_path))

import pytest
from skill.routing import extract_template_override, VALID_TEMPLATES


class TestExtractTemplateOverrideSecurity:
    """
    Tests for SEC-002: Template override without allowlist validation.

    These tests demonstrate that extract_template_override() returns values
    without validating them against VALID_TEMPLATES allowlist.
    """

    def test_extract_template_override_returns_any_value(self):
        """
        Test that extract_template_override() validates against allowlist.

        Given: Query with template=<non-allowlist-value>
        When: extract_template_override() is called
        Then: Returns None (safe default) for invalid templates

        SEC-002 FIX: This test verifies the security fix is in place.
        The function now validates against VALID_TEMPLATES and returns None for invalid values.
        """
        # Regex pattern: r"template=([a-zA-Z0-9-]+)"
        # Only matches alphanumeric + dash (no dots, slashes, etc.)
        non_allowlist_values = [
            "malicious",
            "admin-template",
            "custom-123",
            "XYZ-999",
            "injection-test",
            "exploit-payload",
        ]

        for test_value in non_allowlist_values:
            # Verify the value is NOT in the allowlist
            assert test_value not in VALID_TEMPLATES, (
                f"Test setup error: {test_value} should not be in VALID_TEMPLATES"
            )

            query = f"redesign api template={test_value}"
            result = extract_template_override(query)

            # EXPECTED: Should return None for invalid templates (safe default)
            # ACTUAL: Returns the invalid template value (VULNERABILITY)
            assert result is None or result in VALID_TEMPLATES, (
                f"SECURITY ISSUE: extract_template_override() returned '{result}' "
                f"for invalid template '{test_value}'. Should return None or "
                f"only values from VALID_TEMPLATES {VALID_TEMPLATES}."
            )

    def test_extract_template_override_with_special_chars(self):
        """
        Test that extract_template_override() validates non-allowlist patterns.

        Given: Query with various template patterns
        When: extract_template_override() is called
        Then: Rejects patterns not in VALID_TEMPLATES

        SEC-002 FIX: The function now validates against VALID_TEMPLATES allowlist.
        Uses restrictive regex r"template=([a-zA-Z0-9-]+)" combined with allowlist validation.
        """
        test_cases = [
            ("redesign api template=malicious-123", "malicious-123"),
            ("improve system template=ABC-XYZ-999", "ABC-XYZ-999"),
            ("analyze code template=CustomTemplate", "CustomTemplate"),
            ("refactor module template=x---y", "x---y"),  # Multiple dashes
        ]

        for query, invalid_template in test_cases:
            # Verify these are NOT in the allowlist
            assert invalid_template not in VALID_TEMPLATES, (
                f"Test setup error: {invalid_template} should not be in VALID_TEMPLATES"
            )

            result = extract_template_override(query)

            # EXPECTED: Should return None for invalid templates (safe default)
            # ACTUAL: Returns the invalid template value (VULNERABILITY)
            assert result is None or result in VALID_TEMPLATES, (
                f"SECURITY ISSUE: extract_template_override() returned '{result}' "
                f"for invalid template '{invalid_template}'. Should return None or "
                f"only values from VALID_TEMPLATES {VALID_TEMPLATES}."
            )

    def test_extract_template_override_should_validate_against_allowlist(self):
        """
        Test that extract_template_override() validates against allowlist.

        Given: Query with template=<non-allowlist-value>
        When: extract_template_override() is called
        Then: Returns None for invalid templates (safe default)

        SEC-002 FIX: The function now performs proper allowlist validation.
        Returns None for invalid templates, only values from VALID_TEMPLATES.
        """
        # Pick a value that is clearly NOT in VALID_TEMPLATES
        invalid_template = "clearly-invalid-template-name-123"

        # Verify it's not in the allowlist (test sanity check)
        assert invalid_template not in VALID_TEMPLATES, (
            f"Test setup error: {invalid_template} should not be in VALID_TEMPLATES"
        )

        query = f"redesign api template={invalid_template}"
        result = extract_template_override(query)

        # EXPECTED BEHAVIOR: Returns None for invalid templates (safe default)
        # SEC-002 FIX: This assertion now PASSES - vulnerability is fixed
        assert result is None or result in VALID_TEMPLATES, (
            f"SECURITY ISSUE: extract_template_override() returned '{result}' "
            f"which is NOT in VALID_TEMPLATES {VALID_TEMPLATES}. "
            f"Function should validate templates before returning them."
        )
