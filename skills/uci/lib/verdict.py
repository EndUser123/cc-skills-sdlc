"""
Three-Tier Verdict Synthesis for Unified Code Inspection

Verdict calculator:
- Ready to Merge: No blockers/high, tests pass
- Needs Attention: Medium issues worth addressing
- Needs Work: Blockers/high or failing tests
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Verdict(Enum):
    """Three-tier verdict levels."""
    READY_TO_MERGE = "Ready to Merge"
    NEEDS_ATTENTION = "Needs Attention"
    NEEDS_WORK = "Needs Work"


def synthesize_verdict(
    findings: List[Dict[str, Any]],
    tests_pass: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Calculate three-tier verdict from findings.

    Args:
        findings: List of finding dicts with severity field
        tests_pass: Whether tests pass (None = unknown)

    Returns:
        Verdict dict with verdict, reason, counts, next_steps

    Examples:
        >>> synthesize_verdict([{"severity": "high"}], tests_pass=True)
        {
            "verdict": "Needs Attention",
            "reason": "1 high severity issue found",
            "blockers": 0,
            "high": 1,
            "medium": 0,
            "low": 0,
            "next_steps": ["Address high severity issue before merge"]
        }

        >>> synthesize_verdict([], tests_pass=True)
        {
            "verdict": "Ready to Merge",
            "reason": "No issues found, tests passing",
            "blockers": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "next_steps": []
        }
    """
    # Count findings by severity
    blockers = 0
    high = 0
    medium = 0
    low = 0

    for finding in findings:
        severity = finding.get("severity", "").lower()
        if "blocker" in severity:
            blockers += 1
        elif "high" in severity or "critical" in severity:
            high += 1
        elif "medium" in severity or "med" in severity:
            medium += 1
        elif "low" in severity:
            low += 1

    # Determine verdict
    verdict, reason, next_steps = _determine_verdict(
        blockers, high, medium, low, tests_pass
    )

    return {
        "verdict": verdict,
        "reason": reason,
        "blockers": blockers,
        "high": high,
        "medium": medium,
        "low": low,
        "next_steps": next_steps
    }


def _determine_verdict(
    blockers: int,
    high: int,
    medium: int,
    low: int,
    tests_pass: Optional[bool]
) -> tuple[str, str, List[str]]:
    """
    Determine verdict level from severity counts.

    Returns:
        Tuple of (verdict, reason, next_steps)
    """
    # Needs Work: Blockers or high issues or failing tests
    if blockers > 0 or high > 0 or (tests_pass is False):
        verdict = Verdict.NEEDS_WORK
        issues = []
        if blockers > 0:
            issues.append(f"{blockers} blocker issue(s)")
        if high > 0:
            issues.append(f"{high} high severity issue(s)")
        if tests_pass is False:
            issues.append("failing tests")

        reason = ", ".join(issues) + " found"
        next_steps = [
            "Must fix all blocker and high severity issues",
            "Ensure all tests pass before merge"
        ]
        return verdict.value, reason, next_steps

    # Needs Attention: Medium issues present
    if medium > 0:
        verdict = Verdict.NEEDS_ATTENTION
        reason = f"{medium} medium issue(s) worth addressing"
        next_steps = [
            "Address medium issues if time permits",
            "Consider fixing before merge for quality"
        ]
        return verdict.value, reason, next_steps

    # Ready to Merge: No blockers/high, tests pass (or unknown)
    verdict = Verdict.READY_TO_MERGE
    if low > 0:
        reason = f"No critical issues ({low} low severity finding(s))"
        next_steps = ["Optional: address low severity issues"]
    else:
        reason = "No issues found"
        next_steps = []

    if tests_pass is False:
        # Tests unknown but failing is not a blocker for Ready to Merge
        next_steps.append("Note: Test status unknown, verify tests pass")

    return verdict.value, reason, next_steps


def format_verdict_summary(verdict_dict: Dict[str, Any]) -> str:
    """Format verdict dict for display."""
    verdict = verdict_dict["verdict"]
    reason = verdict_dict["reason"]
    blockers = verdict_dict["blockers"]
    high = verdict_dict["high"]
    medium = verdict_dict["medium"]

    summary = f"### Verdict: {verdict}\n"
    summary += f"**Reason**: {reason}\n\n"

    if blockers > 0 or high > 0 or medium > 0:
        summary += "**Issue Summary**:\n"
        if blockers > 0:
            summary += f"- Blockers: {blockers}\n"
        if high > 0:
            summary += f"- High: {high}\n"
        if medium > 0:
            summary += f"- Medium: {medium}\n"
        summary += "\n"

    if verdict_dict["next_steps"]:
        summary += "**Next Steps**:\n"
        for step in verdict_dict["next_steps"]:
            summary += f"- {step}\n"

    return summary
