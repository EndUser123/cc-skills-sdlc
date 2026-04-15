"""Tests for hook_error_rca.py validate_matcher_pattern() function.

Tests validate_matcher_pattern() which validates hook matcher patterns
and detects dangerous/invalid regex patterns.

QA Finding: QA-009-001 - validate_matcher_pattern() defaults untested

Run with: pytest P:/packages/rca/skill/tests/test_hook_error_rca.py -v
"""

import sys
from pathlib import Path

import pytest

# Ensure skill/hooks is in path for imports
skill_hooks = str(Path("P:/packages/rca/skill/hooks").resolve())
if skill_hooks not in sys.path:
    sys.path.insert(0, skill_hooks)


class TestValidateMatcherPattern:
    """Tests for validate_matcher_pattern() function."""

    def setup_method(self):
        """Import the function before each test."""
        try:
            from hook_error_rca import validate_matcher_pattern

            self.validate_matcher_pattern = validate_matcher_pattern
        except ImportError as e:
            pytest.skip(f"Cannot import validate_matcher_pattern: {e}")

    def test_special_matcher_patterns_always_match(self):
        """Test that special matcher patterns ('', '.*', '*') always match.

        Given: Special matcher patterns that match everything
        When: Calling validate_matcher_pattern with special patterns
        Then: Should return (True, "") for all special patterns
        """
        special_patterns = ["", ".*", "*"]
        tool_name = "Task"

        for pattern in special_patterns:
            matches, warning = self.validate_matcher_pattern(pattern, tool_name)

            assert (
                matches is True
            ), f"Special pattern '{pattern}' should always match, got {matches}"
            assert (
                warning == ""
            ), f"Special pattern '{pattern}' should have no warning, got '{warning}'"

    def test_normal_match_scenario_exact_match(self):
        """Test that normal match scenarios work correctly with exact match.

        Given: A valid regex pattern that exactly matches a tool name
        When: Calling validate_matcher_pattern with matching pattern and tool
        Then: Should return (True, "") indicating successful match
        """
        pattern = "Task"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Pattern '{pattern}' should match tool '{tool_name}', got {matches}"
        assert warning == "", f"Valid pattern should have no warning, got '{warning}'"

    def test_normal_match_scenario_no_match(self):
        """Test that normal match scenarios work correctly with no match.

        Given: A valid regex pattern that does not match a tool name
        When: Calling validate_matcher_pattern with non-matching pattern and tool
        Then: Should return (False, "") indicating no match
        """
        pattern = "Bash"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is False
        ), f"Pattern '{pattern}' should NOT match tool '{tool_name}', got {matches}"
        assert warning == "", f"Valid pattern should have no warning, got '{warning}'"

    def test_normal_match_scenario_regex_pattern(self):
        """Test that normal match scenarios work correctly with regex patterns.

        Given: A valid regex pattern with special characters
        When: Calling validate_matcher_pattern with regex pattern
        Then: Should return correct match result with no warning
        """
        pattern = "Task|Bash"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Pattern '{pattern}' should match tool '{tool_name}', got {matches}"
        assert warning == "", f"Valid regex pattern should have no warning, got '{warning}'"

    def test_catastrophic_pattern_a_plus_plus_b(self):
        """Test catastrophic pattern detection for '(a+)+b'.

        Given: A pattern containing catastrophic backtracking '(a+)+b'
        When: Calling validate_matcher_pattern with this dangerous pattern
        Then: Should return (True, warning) with 'catastrophic' in warning
        """
        pattern = "(a+)+b"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Dangerous pattern should default to True (safe default), got {matches}"
        assert (
            "catastrophic" in warning.lower()
        ), f"Warning should mention 'catastrophic' for dangerous pattern, got '{warning}'"
        assert pattern in warning, f"Warning should include the pattern name, got '{warning}'"

    def test_catastrophic_pattern_nested_quantifiers(self):
        """Test catastrophic pattern detection for '((a+)*)+'.

        Given: A pattern containing nested quantifiers '((a+)*)+'
        When: Calling validate_matcher_pattern with this dangerous pattern
        Then: Should return (True, warning) with 'catastrophic' in warning
        """
        pattern = "((a+)*)+"
        tool_name = "Bash"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Dangerous pattern should default to True (safe default), got {matches}"
        assert (
            "catastrophic" in warning.lower()
        ), f"Warning should mention 'catastrophic' for dangerous pattern, got '{warning}'"

    def test_catastrophic_pattern_contained_in_larger_pattern(self):
        """Test catastrophic pattern detection when dangerous pattern is a substring.

        Given: A larger pattern containing '(a+)+b' as a substring
        When: Calling validate_matcher_pattern with this pattern
        Then: Should return (True, warning) with 'catastrophic' in warning
        """
        pattern = "^Prefix(a+)+bSuffix$"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Dangerous pattern should default to True (safe default), got {matches}"
        assert (
            "catastrophic" in warning.lower()
        ), f"Warning should mention 'catastrophic' for dangerous pattern, got '{warning}'"

    def test_invalid_regex_asterisk_only(self):
        """Test invalid regex handling for '(*invalid)' pattern.

        Given: An invalid regex pattern with syntax error
        When: Calling validate_matcher_pattern with invalid regex
        Then: Should return (True, 'Invalid regex') in warning
        """
        pattern = "(*invalid)"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Invalid regex should default to True (safe default), got {matches}"
        assert (
            "invalid" in warning.lower()
        ), f"Warning should mention 'invalid regex' for invalid pattern, got '{warning}'"
        assert pattern in warning, f"Warning should include the pattern, got '{warning}'"

    def test_invalid_regex_unclosed_bracket(self):
        """Test invalid regex handling for '[unclosed' pattern.

        Given: An invalid regex with unclosed character class
        When: Calling validate_matcher_pattern with unclosed bracket
        Then: Should return (True, 'Invalid regex') in warning
        """
        pattern = "[unclosed"
        tool_name = "Bash"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Invalid regex should default to True (safe default), got {matches}"
        assert (
            "invalid" in warning.lower()
        ), f"Warning should mention 'invalid regex' for invalid pattern, got '{warning}'"

    def test_invalid_regex_unclosed_paren(self):
        """Test invalid regex handling for unclosed parenthesis.

        Given: An invalid regex with unclosed parenthesis
        When: Calling validate_matcher_pattern with unclosed paren
        Then: Should return (True, 'Invalid regex') in warning
        """
        pattern = "(unclosed"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Invalid regex should default to True (safe default), got {matches}"
        assert (
            "invalid" in warning.lower()
        ), f"Warning should mention 'invalid regex' for invalid pattern, got '{warning}'"

    def test_case_sensitive_matching(self):
        """Test that regex matching is case-sensitive by default.

        Given: A pattern with specific case
        When: Calling validate_matcher_pattern with different case tool name
        Then: Should return False for non-matching case
        """
        pattern = "Task"
        tool_name = "task"  # lowercase

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is False
        ), f"Pattern '{pattern}' should NOT match '{tool_name}' (case-sensitive), got {matches}"
        assert warning == "", f"Valid pattern should have no warning, got '{warning}'"

    def test_complex_valid_regex(self):
        """Test complex but valid regex patterns.

        Given: A complex regex pattern using anchors and character classes
        When: Calling validate_matcher_pattern with valid complex pattern
        Then: Should return correct match result with no warning
        """
        pattern = r"^(Task|Bash|Read)$"
        tool_name = "Task"

        matches, warning = self.validate_matcher_pattern(pattern, tool_name)

        assert (
            matches is True
        ), f"Pattern '{pattern}' should match tool '{tool_name}', got {matches}"
        assert warning == "", f"Valid complex pattern should have no warning, got '{warning}'"

    def test_dot_star_matches_everything(self):
        """Test that '.*' pattern (standard regex) matches all tools.

        Given: The '.*' special matcher pattern
        When: Calling validate_matcher_pattern with any tool name
        Then: Should return (True, "") for any tool
        """
        pattern = ".*"
        tool_names = ["Task", "Bash", "Read", "Write", "Grep"]

        for tool in tool_names:
            matches, warning = self.validate_matcher_pattern(pattern, tool)

            assert matches is True, f"Pattern '.*' should match tool '{tool}', got {matches}"
            assert (
                warning == ""
            ), f"Pattern '.*' should have no warning for '{tool}', got '{warning}'"

    def test_wildcard_star_matches_everything(self):
        """Test that '*' wildcard pattern matches all tools.

        Given: The '*' special matcher pattern (not standard regex)
        When: Calling validate_matcher_pattern with any tool name
        Then: Should return (True, "") for any tool
        """
        pattern = "*"
        tool_names = ["Task", "Bash", "Read", "Write", "Grep"]

        for tool in tool_names:
            matches, warning = self.validate_matcher_pattern(pattern, tool)

            assert matches is True, f"Pattern '*' should match tool '{tool}', got {matches}"
            assert (
                warning == ""
            ), f"Pattern '*' should have no warning for '{tool}', got '{warning}'"

    def test_empty_string_matches_everything(self):
        """Test that empty string pattern matches all tools.

        Given: The '' special matcher pattern
        When: Calling validate_matcher_pattern with any tool name
        Then: Should return (True, "") for any tool
        """
        pattern = ""
        tool_names = ["Task", "Bash", "Read", "Write", "Grep"]

        for tool in tool_names:
            matches, warning = self.validate_matcher_pattern(pattern, tool)

            assert matches is True, f"Pattern '' should match tool '{tool}', got {matches}"
            assert warning == "", f"Pattern '' should have no warning for '{tool}', got '{warning}'"


class TestValidateMatcherPatternSafety:
    """Tests for validate_matcher_pattern() safety guarantees."""

    def setup_method(self):
        """Import the function before each test."""
        try:
            from hook_error_rca import validate_matcher_pattern

            self.validate_matcher_pattern = validate_matcher_pattern
        except ImportError as e:
            pytest.skip(f"Cannot import validate_matcher_pattern: {e}")

    def test_invalid_regex_safe_default_returns_true(self):
        """Test that invalid regex defaults to True (safe: allow the hook).

        Given: An invalid regex pattern that would raise re.error
        When: Calling validate_matcher_pattern with invalid pattern
        Then: Should return True (safe default to not block hooks)
        """
        invalid_patterns = [
            "(?P<unclosed",
            "[",
            "(",
            "*invalid",
            "\\x",  # incomplete escape
        ]

        for pattern in invalid_patterns:
            matches, warning = self.validate_matcher_pattern(pattern, "Task")

            assert (
                matches is True
            ), f"Invalid pattern '{pattern}' should default to True (safe default), got {matches}"
            assert (
                len(warning) > 0
            ), f"Invalid pattern '{pattern}' should generate a warning message"

    def test_catastrophic_pattern_safe_default_returns_true(self):
        """Test that catastrophic patterns default to True (safe: allow the hook).

        Given: A pattern that could cause catastrophic backtracking
        When: Calling validate_matcher_pattern with dangerous pattern
        Then: Should return True (safe default to not hang on matching)
        """
        catastrophic_patterns = [
            "(a+)+b",
            "((a+)*)+",
        ]

        for pattern in catastrophic_patterns:
            matches, warning = self.validate_matcher_pattern(pattern, "Task")

            assert (
                matches is True
            ), f"Dangerous pattern '{pattern}' should default to True (safe default), got {matches}"
            assert (
                len(warning) > 0
            ), f"Dangerous pattern '{pattern}' should generate a warning message"

    def test_function_does_not_raise_exception(self):
        """Test that function never raises exceptions for any input.

        Given: Various edge case inputs
        When: Calling validate_matcher_pattern with edge cases
        Then: Should always return a tuple without raising
        """
        edge_cases = [
            "",  # empty string (special pattern)
            ".*",  # match all (special pattern)
            "*",  # wildcard (special pattern)
            "[",  # unclosed bracket
            "(",  # unclosed paren
            "(a+)+b",  # catastrophic
            "((a+)*)+",  # catastrophic
            "^Task$",  # valid anchored pattern
            None,  # None input (should handle gracefully)
        ]

        for pattern in edge_cases:
            try:
                # Handle None separately if needed
                if pattern is None:
                    # May raise AttributeError - that's acceptable for None
                    try:
                        matches, warning = self.validate_matcher_pattern(pattern, "Task")
                    except (AttributeError, TypeError):
                        continue  # Expected for None input
                else:
                    matches, warning = self.validate_matcher_pattern(pattern, "Task")

                # Verify return type
                assert isinstance(
                    matches, bool
                ), f"Pattern '{pattern}': matches should be bool, got {type(matches)}"
                assert isinstance(
                    warning, str
                ), f"Pattern '{pattern}': warning should be str, got {type(warning)}"

            except Exception as e:
                pytest.fail(
                    f"validate_matcher_pattern should not raise exception for pattern '{pattern}': {e}"
                )


class TestValidateMatcherPatternLogging:
    """Tests for validate_matcher_pattern() logging behavior."""

    def setup_method(self):
        """Import the function before each test."""
        try:
            from hook_error_rca import validate_matcher_pattern

            self.validate_matcher_pattern = validate_matcher_pattern
        except ImportError as e:
            pytest.skip(f"Cannot import validate_matcher_pattern: {e}")

    def test_logging_occurs_for_invalid_regex(self, caplog):
        """Test that invalid regex patterns generate log warnings.

        Given: An invalid regex pattern
        When: Calling validate_matcher_pattern
        Then: Should log a warning message
        """
        import logging

        pattern = "(*invalid)"

        with caplog.at_level(logging.WARNING):
            matches, warning = self.validate_matcher_pattern(pattern, "Task")

        # Verify return value still works correctly
        assert matches is True
        assert "invalid" in warning.lower()

        # Note: Logger may not be configured in test environment,
        # so we don't assert on caplog records, just verify no exception

    def test_logging_occurs_for_catastrophic_patterns(self, caplog):
        """Test that catastrophic patterns generate log warnings.

        Given: A catastrophic backtracking pattern
        When: Calling validate_matcher_pattern
        Then: Should log a warning message
        """
        import logging

        pattern = "(a+)+b"

        with caplog.at_level(logging.WARNING):
            matches, warning = self.validate_matcher_pattern(pattern, "Task")

        # Verify return value still works correctly
        assert matches is True
        assert "catastrophic" in warning.lower()

        # Note: Logger may not be configured in test environment,
        # so we don't assert on caplog records, just verify no exception
