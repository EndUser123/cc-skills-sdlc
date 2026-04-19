"""
Failing test for TEST-ARCH-002: Overlap percentage numeric validation (RED phase).

These tests verify numeric threshold validation for overlap percentages returned by
check_duplicate_logic(). The current tests only check for 'overlap' string but don't
validate the actual numeric values against thresholds.

Requirements:
1. Test that overlap percentage is numeric value (not just 'overlap' substring)
2. Test that value is validated against DUPLICATE_OVERLAP_THRESHOLD (50%)
3. Test that HIGH_OVERLAP_THRESHOLD (70%) causes validation failure

Run with: pytest P:/.claude/skills/arch/tests/test_overlap_numeric_validation.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_templates import (
    check_duplicate_logic,
    DUPLICATE_OVERLAP_THRESHOLD,
    HIGH_OVERLAP_THRESHOLD,
)


# NOTE: After QUAL-008, check_duplicate_logic() returns overlap as float directly.
# The parse_overlap_percentage helper function is obsolete and removed.


class TestOverlapNumericValidation:
    """
    Tests for numeric overlap percentage validation.

    Current tests in test_validate_templates.py only check that "overlap"
    appears in the result string. These tests verify the actual numeric
    values are properly validated against thresholds.
    """

    def test_check_duplicate_logic_returns_numeric_value(self):
        """
        Test that check_duplicate_logic returns numeric overlap value.

        Given: fast.md and deep.md with >50% overlap
        When: check_duplicate_logic is called
        Then: The overlap percentage should be a parseable numeric value

        This test verifies numeric parsing of overlap percentage, which is
        NOT validated in current test_validate_templates.py tests.
        """
        # Create content with ~55% overlap (between 50% and 70% thresholds)
        # 6 shared lines + 5 unique lines each = 11 total lines, 6 shared = ~54.5%
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 7)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique 1\nFast unique 2\nFast unique 3\nFast unique 4\nFast unique 5"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique 1\nDeep unique 2\nDeep unique 3\nDeep unique 4\nDeep unique 5"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        section_name, overlap_percent, suggestion, severity = result[0]

        # After QUAL-008: overlap_percent is already a float, no parsing needed
        overlap_value = overlap_percent

        # Verify the value is numeric and in expected range
        assert isinstance(overlap_value, (int, float)), (
            f"Overlap value should be numeric, got {type(overlap_value)}"
        )
        assert DUPLICATE_OVERLAP_THRESHOLD < overlap_value <= HIGH_OVERLAP_THRESHOLD, (
            f"Expected overlap in warning range (50-70%), got {overlap_value}%"
        )
        assert severity == "warning", (
            f"Overlap in warning range should have severity='warning', got '{severity}'"
        )

    def test_check_duplicate_logic_validates_against_50_percent_threshold(self):
        """
        Test that overlap percentage is validated against DUPLICATE_OVERLAP_THRESHOLD.

        Given: fast.md and deep.md with overlap just above 50%
        When: check_duplicate_logic is called
        Then: The numeric overlap should be validated against 50% threshold

        This test FAILS because current tests don't validate the exact
        numeric threshold boundary.

        The implementation uses > DUPLICATE_OVERLAP_THRESHOLD (50%), not >=,
        so this test needs >50% overlap to trigger detection.
        """
        # Create content with ~55% overlap (above 50% threshold)
        # 5 shared lines + 4 unique lines each = 9 total lines, 5 shared = 55.5%
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 6)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique 1\nFast unique 2\nFast unique 3\nFast unique 4"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique 1\nDeep unique 2\nDeep unique 3\nDeep unique 4"

        result = check_duplicate_logic(fast_content, deep_content)

        # Should detect duplicates above 50% threshold
        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        section_name, overlap_percent, suggestion, severity = result[0]
        # After QUAL-008: overlap_percent is already a float
        overlap_value = overlap_percent

        # FAILING ASSERTION: Need to validate against exact threshold
        # The implementation uses > 50%, so overlap_value should be > 50
        assert overlap_value > DUPLICATE_OVERLAP_THRESHOLD, (
            f"Overlap {overlap_value}% should be > DUPLICATE_OVERLAP_THRESHOLD "
            f"({DUPLICATE_OVERLAP_THRESHOLD}%)"
        )
        assert overlap_value <= HIGH_OVERLAP_THRESHOLD, (
            f"Overlap {overlap_value}% should be in warning range (< {HIGH_OVERLAP_THRESHOLD}%)"
        )
        assert severity == "warning", (
            f"Overlap in warning range should have severity='warning', got '{severity}'"
        )

    def test_check_duplicate_logic_high_overlap_triggers_failure(self):
        """
        Test that HIGH_OVERLAP_THRESHOLD (70%) causes validation failure.

        Given: fast.md and deep.md with >70% overlap
        When: check_duplicate_logic is called
        Then: High overlap should be detected and cause validation failure

        This test FAILS because the current implementation doesn't
        distinguish between warning threshold (50-70%) and failure
        threshold (>70%).
        """
        # Create content with ~80% overlap
        # 8 shared lines + 2 unique lines each = 10 total lines, 8 shared = 80%
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 9)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique 1\nFast unique 2"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique 1\nDeep unique 2"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        section_name, overlap_percent, suggestion, severity = result[0]
        # After QUAL-008: overlap_percent is already a float
        overlap_value = overlap_percent

        # FAILING ASSERTION: Need to validate against HIGH_OVERLAP_THRESHOLD
        assert overlap_value > HIGH_OVERLAP_THRESHOLD, (
            f"Expected overlap >70% (HIGH_OVERLAP_THRESHOLD), got {overlap_value}%"
        )

        # Verify severity is 'critical' for high overlap
        assert severity == "critical", (
            f"High overlap ({overlap_value}%) should have severity='critical', got '{severity}'"
        )

        # Additionally, the result should indicate failure vs warning
        # Current implementation doesn't distinguish these states
        # This assertion documents what SHOULD happen but DOESN'T
        assert overlap_value > HIGH_OVERLAP_THRESHOLD, (
            f"High overlap ({overlap_value}%) should trigger validation failure, "
            f"not just warning"
        )

    def test_check_duplicate_logic_below_threshold_returns_empty(self):
        """
        Test that overlap below 50% threshold returns empty list.

        Given: fast.md and deep.md with <50% overlap
        When: check_duplicate_logic is called
        Then: Empty list should be returned (below threshold)

        This test PASSES but documents the lower boundary behavior.
        """
        # Create content with ~40% overlap
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 5)])
        fast_unique = "\n".join([f"Fast unique {i}" for i in range(1, 7)])
        deep_unique = "\n".join([f"Deep unique {i}" for i in range(1, 7)])

        fast_content = f"## Stage 0\n{shared_lines}\n{fast_unique}"
        deep_content = f"## Stage 0\n{shared_lines}\n{deep_unique}"

        result = check_duplicate_logic(fast_content, deep_content)

        # Should NOT detect duplicates (below 50% threshold)
        assert result == [], f"Expected no duplicates below 50% threshold, got {result}"

    def test_threshold_constants_are_defined(self):
        """
        Test that threshold constants are properly defined.

        Given: The validate_templates module
        When: Threshold constants are accessed
        Then: DUPLICATE_OVERLAP_THRESHOLD and HIGH_OVERLAP_THRESHOLD exist

        This test PASSES but documents expected threshold values.
        """
        assert DUPLICATE_OVERLAP_THRESHOLD == 50.0, (
            f"Expected DUPLICATE_OVERLAP_THRESHOLD=50.0, got {DUPLICATE_OVERLAP_THRESHOLD}"
        )
        assert HIGH_OVERLAP_THRESHOLD == 70.0, (
            f"Expected HIGH_OVERLAP_THRESHOLD=70.0, got {HIGH_OVERLAP_THRESHOLD}"
        )
        assert HIGH_OVERLAP_THRESHOLD > DUPLICATE_OVERLAP_THRESHOLD, (
            f"HIGH_OVERLAP_THRESHOLD ({HIGH_OVERLAP_THRESHOLD}) should be "
            f"> DUPLICATE_OVERLAP_THRESHOLD ({DUPLICATE_OVERLAP_THRESHOLD})"
        )


class TestCurrentTestLimitations:
    """
    Characterization tests showing what current tests DON'T validate.

    These tests demonstrate the gap between current test coverage
    (which only checks for 'overlap' substring) and required
    numeric validation.
    """

    def test_current_test_only_checks_string_not_numeric(self):
        """
        Characterization: Current test_check_duplicate_logic_detects_50_percent_overlap
        only validates 'overlap' in string, not the numeric percentage.

        This test demonstrates what's MISSING from current test_validate_templates.py.
        The existing test at line 420 only checks:
            assert "overlap" in result[0][1].lower()

        It does NOT validate the numeric percentage value against thresholds.
        """
        # Same content as existing test
        shared_lines = "\n".join([
            "Shared line 1",
            "Shared line 2",
            "Shared line 3",
            "Shared line 4",
            "Shared line 5",
        ])
        fast_content = f"# Fast\n\n## Stage 0\n{shared_lines}\nFast unique line"
        deep_content = f"# Deep\n\n## Stage 0\n{shared_lines}\nDeep unique line"

        result = check_duplicate_logic(fast_content, deep_content)

        # This is what the current test validates (PASSES):
        assert len(result) > 0, "Should detect duplicates"
        assert result[0][0] == "Stage 0"
        # After QUAL-008: overlap_percent is float, not string - check it's numeric
        overlap_percent = result[0][1]
        assert isinstance(overlap_percent, float), "Overlap should be float after QUAL-008"

        # This is what's MISSING (should be added):
        overlap_value = overlap_percent

        # The current test doesn't validate this numeric threshold
        assert overlap_value > DUPLICATE_OVERLAP_THRESHOLD, (
            f"Overlap {overlap_value}% should be > DUPLICATE_OVERLAP_THRESHOLD "
            f"({DUPLICATE_OVERLAP_THRESHOLD}%) - this validation is MISSING from current tests"
        )

    def test_check_duplicate_logic_returns_severity_indicator(self):
        """
        FAILING TEST: check_duplicate_logic should return severity indicator.

        Given: fast.md and deep.md with >70% overlap
        When: check_duplicate_logic is called
        Then: Result should include severity level ('warning' or 'failure')

        This test FAILS because the current implementation returns:
            (section_name, overlap_str, suggestion)

        But SHOULD return:
            (section_name, overlap_str, suggestion, severity)

        This is MISSING functionality that TEST-ARCH-002 requires.
        """
        # Create content with ~80% overlap (critical/failure range)
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 9)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique 1\nFast unique 2"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique 1\nDeep unique 2"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        # FAILING: Result tuple should have 4 elements (including severity)
        # Current implementation only has 3 elements
        assert len(result[0]) == 4, (
            f"Result should have 4 elements (section, overlap, suggestion, severity), "
            f"got {len(result[0])}: {result[0]}"
        )

        section_name, overlap_percent, suggestion, severity = result[0]

        # After QUAL-008: overlap_percent is already a float
        overlap_value = overlap_percent
        assert overlap_value > HIGH_OVERLAP_THRESHOLD, (
            f"Expected overlap >70%, got {overlap_value}%"
        )

        # Severity should be 'failure' or 'critical' for high overlap
        assert severity in ['warning', 'failure', 'critical'], (
            f"Severity should be one of: warning, failure, critical. Got: '{severity}'"
        )

        # For overlap >70%, severity should be 'failure' or 'critical'
        assert severity in ['failure', 'critical'], (
            f"Overlap {overlap_value}% > HIGH_OVERLAP_THRESHOLD ({HIGH_OVERLAP_THRESHOLD}%) "
            f"should have severity='failure' or 'critical', got '{severity}'"
        )

    def test_warning_range_has_severity_warning(self):
        """
        FAILING TEST: Overlap in 50-70% range should have severity='warning'.

        Given: fast.md and deep.md with 50-70% overlap
        When: check_duplicate_logic is called
        Then: Result should have severity='warning'

        This test FAILS because severity indicator is NOT implemented.
        """
        # Create content with ~55% overlap (warning range)
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 7)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique 1\nFast unique 2\nFast unique 3\nFast unique 4\nFast unique 5"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique 1\nDeep unique 2\nDeep unique 3\nDeep unique 4\nDeep unique 5"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        # FAILING: Result should have 4th element with severity
        assert len(result[0]) == 4, (
            f"Result should have 4 elements including severity, got {len(result[0])}"
        )

        section_name, overlap_percent, suggestion, severity = result[0]

        # Verify overlap is in warning range
        overlap_value = overlap_percent
        assert DUPLICATE_OVERLAP_THRESHOLD < overlap_value <= HIGH_OVERLAP_THRESHOLD, (
            f"Expected overlap in warning range (50-70%), got {overlap_value}%"
        )

        # FAILING: Severity should be 'warning' for 50-70% range
        assert severity == 'warning', (
            f"Overlap {overlap_value}% in warning range should have severity='warning', "
            f"got '{severity}'"
        )
