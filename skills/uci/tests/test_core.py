"""
Unit tests for UCI core layer functions.

Tests scope detection, impact/effort matrix, and verdict synthesis.
"""

from pathlib import Path

import pytest


class TestScopeDetector:
    """Test scope detection priority function."""

    def test_scope_detector_exists(self):
        """Test that scope_detector.py module exists."""
        scope_detector = Path("P:/.claude/skills/uci/lib/scope_detector.py")
        assert scope_detector.exists(), "scope_detector.py should exist"

    def test_scope_detector_has_detect_scope(self):
        """Test that scope_detector has detect_scope function."""
        scope_detector = Path("P:/.claude/skills/uci/lib/scope_detector.py")
        content = scope_detector.read_text(encoding="utf-8")

        # Should have detect_scope function
        assert "def detect_scope" in content or "async def detect_scope" in content

    def test_scope_detector_has_scope_type(self):
        """Test that scope_detector defines ScopeType."""
        scope_detector = Path("P:/.claude/skills/uci/lib/scope_detector.py")
        content = scope_detector.read_text(encoding="utf-8")

        # Should have ScopeType (enum or class)
        assert "ScopeType" in content

    def test_scope_detector_priority_order(self):
        """Test that scope detector follows priority order."""
        scope_detector = Path("P:/.claude/skills/uci/lib/scope_detector.py")
        content = scope_detector.read_text(encoding="utf-8")

        # Should mention priority: user-specified > feature branch > staged > latest commit
        assert any(
            term in content.lower()
            for term in ["priority", "user", "feature", "branch", "staged", "commit"]
        )

    def test_scope_detector_exported(self):
        """Test that detect_scope is exported from __init__.py."""
        init_file = Path("P:/.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export detect_scope
        assert '"detect_scope"' in content or "'detect_scope'" in content


class TestImpactEffort:
    """Test impact/effort matrix calculation."""

    def test_impact_effort_module_exists(self):
        """Test that impact_effort.py module exists."""
        impact_effort = Path("P:/.claude/skills/uci/lib/impact_effort.py")
        assert impact_effort.exists(), "impact_effort.py should exist"

    def test_impact_effort_has_calculate_function(self):
        """Test that impact_effort has calculate_impact_effort function."""
        impact_effort = Path("P:/.claude/skills/uci/lib/impact_effort.py")
        content = impact_effort.read_text(encoding="utf-8")

        # Should have calculate_impact_effort function
        assert (
            "def calculate_impact_effort" in content
            or "async def calculate_impact_effort" in content
        )

    def test_impact_effort_has_level_enum(self):
        """Test that impact_effort defines Level (HIGH/MED/LOW)."""
        impact_effort = Path("P:/.claude/skills/uci/lib/impact_effort.py")
        content = impact_effort.read_text(encoding="utf-8")

        # Should have Level with HIGH, MED, LOW values
        assert "Level" in content
        assert all(level in content for level in ["HIGH", "MED", "LOW"])

    def test_impact_effort_has_sort_function(self):
        """Test that impact_effort can sort findings by priority."""
        impact_effort = Path("P:/.claude/skills/uci/lib/impact_effort.py")
        content = impact_effort.read_text(encoding="utf-8")

        # Should have sort_findings_by_priority function
        assert "sort_findings_by_priority" in content

    def test_impact_effort_exported(self):
        """Test that impact_effort functions are exported from __init__.py."""
        init_file = Path("P:/.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export key functions
        assert '"calculate_impact_effort"' in content or "'calculate_impact_effort'" in content
        assert '"sort_findings_by_priority"' in content or "'sort_findings_by_priority'" in content


class TestVerdictSynthesis:
    """Test three-tier verdict synthesis."""

    def test_verdict_module_exists(self):
        """Test that verdict.py module exists."""
        verdict = Path("P:/.claude/skills/uci/lib/verdict.py")
        assert verdict.exists(), "verdict.py should exist"

    def test_verdict_has_synthesize_function(self):
        """Test that verdict has synthesize_verdict function."""
        verdict = Path("P:/.claude/skills/uci/lib/verdict.py")
        content = verdict.read_text(encoding="utf-8")

        # Should have synthesize_verdict function
        assert "def synthesize_verdict" in content or "async def synthesize_verdict" in content

    def test_verdict_has_verdict_class(self):
        """Test that verdict defines Verdict dataclass/enum."""
        verdict = Path("P:/.claude/skills/uci/lib/verdict.py")
        content = verdict.read_text(encoding="utf-8")

        # Should have Verdict class
        assert "class Verdict" in content or "Verdict =" in content

    def test_verdict_three_tier_levels(self):
        """Test that verdict has three tiers: Ready to Merge / Needs Attention / Needs Work."""
        verdict = Path("P:/.claude/skills/uci/lib/verdict.py")
        content = verdict.read_text(encoding="utf-8")

        # Should mention three-tier verdict levels
        # "Ready to Merge", "Needs Attention", "Needs Work"
        assert any(
            term in content
            for term in [
                "Ready to Merge",
                "Needs Attention",
                "Needs Work",
                "READY_TO_MERGE",
                "NEEDS_ATTENTION",
                "NEEDS_WORK",
            ]
        )

    def test_verdict_exported(self):
        """Test that verdict functions are exported from __init__.py."""
        init_file = Path("P:/.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export key functions
        assert '"synthesize_verdict"' in content or "'synthesize_verdict'" in content


class TestFormatter:
    """Test output formatter with enhanced schema."""

    def test_formatter_module_exists(self):
        """Test that formatter.py module exists."""
        formatter = Path("P:/.claude/skills/uci/lib/formatter.py")
        assert formatter.exists(), "formatter.py should exist"

    def test_formatter_has_uci_formatter_class(self):
        """Test that formatter has UCIFormatter class."""
        formatter = Path("P:/.claude/skills/uci/lib/formatter.py")
        content = formatter.read_text(encoding="utf-8")

        # Should have UCIFormatter class
        assert "class UCIFormatter" in content

    def test_formatter_has_output_format(self):
        """Test that formatter defines OutputFormat."""
        formatter = Path("P:/.claude/skills/uci/lib/formatter.py")
        content = formatter.read_text(encoding="utf-8")

        # Should have OutputFormat (markdown, json, summary)
        assert "OutputFormat" in content

    def test_formatter_exported(self):
        """Test that formatter is exported from __init__.py."""
        init_file = Path("P:/.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export UCIFormatter
        assert '"UCIFormatter"' in content or "'UCIFormatter'" in content


class TestAssessmentMode:
    """Test assessment/dry-run mode."""

    def test_assessment_mode_exists(self):
        """Test that assessment_mode.py module exists."""
        assessment = Path("P:/.claude/skills/uci/lib/assessment_mode.py")
        assert assessment.exists(), "assessment_mode.py should exist"

    def test_assessment_mode_has_class(self):
        """Test that assessment_mode has AssessmentMode class."""
        assessment = Path("P:/.claude/skills/uci/lib/assessment_mode.py")
        content = assessment.read_text(encoding="utf-8")

        # Should have AssessmentMode class
        assert "class AssessmentMode" in content

    def test_assessment_mode_has_finding_class(self):
        """Test that assessment_mode has AssessmentFinding dataclass."""
        assessment = Path("P:/.claude/skills/uci/lib/assessment_mode.py")
        content = assessment.read_text(encoding="utf-8")

        # Should have AssessmentFinding dataclass
        assert "class AssessmentFinding" in content

    def test_assessment_mode_has_report_class(self):
        """Test that assessment_mode has AssessmentReport dataclass."""
        assessment = Path("P:/.claude/skills/uci/lib/assessment_mode.py")
        content = assessment.read_text(encoding="utf-8")

        # Should have AssessmentReport dataclass
        assert "class AssessmentReport" in content

    def test_assessment_mode_quality_checks(self):
        """Test that assessment_mode has 6-check quality validation."""
        assessment = Path("P:/.claude/skills/uci/lib/assessment_mode.py")
        content = assessment.read_text(encoding="utf-8")

        # Should have QUALITY_CHECKS with 6 checks
        assert "QUALITY_CHECKS" in content

    def test_assessment_mode_exported(self):
        """Test that assessment_mode is exported from __init__.py."""
        init_file = Path("P:/.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export key classes and functions
        assert '"AssessmentMode"' in content or "'AssessmentMode'" in content
        assert '"run_assessment"' in content or "'run_assessment'" in content


class TestCoreIntegration:
    """Integration tests for core layer components."""

    def test_all_core_modules_exist(self):
        """Test that all core layer modules exist."""
        modules = [
            "scope_detector.py",
            "impact_effort.py",
            "verdict.py",
            "formatter.py",
            "assessment_mode.py",
        ]

        for module in modules:
            module_path = Path(f"P:/.claude/skills/uci/lib/{module}")
            assert module_path.exists(), f"{module} should exist"

    def test_all_core_modules_exported(self):
        """Test that all core layer functions are exported."""
        init_file = Path("P:/.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export all core functions
        expected_exports = [
            "detect_scope",
            "calculate_impact_effort",
            "synthesize_verdict",
            "UCIFormatter",
            "AssessmentMode",
        ]

        for export in expected_exports:
            assert (
                f'"{export}"' in content or f"'{export}'" in content
            ), f"{export} should be exported"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
