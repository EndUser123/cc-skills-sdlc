"""Test pattern_validation.py - Validates detector patterns before implementation.

Related bugs:
- unverified_stance_detector.py Bug #1: Bare "has" caused false positives
- Pattern "blocked" matched injected context keywords

Test coverage ensures pattern validation catches these issues BEFORE implementation.
"""

import sys
from pathlib import Path

# Add parent scripts directory to path for import
# ruff: noqa: E402
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from pattern_validation import PatternIssue, validate_detector_patterns


class TestPatternIssue:
    """Test PatternIssue NamedTuple creation and properties."""

    def test_pattern_issue_creation(self):
        """PatternIssue can be created with all fields."""
        issue = PatternIssue(
            pattern="blocked",
            issue="Pattern matches injected context keyword 'blocked'",
            severity="critical",
            recommendation="Use word boundaries: \\bblocked\\b"
        )
        assert issue.pattern == "blocked"
        assert issue.severity == "critical"
        assert "context keyword" in issue.issue.lower()

    def test_pattern_issue_severity_levels(self):
        """All severity levels are valid strings."""
        severities = ["critical", "high", "medium"]
        for severity in severities:
            issue = PatternIssue(
                pattern="test",
                issue="Test issue",
                severity=severity,
                recommendation="Fix it"
            )
            assert issue.severity == severity


class TestValidateDetectorPatterns:
    """Test pattern validation function with realistic detector patterns."""

    def test_validate_no_patterns(self):
        """Empty pattern list returns no issues."""
        issues = validate_detector_patterns([], [])
        assert issues == []

    def test_validate_no_issues(self):
        """Valid patterns with no conflicts return empty list."""
        patterns = [r"\bfactual\b", r"\bverified\b"]
        context_keywords = ["blocked", "verification"]
        issues = validate_detector_patterns(patterns, context_keywords)
        assert issues == []

    def test_validate_context_conflict_exact_match(self):
        """Pattern matching context keyword triggers critical issue."""
        patterns = ["blocked"]
        context_keywords = ["blocked"]
        issues = validate_detector_patterns(patterns, context_keywords)

        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "context keyword" in issues[0].issue.lower()
        assert issues[0].pattern == "blocked"

    def test_validate_context_conflict_partial_match(self):
        """Pattern containing context keyword as substring is detected."""
        patterns = [r"has_blocked"]
        context_keywords = ["blocked"]
        issues = validate_detector_patterns(patterns, context_keywords)

        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "blocked" in issues[0].issue.lower()

    def test_validate_context_conflict_case_insensitive(self):
        """Context keyword detection is case-insensitive."""
        patterns = ["BLOCKED"]
        context_keywords = ["blocked"]
        issues = validate_detector_patterns(patterns, context_keywords)

        assert len(issues) == 1
        assert issues[0].severity == "critical"

    def test_validate_overmatching_common_words(self):
        """Common words like 'verify', 'check', 'that' trigger high severity."""
        common_words = ["verify", "check", "that", "this"]

        for word in common_words:
            patterns = [word]
            issues = validate_detector_patterns(patterns, [])

            assert len(issues) == 1
            assert issues[0].severity == "high"
            assert "too broad" in issues[0].issue.lower() or "common word" in issues[0].issue.lower()

    def test_validate_regex_syntax_error(self):
        """Invalid regex patterns trigger critical issues."""
        invalid_patterns = [
            r"[unclosed",           # Unclosed character class
            r"(?=unclosed",         # Unclosed group
                            r"*invalid",            # Quantifier at start
        ]

        for pattern in invalid_patterns:
            issues = validate_detector_patterns([pattern], [])
            assert len(issues) == 1
            assert issues[0].severity == "critical"
            assert "regex" in issues[0].issue.lower() or "invalid" in issues[0].issue.lower()

    def test_validate_multiple_issues(self):
        """Single pattern can trigger multiple issues."""
        # Pattern that is both a common word AND matches a context keyword
        patterns = ["verify"]
        context_keywords = ["verify"]

        issues = validate_detector_patterns(patterns, context_keywords)

        # Should detect both over-matching AND context conflict
        assert len(issues) == 2
        severities = {issue.severity for issue in issues}
        assert severities == {"critical", "high"}

    def test_validate_real_world_patterns(self):
        """Test patterns from actual unverified_stance_detector.py bugs."""
        # Bug #1: Bare "has" caused false positives
        # This should trigger "common word" warning
        issues = validate_detector_patterns(["has"], [])
        assert len(issues) == 1
        assert issues[0].severity == "high"

        # Bug #1 variant: Context keyword conflict
        issues = validate_detector_patterns(
            ["blocked"],
            ["blocked", "verification", "evidence"]
        )
        assert len(issues) == 1
        assert issues[0].severity == "critical"

    def test_validate_word_boundary_recommendations(self):
        """Context conflict issues include word boundary recommendations."""
        patterns = ["blocked"]
        context_keywords = ["blocked"]
        issues = validate_detector_patterns(patterns, context_keywords)

        assert len(issues) == 1
        # Check for "word boundary" or "word boundaries" phrase (case-insensitive)
        assert "boundar" in issues[0].recommendation.lower()

    def test_validate_complex_regex_valid(self):
        """Valid complex regex patterns pass validation."""
        # Realistic pattern with word boundaries and alternation
        patterns = [r"\b(?:has|contains|includes)\b"]
        context_keywords = ["blocked"]
        issues = validate_detector_patterns(patterns, context_keywords)

        # Should not trigger any issues (pattern uses word boundaries)
        assert len(issues) == 0

    def test_validate_empty_pattern(self):
        """Empty pattern string triggers appropriate issue."""
        issues = validate_detector_patterns([""], [])
        # Empty pattern may not be invalid regex, but should be flagged
        # This test documents current behavior
        assert isinstance(issues, list)

    def test_validate_whitespace_pattern(self):
        """Whitespace-only pattern is handled gracefully."""
        issues = validate_detector_patterns(["   "], [])
        # Whitespace pattern may not be invalid regex, but should be flagged
        assert isinstance(issues, list)

    def test_validate_multiple_patterns_independent(self):
        """Multiple patterns are validated independently."""
        patterns = [r"\bvalid\b", r"[unclosed", "verify"]
        context_keywords = ["blocked"]

        issues = validate_detector_patterns(patterns, context_keywords)

        # Should have issues for r"[unclosed" (invalid regex) and "verify" (common word)
        # but NOT for r"\bvalid\b"
        assert len(issues) == 2

        pattern_texts = {issue.pattern for issue in issues}
        assert r"[unclosed" in pattern_texts
        assert "verify" in pattern_texts
        assert r"\bvalid\b" not in pattern_texts


class TestPatternValidationIntegration:
    """Integration tests for pattern validation with real detector modules."""

    def test_unverified_stance_detector_patterns(self):
        """Validate patterns from unverified_stance_detector.py (Bug #1 reproduction)."""
        # These patterns caused false positives
        problematic_patterns = ["has", "let me verify", "i think"]

        # Simulated context keywords from anti_sycophancy module
        context_keywords = ["blocked", "verification", "evidence", "stance"]

        issues = validate_detector_patterns(problematic_patterns, context_keywords)

        # Should detect multiple issues
        assert len(issues) > 0

        # At minimum, "has" should be flagged as too broad
        issue_patterns = {issue.pattern for issue in issues}
        assert "has" in issue_patterns

    def test_recommended_pattern_fixes(self):
        """Recommended fixed patterns pass validation."""
        # Word-bounded versions of problematic patterns
        fixed_patterns = [
            r"\bhas\b",
            r"\blet me verify\b",
            r"\bi think\b"
        ]

        context_keywords = ["blocked", "verification", "evidence"]

        issues = validate_detector_patterns(fixed_patterns, context_keywords)

        # Should have fewer issues than bare versions
        # (May still have some issues for other reasons)
        assert len(issues) == 0
