"""
Failing test for overlap percentage validation (RED phase).

These tests verify numeric threshold validation for overlap percentages
returned by check_duplicate_logic(). The tests parse the overlap percentage
string (e.g., '85.0% overlap') and validate against thresholds:
- <50%: no warning (not returned by check_duplicate_logic)
- 50-70%: warn
- >70%: fail

Run with: pytest P:/.claude/skills/arch/tests/test_overlap_validation.py -v

Context: TEST-007 - No overlap percentage validation in test_validate_templates.py

This test file demonstrates tests that SHOULD exist in test_validate_templates.py
but currently DON'T. The tests below verify numeric parsing and threshold validation
that is MISSING from the existing test suite.
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
# The parse_overlap_percentage helper is obsolete - removed.


class TestOverlapPercentageParsingMISSING:
    """
    Tests for parsing overlap percentage from result strings.

    THESE TESTS DOCUMENT MISSING FUNCTIONALITY in test_validate_templates.py.

    The existing tests in test_validate_templates.py call check_duplicate_logic()
    but do NOT parse or validate the numeric overlap percentage values.

    This class demonstrates what tests SHOULD be added.
    """

    def test_check_duplicate_logic_returns_numeric_overlap_parseable(self, capsys):
        """
        FAILING TEST: check_duplicate_logic results should have parseable percentages.

        Given: fast.md and deep.md with >50% overlap
        When: check_duplicate_logic is called
        Then: The overlap string should be parseable to a numeric percentage

        THIS TEST FAILS because test_validate_templates.py does not have any tests
        that parse and validate the numeric overlap percentage from the result tuples.
        """
        # Create content with ~60% overlap
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 7)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique 1\nFast unique 2\nFast unique 3\nFast unique 4"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique 1\nDeep unique 2\nDeep unique 3\nDeep unique 4"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        section_name, overlap_percent, suggestion, severity = result[0]

        # After QUAL-008 fix: overlap is now float, not string
        # Before: overlap_str.split('%')[0] was fragile parsing
        # After: Direct float access with formatting only for display
        overlap_value = overlap_percent
        assert isinstance(overlap_value, float)

        # This validation is MISSING from test_validate_templates.py
        assert DUPLICATE_OVERLAP_THRESHOLD < overlap_value <= HIGH_OVERLAP_THRESHOLD, (
            f"Expected overlap in warning range (50-70%), got {overlap_value}%"
        )

    def test_check_duplicate_logic_threshold_validation_70_plus(self, capsys):
        """
        FAILING TEST: High overlap (>70%) should be validated numerically.

        Given: fast.md and deep.md with >70% overlap
        When: check_duplicate_logic is called
        Then: The numeric overlap should be validated against HIGH_OVERLAP_THRESHOLD

        THIS TEST FAILS because test_validate_templates.py does not validate
        that overlap percentages above HIGH_OVERLAP_THRESHOLD (70%) are properly detected.
        """
        # Create content with ~85% overlap
        shared_lines = "\n".join([f"Shared line {i}" for i in range(1, 10)])
        fast_content = f"## Stage 0\n{shared_lines}\nFast unique"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates above 50% threshold"

        section_name, overlap_percent, suggestion, severity = result[0]

        # After QUAL-008 and TEST-ARCH-002 fixes: Direct float access, severity indicates critical
        overlap_value = overlap_percent
        assert severity == "critical"
        # This validation against HIGH_OVERLAP_THRESHOLD does NOT exist
        assert overlap_value > HIGH_OVERLAP_THRESHOLD, (
            f"Expected overlap >70% (HIGH_OVERLAP_THRESHOLD), got {overlap_value}%"
        )

    def test_check_duplicate_logic_threshold_validation_below_50(self, capsys):
        """
        FAILING TEST: Low overlap (<50%) should NOT be reported.

        Given: fast.md and deep.md with <50% overlap
        When: check_duplicate_logic is called
        Then: Empty list should be returned (below threshold)

        NOTE: This test PASSES because the existing test_check_duplicate_logic_ignores_low_overlap
        in test_validate_templates.py does test this. However, it doesn't validate the exact
        numeric threshold boundary.
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


class TestOverlapPercentageThresholds:
    """
    Tests for threshold validation logic.

    THESE TESTS DOCUMENT MISSING threshold validation in test_validate_templates.py.

    The existing tests don't validate that overlap percentages are correctly
    categorized into the three tiers:
    - <50%: no warning (not returned)
    - 50-70%: warning threshold
    - >70%: failure threshold
    """

    def test_threshold_constants_exist_and_are_correct(self):
        """
        Test that threshold constants are properly defined and have expected values.

        Given: The validate_templates module
        When: Threshold constants are accessed
        Then: DUPLICATE_OVERLAP_THRESHOLD and HIGH_OVERLAP_THRESHOLD have expected values

        THIS TEST PASSES but documents expected values for other failing tests.
        """
        # This test documents the expected threshold values
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


class TestMissingNumericValidationInExistingTests:
    """
    Characterization tests for MISSING numeric validation in test_validate_templates.py.

    These tests demonstrate what's MISSING from the existing test suite:
    - test_check_duplicate_logic_detects_50_percent_overlap only checks "overlap" in string
    - No test parses the numeric percentage value
    - No test validates against DUPLICATE_OVERLAP_THRESHOLD or HIGH_OVERLAP_THRESHOLD
    """

    def test_existing_test_only_checks_string_not_numeric(self, capsys):
        """
        FAILING TEST: Existing test doesn't validate numeric percentage.

        The test test_check_duplicate_logic_detects_50_percent_overlap in
        test_validate_templates.py only checks:
            assert "overlap" in result[0][1].lower()

        It does NOT parse and validate the numeric percentage value against
        the threshold constants.

        This test demonstrates that gap by showing what SHOULD be validated.
        """
        # Same content as test_check_duplicate_logic_detects_50_percent_overlap
        shared_lines = "\n".join(
            [
                "Shared line 1",
                "Shared line 2",
                "Shared line 3",
                "Shared line 4",
                "Shared line 5",
            ]
        )
        fast_content = f"# Fast\n\n## Stage 0\n{shared_lines}\nFast unique line"
        deep_content = f"# Deep\n\n## Stage 0\n{shared_lines}\nDeep unique line"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0, "Should detect duplicates"
        section_name, overlap_percent, suggestion, severity = result[0]
        assert section_name == "Stage 0"
        assert isinstance(overlap_percent, float)

        # After QUAL-008 and TEST-ARCH-002 fixes: Direct float access
        # Before: overlap_str.split('%')[0] was fragile parsing
        overlap_value = overlap_percent

        # This numeric threshold validation does NOT exist in test_validate_templates.py
        assert overlap_value > DUPLICATE_OVERLAP_THRESHOLD, (
            f"Overlap {overlap_value}% should be > DUPLICATE_OVERLAP_THRESHOLD "
            f"({DUPLICATE_OVERLAP_THRESHOLD}%)"
        )

    # NOTE: After QUAL-008, test_parse_overlap_percentage_helper_function removed.
    # The helper function is obsolete since overlap is now returned as float directly.
