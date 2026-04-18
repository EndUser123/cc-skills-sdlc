"""
Practicality Filter for Unified Code Inspection

Filters findings based on solo-dev practicality and feasibility.
Assesses time, complexity, dependencies, and testing overhead.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class PracticalityAssessment:
    """Result of practicality assessment for a finding."""
    is_practical: bool
    time_estimate: str  # e.g., "5 minutes", "2 hours", "1 day"
    complexity: str  # e.g., "trivial", "moderate", "complex"
    blockers: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)


@dataclass
class FilterResult:
    """Result of practicality filtering."""
    practical_findings: List[Dict[str, Any]]
    impractical_findings: List[Dict[str, Any]]
    filtered_count: int = 0
    filter_reasons: Dict[str, int] = field(default_factory=dict)


class PracticalityFilter:
    """
    Filters findings based on solo-dev practicality.

    Solo-dev practicality considerations:
    1. Time Constraints (90% confidence)
       - Trivial fixes: < 15 minutes
       - Moderate fixes: 15-60 minutes
       - Complex fixes: > 1 hour may require reconsideration

    2. Solo-Dev Constraints (95% confidence)
       - No team coordination required
       - No external approvals needed
       - Can be tested independently

    3. Tool Availability (80% confidence)
       - Required tools available in environment
       - No complex infrastructure setup required
       - Testing can be done locally

    4. Testing Overhead (85% confidence)
       - Testing can be done in reasonable time
       - No complex test data setup required
       - No integration with external systems needed
    """

    # Time thresholds for practicality
    TIME_THRESHOLDS = {
        "trivial": 15,      # 15 minutes
        "moderate": 60,     # 1 hour
        "complex": 480       # 8 hours (full work day)
    }

    # Impractical patterns that filter out findings
    IMPRACTICAL_PATTERNS = [
        "requires team coordination",
        "requires stakeholder approval",
        "requires cross-team coordination",
        "requires external service setup",
        "requires infrastructure provision",
        "requires complex test data setup",
        "requires integration with external system",
        "requires enterprise license",
    ]

    # Allowed categories that are generally practical
    PRACTICAL_CATEGORIES = [
        "logic", "testing", "security", "performance", "conventions",
        "quality", "compliance", "qa", "simplification", "rca",
        "failure-modes", "deployment", "modernization", "test-quality",
        "spec", "schema", "validation", "error", "async", "race",
        "resource", "maintainability", "coverage", "type", "syntax",
        "stdlib", "anti-pattern", "observability", "rollback",
        "infrastructure", "runtime", "migration"
    ]

    def __init__(self, max_time_minutes: int = 480):
        """
        Initialize practicality filter.

        Args:
            max_time_minutes: Maximum time (in minutes) considered practical
        """
        self.max_time_minutes = max_time_minutes

    def filter_findings(
        self,
        findings: List[Dict[str, Any]]
    ) -> FilterResult:
        """
        Filter findings based on solo-dev practicality.

        Args:
            findings: List of findings to filter

        Returns:
            FilterResult with practical_findings, impractical_findings, and stats
        """
        practical = []
        impractical = []
        reasons = {}

        for finding in findings:
            assessment = self._assess_practicality(finding)

            if assessment.is_practical:
                # Add practicality metadata to finding
                finding["_practicality"] = {
                    "time_estimate": assessment.time_estimate,
                    "complexity": assessment.complexity,
                }
                practical.append(finding)
            else:
                # Add to impractical with reasons
                finding["_impractical"] = {
                    "time_estimate": assessment.time_estimate,
                    "complexity": assessment.complexity,
                    "blockers": assessment.blockers,
                    "alternatives": assessment.alternatives,
                }
                impractical.append(finding)

                # Track reasons
                for blocker in assessment.blockers:
                    reasons[blocker] = reasons.get(blocker, 0) + 1

        return FilterResult(
            practical_findings=practical,
            impractical_findings=impractical,
            filtered_count=len(impractical),
            filter_reasons=reasons
        )

    def _assess_practicality(self, finding: Dict[str, Any]) -> PracticalityAssessment:
        """
        Assess whether a finding is practical for solo-dev implementation.

        Args:
            finding: Finding to assess

        Returns:
            PracticalityAssessment with practicality judgment and details
        """
        problem = finding.get("problem", "").lower()
        recommendation = finding.get("recommendation", "").lower()
        category = finding.get("category", "general").lower()

        # Check for impractical patterns
        blockers = []
        alternatives = []

        for pattern in self.IMRACTICAL_PATTERNS:
            if pattern in problem or pattern in recommendation:
                blockers.append(f"Impractical pattern: '{pattern}'")
                alternatives.append(self._suggest_alternative(pattern))

        # Assess time requirement from recommendation
        time_estimate = self._estimate_time(recommendation)
        complexity = self._assess_complexity(time_estimate)

        # Determine if practical
        is_practical = (
            len(blockers) == 0 and
            time_estimate <= self.max_time_minutes
        )

        return PracticalityAssessment(
            is_practical=is_practical,
            time_estimate=self._format_time(time_estimate),
            complexity=complexity,
            blockers=blockers,
            alternatives=alternatives
        )

    def _estimate_time(self, text: str) -> int:
        """
        Estimate time (in minutes) from recommendation text.

        Args:
            text: Recommendation text to parse

        Returns:
            Estimated time in minutes
        """
        # Look for time-related keywords
        time_keywords = {
            "5 minutes": 5,
            "10 minutes": 10,
            "15 minutes": 15,
            "30 minutes": 30,
            "1 hour": 60,
            "2 hours": 120,
            "half hour": 30,
            "couple hours": 120,
            "few hours": 180,
            "several hours": 240,
            "1 day": 480,
            "2 days": 960,
            "quick": 10,
            "trivial": 5,
            "simple": 15,
            "complex": 120,
            "major": 240,
        }

        text_lower = text.lower()

        for keyword, minutes in time_keywords.items():
            if keyword in text_lower:
                return minutes

        # Default estimation based on recommendation length
        # Short recommendations (< 50 chars) = trivial
        # Medium (50-200 chars) = moderate
        # Long (> 200 chars) = complex
        if len(text) < 50:
            return self.TIME_THRESHOLDS["trivial"]
        elif len(text) < 200:
            return self.TIME_THRESHOLDS["moderate"]
        else:
            return self.TIME_THRESHOLDS["complex"]

    def _assess_complexity(self, time_minutes: int) -> str:
        """
        Assess complexity level based on time estimate.

        Args:
            time_minutes: Estimated time in minutes

        Returns:
            Complexity level (trivial/moderate/complex)
        """
        if time_minutes <= self.TIME_THRESHOLDS["trivial"]:
            return "trivial"
        elif time_minutes <= self.TIME_THRESHOLDS["moderate"]:
            return "moderate"
        else:
            return "complex"

    def _format_time(self, minutes: int) -> str:
        """
        Format time estimate for display.

        Args:
            minutes: Time in minutes

        Returns:
            Formatted time string
        """
        if minutes < 60:
            return f"{minutes} minutes"
        elif minutes < 480:
            hours = minutes // 60
            return f"{hours} hour{'s' if hours > 1 else ''}"
        else:
            days = minutes // 480
            return f"{days} day{'s' if days > 1 else ''}"

    def _suggest_alternative(self, pattern: str) -> str:
        """
        Suggest alternative approach for impractical pattern.

        Args:
            pattern: Impractical pattern found

        Returns:
            Alternative suggestion
        """
        alternatives = {
            "requires team coordination": "Consider reworking to avoid coordination",
            "requires stakeholder approval": "Document decision rationale instead",
            "requires cross-team coordination": "Reduce scope to single-team effort",
            "requires external service setup": "Use mock/local alternative for development",
            "requires infrastructure provision": "Document infra requirements for later",
            "requires complex test data setup": "Simplify test data or use factories",
            "requires integration with external system": "Design integration point for later",
            "requires enterprise license": "Use open-source alternative",
        }

        return alternatives.get(pattern, "See if requirement can be relaxed")


def create_practicality_filter(max_time_minutes: int = 480) -> PracticalityFilter:
    """
    Factory function to create a practicality filter.

    Args:
        max_time_minutes: Maximum time considered practical (default: 8 hours)

    Returns:
        PracticalityFilter instance
    """
    return PracticalityFilter(max_time_minutes=max_time_minutes)


# Convenience functions for common use cases
def filter_practical_findings(
    findings: List[Dict[str, Any]],
    max_time_minutes: int = 480
) -> FilterResult:
    """
    Filter findings based on solo-dev practicality.

    Convenience function that creates filter and applies it.

    Args:
        findings: List of findings to filter
        max_time_minutes: Maximum time considered practical

    Returns:
        FilterResult with practical findings and filter stats
    """
    filter_obj = create_practicality_filter(max_time_minutes)
    return filter_obj.filter_findings(findings)


def assess_finding_practicality(finding: Dict[str, Any]) -> PracticalityAssessment:
    """
    Assess practicality of a single finding.

    Args:
        finding: Finding to assess

    Returns:
        PracticalityAssessment with practicality judgment
    """
    filter_obj = create_practicality_filter()
    return filter_obj._assess_practicality(finding)
