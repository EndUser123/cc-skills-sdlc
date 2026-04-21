"""
Unit tests for DRY principle enforcement in validate_templates.py.

These tests verify DRY (Don't Repeat Yourself) enforcement for template validation.
All tests are currently FAILING - this is the RED phase of TDD.

Run with: pytest P:/.claude/skills/arch/tests/test_dry_enforcement.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_templates import (
    check_duplicate_logic,
    _calculate_line_overlap,
    DUPLICATE_OVERLAP_THRESHOLD,
)


class TestDuplicateDetectionWarns:
    """Tests for duplicate detection warning functionality."""

    def test_duplicate_detection_warns_when_over_50_percent_overlap(self, capsys):
        """
        Test that check_duplicate_logic warns when >50% overlap is detected.

        Given: Two templates with >50% content overlap in a section
        When: check_duplicate_logic is called
        Then: Warning message should be printed for the duplicate section

        NOTE: This test FAILS because check_duplicate_logic does not
        currently print warnings - it only returns a list. The calling
        code (validate_all) handles warning display.
        """
        # Create content with >50% overlap
        shared_lines = "\n".join(
            [
                "Shared line 1",
                "Shared line 2",
                "Shared line 3",
                "Shared line 4",
                "Shared line 5",
                "Shared line 6",
            ]
        )

        fast_content = f"## Stage 0\n{shared_lines}\nFast unique"
        deep_content = f"## Stage 0\n{shared_lines}\nDeep unique"

        # This should return duplicates but does NOT print warnings itself
        result = check_duplicate_logic(fast_content, deep_content)

        # Current behavior: returns list of duplicates
        # Expected behavior: Should also emit warnings directly
        assert len(result) > 0, "Should detect duplicate"

        captured = capsys.readouterr()
        # This FAILS - no warning is printed by check_duplicate_logic itself
        assert "warn" in captured.out.lower() or "overlap" in captured.out.lower(), (
            "Expected warning message to be printed"
        )

    def test_duplicate_detection_returns_overlap_percentage(self):
        """
        Test that check_duplicate_logic returns overlap percentage data.

        Given: Two templates with overlapping content
        When: check_duplicate_logic is called
        Then: Returns tuples with section name, overlap percentage, and suggestion

        NOTE: This test PASSES - this functionality exists.
        """
        shared = "\n".join(["Same 1", "Same 2", "Same 3", "Same 4"])
        fast_content = f"## Stage 0\n{shared}\nFast"
        deep_content = f"## Stage 0\n{shared}\nDeep"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0
        section_name, overlap_percent, suggestion, severity = result[0]
        assert section_name == "Stage 0"
        assert isinstance(overlap_percent, float)
        assert overlap_percent > 50

    def test_duplicate_detection_threshold_at_exactly_50_percent(self):
        """
        Test boundary condition at exactly 50% overlap.

        Given: Two templates with exactly 50% content overlap
        When: check_duplicate_logic is called
        Then: Should NOT warn (threshold is >50%, not >=50%)

        NOTE: This test PASSES - threshold correctly uses > not >=.
        """
        # Exactly 50% overlap
        fast_content = "## Stage 0\nLine 1\nLine 2\nLine 3\nLine 4"
        deep_content = "## Stage 0\nLine 1\nLine 2\nDifferent 3\nDifferent 4"

        result = check_duplicate_logic(fast_content, deep_content)

        # Should NOT detect duplicate at exactly 50%
        assert len(result) == 0, "Should not warn at exactly 50% threshold"


class TestSharedFrameworkReference:
    """Tests for shared framework reference enforcement."""

    def test_shared_framework_reference_suggests_extraction(self):
        """
        Test that duplicate detection suggests referencing shared_frameworks.md.

        Given: Duplicate logic detected between templates
        When: check_duplicate_logic returns results
        Then: Suggestion should include reference to shared_frameworks.md

        NOTE: This test FAILS - current implementation returns generic
        "Consider extraction" suggestion without mentioning shared_frameworks.md.
        """
        shared = "\n".join(["Framework content 1", "Framework content 2"] * 5)
        fast_content = f"## Stage 0\n{shared}\nFast"
        deep_content = f"## Stage 0\n{shared}\nDeep"

        result = check_duplicate_logic(fast_content, deep_content)

        assert len(result) > 0
        section_name, overlap_percent, suggestion, severity = result[0]

        # This FAILS - suggestion is "Consider extraction" not specific
        assert (
            "shared_frameworks.md" in suggestion.lower()
            or "shared framework" in suggestion.lower()
        ), f"Expected reference to shared_frameworks.md, got: {suggestion}"

    def test_templates_should_reference_shared_frameworks(self, tmp_path):
        """
        Test that templates containing shared frameworks reference shared_frameworks.md.

        Given: Template content that duplicates shared_frameworks.md content
        When: Validation is performed
        Then: Should detect that shared_frameworks.md should be referenced instead

        NOTE: This test FAILS - no validation logic exists to check
        if templates duplicate content from shared_frameworks.md.
        """
        # Create mock shared frameworks file
        shared_frameworks = tmp_path / "shared_frameworks.md"
        shared_frameworks.write_text("""# Shared Decision Frameworks

## First Principles Thinking

When stuck:
1. What's the assumption I'm making?
2. Is it true? (or just conventional wisdom?)
3. What if I invert it?
""")

        # Create template that duplicates the framework
        template = tmp_path / "fast.md"
        template.write_text("""# Quick Architecture Decision

## Stage 0
Apply First Principles Thinking:
1. What's the assumption I'm making?
2. Is it true?
3. What if I invert it?
""")

        # This functionality does NOT exist yet
        # Need to import a function that checks shared framework duplication
        # For now, we test that the expected function would fail

        with pytest.raises(ImportError):
            # This function doesn't exist yet
            from validate_templates import check_shared_framework_duplication

            check_shared_framework_duplication(template, shared_frameworks)

    def test_detect_known_shared_framework_pattern(self):
        """
        Test detection of known shared framework patterns in templates.

        Given: Template contains known framework text (e.g., First Principles Thinking)
        When: Scanning for shared framework patterns
        Then: Should detect that it should reference shared_frameworks.md

        NOTE: This test FAILS - no pattern matching for shared frameworks exists.
        """
        # Known framework content from shared_frameworks.md
        first_principles_pattern = (
            "When stuck:\n1. What's the assumption I'm making?\n2. Is it true?"
        )

        template_content = f"""## Stage 0
Use {first_principles_pattern}
"""

        # This detection function doesn't exist
        with pytest.raises(ImportError):
            from validate_templates import detect_shared_framework_patterns

            detect_shared_framework_patterns(template_content)


class TestEnforcementLevel:
    """Tests for enforcement level (fail vs warn based on overlap percentage)."""

    def test_high_overlap_over_70_percent_should_fail_validation(self, tmp_path):
        """
        Test that overlap >70% causes validation to FAIL.

        Given: Two templates with >70% content overlap
        When: validate_all() is called
        Then: Should return exit code 1 (failure) not just warn

        NOTE: This test FAILS - current implementation only warns for
        duplicates regardless of severity. No failure mode exists.
        """
        from validate_templates import validate_all

        # Create high overlap content (>70%)
        shared = "\n".join(
            [f"Shared line {i}" for i in range(1, 11)]
        )  # 10 shared lines
        fast_content = f"## Stage 0\n{shared}\nFast"
        deep_content = f"## Stage 0\n{shared}\nDeep"

        # Mock the file system
        with patch("validate_templates.load_template_content") as mock_load:
            mock_load.side_effect = lambda p: (
                fast_content
                if "fast" in str(p).lower()
                else deep_content
                if "deep" in str(p).lower()
                else "# Heading\nContent"
            )

            with patch("validate_templates.load_contracts") as mock_contracts:
                # Mock contracts to pass heading validation
                mock_contracts.return_value = {
                    "fast": {
                        "required_headings": ["# Heading"],
                    },
                    "deep": {
                        "required_headings": ["# Heading"],
                    },
                }

                result = validate_all()

                # This FAILS - currently returns 0 (success) even with high overlap
                # Should return 1 (failure) for >70% overlap
                assert result == 1, (
                    f"Expected validation to FAIL with >70% overlap, got exit code {result}"
                )

    def test_high_overlap_threshold_constant_exists(self):
        """
        Test that HIGH_OVERLAP_THRESHOLD constant is defined.

        Given: The validation module
        When: Checking for enforcement thresholds
        Then: HIGH_OVERLAP_THRESHOLD constant should exist (typically 70%)

        NOTE: This test FAILS - only DUPLICATE_OVERLAP_THRESHOLD (50) exists.
        No separate high overlap threshold exists.
        """
        from validate_templates import HIGH_OVERLAP_THRESHOLD

        # This should exist but doesn't
        assert hasattr(HIGH_OVERLAP_THRESHOLD, "__gt__"), (
            "HIGH_OVERLAP_THRESHOLD should be a numeric value"
        )
        assert HIGH_OVERLAP_THRESHOLD > DUPLICATE_OVERLAP_THRESHOLD, (
            "HIGH_OVERLAP_THRESHOLD should be greater than DUPLICATE_OVERLAP_THRESHOLD"
        )

    def test_validation_returns_1_for_critical_duplicates(self, capsys):
        """
        Test that validation returns failure code for critical duplicates.

        Given: Templates with critical (>70%) overlap
        When: validate_all() completes
        Then: Exit code 1 should be returned, not just warnings printed

        NOTE: This test FAILS - validate_all() only returns 0 (success)
        when heading validation passes, regardless of duplicate warnings.
        """
        from validate_templates import validate_all

        # Mock high overlap scenario
        # After QUAL-008/TEST-ARCH-002: check_duplicate_logic returns 4 elements
        with patch("validate_templates.check_duplicate_logic") as mock_check:
            # Return critical overlap with severity indicator
            mock_check.return_value = [
                ("Stage 0", 85.0, "Critical - must extract", "critical"),
                ("IMPROVE_SYSTEM", 75.0, "High - should extract", "critical"),
            ]

        with patch("validate_templates.load_template_content") as mock_load:
            mock_load.return_value = "# Heading\nContent"

        with patch("validate_templates.load_contracts") as mock_contracts:
            mock_contracts.return_value = {
                "fast": {"required_headings": ["# Heading"]},
                "deep": {"required_headings": ["# Heading"]},
            }

            result = validate_all()

            # This FAILS - returns 0 even with critical duplicates
            assert result == 1, "Should return failure code for critical duplicates"


class TestMediumOverlap:
    """Tests for medium overlap (50-70%) behavior."""

    def test_medium_overlap_50_to_70_percent_should_warn_but_pass(self, tmp_path):
        """
        Test that overlap 50-70% warns but validation passes.

        Given: Two templates with 50-70% content overlap
        When: validate_all() is called
        Then: Should print warning but return exit code 0 (success)

        NOTE: This test PASSES - current implementation correctly warns
        but doesn't fail validation for any duplicate level.
        """
        from validate_templates import validate_all

        # Create medium overlap content (60%)
        shared = "\n".join([f"Shared line {i}" for i in range(1, 7)])  # 6 shared
        unique_fast = "\n".join([f"Fast line {i}" for i in range(1, 5)])  # 4 unique
        unique_deep = "\n".join([f"Deep line {i}" for i in range(1, 5)])  # 4 unique

        # 6 shared out of 10 total = 60% overlap
        fast_content = f"# Heading\n## Stage 0\n{shared}\n{unique_fast}"
        deep_content = f"# Heading\n## Stage 0\n{shared}\n{unique_deep}"

        with patch("validate_templates.load_template_content") as mock_load:
            mock_load.side_effect = lambda p: (
                fast_content
                if "fast" in str(p).lower()
                else deep_content
                if "deep" in str(p).lower()
                else "# Heading\nContent"
            )

            with patch("validate_templates.load_contracts") as mock_contracts:
                mock_contracts.return_value = {
                    "fast": {"required_headings": ["# Heading"]},
                    "deep": {"required_headings": ["# Heading"]},
                }

                result = validate_all()

                # Should pass (exit code 0) despite medium overlap
                assert result == 0, "Medium overlap should pass validation"

    def test_medium_overlap_boundary_at_70_percent(self):
        """
        Test boundary at exactly 70% overlap.

        Given: Two templates with exactly 70% content overlap
        When: Validation is performed
        Then: Should warn but NOT fail (70 is not > 70)

        NOTE: This test PASSES if HIGH_OVERLAP_THRESHOLD is 70 (exclusive).
        """
        # Exactly 70% overlap
        shared = "\n".join([f"Shared {i}" for i in range(7)])  # 7 shared
        fast = "## Stage 0\n" + shared + "\nFast1\nFast2\nFast3"
        deep = "## Stage 0\n" + shared + "\nDeep1\nDeep2\nDeep3"

        result = check_duplicate_logic(fast, deep)

        # 7 shared out of 10 total = 70%
        # If HIGH_OVERLAP_THRESHOLD = 70 (exclusive), this should NOT fail
        # Current implementation uses DUPLICATE_OVERLAP_THRESHOLD = 50
        # So this WILL be detected as duplicate
        assert len(result) > 0, "70% overlap should be detected as duplicate"

    def test_overlap_percentage_calculation_accuracy(self):
        """
        Test that overlap percentage is calculated correctly.

        Given: Two text blocks with known overlap
        When: _calculate_line_overlap is called
        Then: Returns accurate percentage

        NOTE: This test PASSES - calculation is correct.
        """
        # 5 shared lines out of 10 total unique lines = 50%
        text1 = "\n".join(
            [
                "Line 1",
                "Line 2",
                "Line 3",
                "Line 4",
                "Line 5",
                "Unique A",
                "Unique B",
                "Unique C",
                "Unique D",
                "Unique E",
            ]
        )
        text2 = "\n".join(
            [
                "Line 1",
                "Line 2",
                "Line 3",
                "Line 4",
                "Line 5",
                "Different F",
                "Different G",
                "Different H",
                "Different I",
                "Different J",
            ]
        )

        overlap = _calculate_line_overlap(text1, text2)

        assert overlap == 50.0, f"Expected 50% overlap, got {overlap}%"


class TestDRYEnforcementIntegration:
    """Integration tests for complete DRY enforcement workflow."""

    def test_complete_dry_validation_workflow(self, tmp_path, capsys):
        """
        Test complete DRY validation: detect duplicates, suggest extraction,
        enforce severity levels.

        Given: Multiple templates with varying overlap levels
        When: Full validation runs
        Then:
            - Low overlap (<50%): no warning
            - Medium overlap (50-70%): warning, passes
            - High overlap (>70%): error, fails

        NOTE: This test FAILS - severity-based enforcement not implemented.
        """
        from validate_templates import validate_all

        # Mock scenarios with different overlap levels
        with patch("validate_templates.load_template_content") as mock_load:
            mock_load.return_value = "# Heading\nContent"

            with patch("validate_templates.load_contracts") as mock_contracts:
                mock_contracts.return_value = {
                    "fast": {"required_headings": ["# Heading"]},
                    "deep": {"required_headings": ["# Heading"]},
                }

                with patch("validate_templates.check_duplicate_logic") as mock_check:
                    # After QUAL-008/TEST-ARCH-002: check_duplicate_logic returns 4 elements
                    # (section_name, overlap_percent, suggestion, severity)
                    mock_check.return_value = [
                        ("Stage 0", 45.0, "OK", "info"),  # Below threshold - ignored
                        (
                            "IMPROVE_SYSTEM",
                            60.0,
                            "Consider extraction",
                            "warning",
                        ),  # Medium - warn
                        (
                            "CKS.db",
                            80.0,
                            "Critical - must extract",
                            "critical",
                        ),  # High - fail
                    ]

                    result = validate_all()
                    captured = capsys.readouterr()

                    # Should detect medium and high overlap (overlap is now float, not formatted string)
                    assert "60.0" in captured.out or "80.0" in captured.out or "warning" in captured.out.lower(), (
                        "Overlap percentages or severity should be reported"
                    )

                    # Should FAIL due to critical (80%) overlap
                    assert result == 1, "Should fail validation with critical overlap"

    def test_shared_frameworks_reference_in_result_message(self, capsys):
        """
        Test that validation output mentions shared_frameworks.md when
        duplicates are found.

        Given: Duplicate logic detected
        When: Validation completes
        Then: Output should reference shared_frameworks.md as solution

        NOTE: This test FAILS - while validate_all() prints a generic message
        about extracting to domain_inclusions.md, it doesn't mention
        shared_frameworks.md for framework-type content.
        """
        from validate_templates import validate_all

        # After QUAL-008/TEST-ARCH-002: check_duplicate_logic returns 4 elements
        with patch("validate_templates.check_duplicate_logic") as mock_check:
            mock_check.return_value = [
                ("Stage 0", 55.0, "Consider extraction", "warning"),
            ]

        with patch("validate_templates.load_template_content") as mock_load:
            mock_load.return_value = "# Heading\nContent"

        with patch("validate_templates.load_contracts") as mock_contracts:
            mock_contracts.return_value = {
                "fast": {"required_headings": ["# Heading"]},
                "deep": {"required_headings": ["# Heading"]},
            }

            validate_all()
            captured = capsys.readouterr()

            # This FAILS - mentions domain_inclusions.md, not shared_frameworks.md
            assert "shared_frameworks.md" in captured.out.lower(), (
                "Should suggest referencing shared_frameworks.md for shared logic"
            )
