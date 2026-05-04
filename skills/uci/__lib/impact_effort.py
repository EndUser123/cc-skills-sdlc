"""
Impact/Effort Matrix Calculation for Unified Code Inspection

Auto-calculates impact and effort levels from findings to help prioritize fixes.
- Impact: HIGH (crashes, data loss, security) / MEDIUM (degraded UX) / LOW (style)
- Effort: HIGH (days, complex refactor) / MEDIUM (hours) / LOW (minutes, simple fix)
"""

import logging
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Level(Enum):
    """Impact/Effort levels."""
    HIGH = "HIGH"
    MEDIUM = "MED"
    LOW = "LOW"


def calculate_impact_effort(finding: Dict[str, Any]) -> tuple[Level, Level]:
    """
    Auto-calculate impact and effort levels from a finding.

    Args:
        finding: Finding dict with fields like severity, problem, recommendation

    Returns:
        Tuple of (impact_level, effort_level)

    Examples:
        >>> calculate_impact_effort({
        ...     "severity": "blocker",
        ...     "problem": "user_token can be None causing crash",
        ...     "recommendation": "Add null check"
        ... })
        (Level.HIGH, Level.LOW)

        >>> calculate_impact_effort({
        ...     "severity": "low",
        ...     "problem": "Long variable name",
        ...     "recommendation": "Rename to shorter name"
        ... })
        (Level.LOW, Level.LOW)
    """
    impact = _calculate_impact(finding)
    effort = _calculate_effort(finding)
    return impact, effort


def _calculate_impact(finding: Dict[str, Any]) -> Level:
    """Calculate impact level from severity and problem description."""
    severity = finding.get("severity", "").lower()
    problem = finding.get("problem", "").lower()
    impact_desc = finding.get("impact_description", "").lower()

    # HIGH impact indicators
    high_indicators = [
        "crash", "runtime error", "exception", "data loss", "security",
        "injection", "vulnerability", "leak", "corruption", "race",
        "deadlock", "blocker", "critical", "auth", "permission", "access"
    ]

    # Check severity first
    if severity in ["blocker", "critical", "high"]:
        return Level.HIGH
    elif severity in ["medium", "med"]:
        # Medium severity might still be HIGH impact based on problem
        if any(indicator in problem or impact_desc for indicator in high_indicators):
            return Level.HIGH
        return Level.MEDIUM
    else:
        # Low severity
        if any(indicator in problem or impact_desc for indicator in high_indicators):
            return Level.MEDIUM
        return Level.LOW


def _calculate_effort(finding: Dict[str, Any]) -> Level:
    """Calculate effort level from recommendation complexity."""
    recommendation = finding.get("recommendation", "").lower()

    # HIGH effort indicators (days, complex refactors)
    high_effort_indicators = [
        "refactor", "redesign", "rework", "rewrite", "architecture",
        "migration", "schema change", "database", "api change",
        "multi-file", "cross-module", "layer", "framework", "days"
    ]

    # LOW effort indicators (minutes, simple fixes)
    low_effort_indicators = [
        "add null check", "rename", "typo", "indent", "format",
        "comment", "import", "remove unused", "delete line",
        "minute", "simple", "trivial", "one-line", "quick fix"
    ]

    # Check for HIGH effort first
    if any(indicator in recommendation for indicator in high_effort_indicators):
        return Level.HIGH

    # Check for LOW effort
    if any(indicator in recommendation for indicator in low_effort_indicators):
        return Level.LOW

    # Check recommendation length as proxy
    word_count = len(recommendation.split())
    if word_count > 30:
        return Level.HIGH
    elif word_count > 10:
        return Level.MEDIUM
    else:
        return Level.LOW


def impact_effort_to_score(impact: Level, effort: Level) -> int:
    """
    Calculate priority score from impact/effort levels.

    Higher score = higher priority (should fix first).
    Quick wins (HIGH impact, LOW effort) get highest score.

    Scoring:
    - HIGH impact + LOW effort = 9 (quick win)
    - HIGH impact + MED effort = 6
    - HIGH impact + HIGH effort = 3
    - MED impact + LOW effort = 8
    - MED impact + MED effort = 5
    - MED impact + HIGH effort = 2
    - LOW impact + LOW effort = 7
    - LOW impact + MED effort = 4
    - LOW impact + HIGH effort = 1 (skip)

    Args:
        impact: Impact level
        effort: Effort level

    Returns:
        Priority score (1-9, higher = more important)
    """
    impact_scores = {Level.HIGH: 3, Level.MEDIUM: 2, Level.LOW: 1}
    effort_scores = {Level.HIGH: 1, Level.MEDIUM: 2, Level.LOW: 3}

    return impact_scores[impact] * 3 - effort_scores[effort] + 1


def format_impact_effort(impact: Level, effort: Level) -> str:
    """Format impact/effort for display."""
    return f"[{impact.value} Impact, {effort.value} Effort]"


def sort_findings_by_priority(findings: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Sort findings by priority score (highest first).

    Args:
        findings: List of finding dicts

    Returns:
        Sorted list of findings (highest priority first)
    """
    def get_priority_score(finding: Dict[str, Any]) -> int:
        impact_str = finding.get("impact", "")
        effort_str = finding.get("effort", "")

        # Parse level from string
        impact = Level.HIGH
        if "MED" in impact_str.upper():
            impact = Level.MEDIUM
        elif "LOW" in impact_str.upper():
            impact = Level.LOW

        effort = Level.HIGH
        if "MED" in effort_str.upper():
            effort = Level.MEDIUM
        elif "LOW" in effort_str.upper():
            effort = Level.LOW

        return impact_effort_to_score(impact, effort)

    return sorted(findings, key=get_priority_score, reverse=True)
