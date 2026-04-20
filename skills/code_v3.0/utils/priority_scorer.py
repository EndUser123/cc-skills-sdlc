"""Priority scoring utility for code findings.

This module provides priority categorization (P0/P1/P2) and confidence scoring
for code analysis findings. Priorities are RECOMMENDATIONS for triage and
attention management, never hard blocks on workflow execution.

Priority Levels:
- P0 (Critical): Security vulnerabilities, breaking API changes, data loss risks
- P1 (High): Major performance improvements, deprecated features, compatibility issues
- P2 (Medium): Minor improvements, cosmetic changes, nice-to-have enhancements

Scoring:
- Priority scores range from 0.0-1.0 based on type and severity
- Confidence scores range from 0.0-1.0 based on evidence strength
- Higher scores indicate higher priority or stronger evidence

Usage:
    finding = {"type": "security", "severity": "high", "description": "SQL injection"}
    result = calculate_priority(finding)
    # Returns PriorityScore(priority=PriorityLevel.P0, score=0.9, confidence=0.7)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


# Constants for confidence scoring
_BASE_CONFIDENCE = 0.5
_EVIDENCE_BONUS = 0.15
_MULTI_EVIDENCE_BONUS = 0.15
_REPRODUCIBLE_BONUS = 0.1
_VERIFIED_BONUS = 0.1
_DETAILED_DESCRIPTION_BONUS = 0.1
_DETAILED_DESCRIPTION_THRESHOLD = 50
_MULTI_EVIDENCE_THRESHOLD = 2

# Constants for priority scoring
_P0_SCORE = 0.9
_P1_SCORE = 0.65
_P2_SCORE = 0.35


class PriorityLevel(Enum):
    """Priority levels for code findings.

    P0: Critical issues requiring immediate attention
    P1: High-priority issues for next available iteration
    P2: Medium-priority issues for backlog consideration
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


@dataclass
class PriorityScore:
    """Priority and confidence score for a finding.

    Attributes:
        priority: Priority level (P0/P1/P2)
        score: Priority score from 0.0-1.0 (higher = more priority)
        confidence: Confidence score from 0.0-1.0 (higher = stronger evidence)
    """

    priority: PriorityLevel
    score: float
    confidence: float


def _extract_finding_attributes(finding: Dict[str, Any]) -> tuple[str, str, str]:
    """Extract and normalize finding attributes for categorization.

    Args:
        finding: Dictionary containing finding metadata

    Returns:
        Tuple of (finding_type, severity, impact) as lowercase strings
    """
    finding_type = finding.get("type", "").lower()
    severity = finding.get("severity", "").lower()
    impact = finding.get("impact", "").lower()
    return finding_type, severity, impact


def _is_critical_issue(finding_type: str, severity: str, impact: str) -> bool:
    """Check if finding represents a critical (P0) issue.

    Args:
        finding_type: Normalized finding type
        severity: Normalized severity level
        impact: Normalized impact level

    Returns:
        True if finding is P0-critical
    """
    if finding_type == "security" and severity in ("high", "critical"):
        return True
    if finding_type == "api" and severity == "breaking":
        return True
    if finding_type == "data" and severity == "high":
        return True
    return False


def _is_high_priority_issue(finding_type: str, severity: str, impact: str) -> bool:
    """Check if finding represents a high-priority (P1) issue.

    Args:
        finding_type: Normalized finding type
        severity: Normalized severity level
        impact: Normalized impact level

    Returns:
        True if finding is P1-high-priority
    """
    if finding_type == "performance" and impact in ("high", "medium"):
        return True
    if finding_type == "deprecation" and severity == "high":
        return True
    if finding_type == "compatibility" and severity in ("medium", "high"):
        return True
    return False


def categorize_finding(finding: Dict[str, Any]) -> PriorityLevel:
    """Categorize a finding into P0/P1/P2 based on type and severity.

    Args:
        finding: Dictionary containing finding metadata with keys like
                 'type', 'severity', 'impact', 'description'

    Returns:
        PriorityLevel: P0, P1, or P2 based on categorization rules

    Categorization Rules:
        P0 (Critical):
        - Security vulnerabilities (type="security" with severity="high" or "critical")
        - Breaking API changes (type="api" with severity="breaking")
        - Data loss risks (type="data" with severity="high")

        P1 (High):
        - Performance improvements (type="performance" with impact="high" or "medium")
        - Deprecated features (type="deprecation" with severity="high")
        - Compatibility issues (type="compatibility" with severity="medium" or "high")

        P2 (Medium):
        - Minor improvements (type="improvement")
        - Cosmetic changes (type="cosmetic")
        - Unknown types (defaults to P2 for graceful degradation)
        - Missing type field (defaults to P2 for graceful degradation)
    """
    finding_type, severity, impact = _extract_finding_attributes(finding)

    if _is_critical_issue(finding_type, severity, impact):
        return PriorityLevel.P0

    if _is_high_priority_issue(finding_type, severity, impact):
        return PriorityLevel.P1

    # P2: Medium-priority issues (including unknown types)
    return PriorityLevel.P2


def _calculate_priority_score(priority: PriorityLevel) -> float:
    """Calculate numeric score based on priority level.

    Args:
        priority: Priority level (P0/P1/P2)

    Returns:
        Score in 0.0-1.0 range based on priority
    """
    if priority == PriorityLevel.P0:
        return _P0_SCORE
    elif priority == PriorityLevel.P1:
        return _P1_SCORE
    else:  # P2
        return _P2_SCORE


def _calculate_confidence_score(finding: Dict[str, Any]) -> float:
    """Calculate confidence score based on evidence strength.

    Args:
        finding: Dictionary containing finding metadata

    Returns:
        Confidence score in 0.0-1.0 range

    Confidence Calculation:
        Base confidence: 0.5
        +0.15 for evidence list present
        +0.15 for multiple evidence items (>2)
        +0.1 for reproducible flag
        +0.1 for verified flag
        +0.1 for detailed description (>50 chars)
        Maximum confidence: 1.0
    """
    confidence = _BASE_CONFIDENCE

    # Check for evidence fields
    if "evidence" in finding:
        evidence = finding["evidence"]
        if isinstance(evidence, list) and len(evidence) > 0:
            confidence += _EVIDENCE_BONUS
            if len(evidence) > _MULTI_EVIDENCE_THRESHOLD:
                confidence += _MULTI_EVIDENCE_BONUS

    # Check verification flags
    if finding.get("reproducible", False) is True:
        confidence += _REPRODUCIBLE_BONUS

    if finding.get("verified", False) is True:
        confidence += _VERIFIED_BONUS

    # Check for detailed description
    description = finding.get("description", "")
    if len(description) > _DETAILED_DESCRIPTION_THRESHOLD:
        confidence += _DETAILED_DESCRIPTION_BONUS

    # Clamp confidence to 0.0-1.0 range
    return round(min(max(confidence, 0.0), 1.0), 2)


def calculate_priority(finding: Dict[str, Any]) -> PriorityScore:
    """Calculate priority score and confidence for a finding.

    Args:
        finding: Dictionary containing finding metadata

    Returns:
        PriorityScore with priority level, score (0.0-1.0), and confidence (0.0-1.0)

    Scoring Rules:
        P0 scores: 0.8-1.0 (critical issues)
        P1 scores: 0.5-0.79 (high-priority issues)
        P2 scores: 0.2-0.49 (medium-priority issues)

    Confidence Scoring:
        Base confidence: 0.5
        +0.15 for evidence list present
        +0.15 for multiple evidence items (>2 in list)
        +0.1 for each verification flag (reproducible, verified)
        +0.1 for detailed description (>50 chars)
        Maximum confidence: 1.0
    """
    priority = categorize_finding(finding)
    score = _calculate_priority_score(priority)
    confidence = _calculate_confidence_score(finding)

    return PriorityScore(priority=priority, score=score, confidence=confidence)
