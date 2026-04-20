#!/usr/bin/env python3
"""Adversarial review of refactoring plans.

Reviews refactoring plans for risks, complexity, dependencies,
and suggests alternatives before any code is changed.
"""

from __future__ import annotations

from typing import Any


def adversarial_review_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Perform adversarial review on a refactoring plan.

    Reviews the plan for:
    - Missing risk analysis
    - Overly complex changes
    - Dependency conflicts
    - Insufficient rollback strategy
    - Better alternatives (AST vs regex, etc.)

    Args:
        plan: Structured refactoring plan

    Returns:
        Review findings with recommendations
    """
    findings = []
    recommendations = []
    risk_factors = []

    # Review each change
    all_changes = []
    for priority in ["P0", "P1", "P2", "P3"]:
        if priority in plan["changes_by_priority"]:
            all_changes.extend(plan["changes_by_priority"][priority])

    for change in all_changes:
        change_findings = _review_change(change)
        if change_findings:
            findings.extend(change_findings)

    # Review overall strategy
    strategy_findings = _review_strategy(plan)
    findings.extend(strategy_findings)

    # Assess overall risk factors
    risk_factors = _assess_plan_risks(plan, findings)

    # Generate recommendations
    recommendations = _generate_recommendations(plan, findings)

    return {
        "findings": findings,
        "recommendations": recommendations,
        "risk_factors": risk_factors,
        "overall_assessment": _overall_assessment(plan, findings),
    }


def _review_change(change: dict[str, Any]) -> list[str]:
    """Review a single change for issues.

    Args:
        change: Single change from plan

    Returns:
        List of finding strings
    """
    findings = []
    change_id = change.get("id", "unknown")
    title = change.get("title", "")
    file_path = change.get("file", "")

    # Check for regex-based refactoring risks
    if "regex" in title.lower() and change.get("risk_analysis", "").startswith("LOW"):
        findings.append(
            f"RISK-001: {change_id} uses regex but marked as LOW risk. "
            f"Regex refactoring can introduce syntax errors. "
            f"Consider AST-based refactoring instead."
        )

    # Check for missing rollback strategy
    rollback = change.get("rollback_strategy", "")
    if "rollback" not in rollback.lower() and "revert" not in rollback.lower():
        findings.append(
            f"ROLLBACK-001: {change_id} has insufficient rollback strategy. "
            f"Specify git commit or characterization test approach."
        )

    # Check for batch operations
    if "batch" in title.lower() or "consolidate" in title.lower():
        findings.append(
            f"COMPLEX-001: {change_id} is a batch operation. "
            f"Batch changes increase risk. Consider splitting into smaller increments."
        )

    # Check for import changes
    if "import" in title.lower():
        findings.append(
            f"IMPORT-001: {change_id} changes imports. "
            f"Import changes can break module loading. Test import order carefully."
        )

    return findings


def _review_strategy(plan: dict[str, Any]) -> list[str]:
    """Review overall refactoring strategy.

    Args:
        plan: Structured refactoring plan

    Returns:
        List of finding strings
    """
    findings = []
    overview = plan["overview"]

    # Check total effort
    effort = overview.get("estimated_effort_hours", 0)
    if effort > 8:
        findings.append(
            f"EFFORT-001: Large refactoring ({effort} hours). "
            f"Consider splitting into multiple sessions to reduce risk."
        )

    # Check P0 count
    p0_count = overview.get("priority_breakdown", {}).get("P0", 0)
    if p0_count > 5:
        findings.append(
            f"PRIORITY-001: Many P0 issues ({p0_count}). "
            f"Fix critical bugs first, then refactor in a follow-up session."
        )

    # Check execution order
    execution_order = plan.get("execution_order", [])
    if len(execution_order) > 4:
        findings.append(
            f"COMPLEX-002: Complex execution order ({len(execution_order)} steps). "
            f"Simplify by grouping related changes."
        )

    return findings


def _assess_plan_risks(plan: dict[str, Any], findings: list[str]) -> list[str]:
    """Assess overall risk factors in the plan.

    Args:
        plan: Structured refactoring plan
        findings: List of review findings

    Returns:
        List of risk factor descriptions
    """
    risks = []
    overview = plan["overview"]

    # Count risk-related findings
    risk_findings = [f for f in findings if f.startswith(("RISK-", "COMPLEX-"))]
    if len(risk_findings) > 3:
        risks.append("HIGH: Multiple risk factors identified in plan")

    # Check effort vs risk
    effort = overview.get("estimated_effort_hours", 0)
    risk_level = overview.get("risk_level", "unknown")
    if effort > 4 and risk_level == "low":
        risks.append("MEDIUM: Effort high but risk marked low - review risk assessment")

    # Check for batch operations
    all_changes = []
    for priority in ["P0", "P1", "P2", "P3"]:
        if priority in plan["changes_by_priority"]:
            all_changes.extend(plan["changes_by_priority"][priority])

    batch_count = sum(1 for c in all_changes if "batch" in c.get("title", "").lower())
    if batch_count > 0:
        risks.append(f"HIGH: {batch_count} batch operation(s) planned - high syntax error risk")

    return risks


def _generate_recommendations(plan: dict[str, Any], findings: list[str]) -> list[str]:
    """Generate recommendations based on findings.

    Args:
        plan: Structured refactoring plan
        findings: List of review findings

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Check for regex recommendations
    regex_findings = [f for f in findings if "regex" in f.lower() and "ast" in f.lower()]
    if regex_findings:
        recommendations.append(
            "Use AST-based refactoring (LibCST) instead of regex for function signature changes. "
            "See P:/packages/refactor/AST_HELPERS_GUIDE.md for API documentation."
        )

    # Check for batch operation recommendations
    batch_findings = [f for f in findings if "batch" in f.lower()]
    if batch_findings:
        recommendations.append(
            "Split batch operations into smaller increments with validation between each step. "
            "Use the validation template: P:/.claude/consolidation_template.py"
        )

    # Check for large refactoring
    effort = plan["overview"].get("estimated_effort_hours", 0)
    if effort > 4:
        recommendations.append(
            f"Consider splitting into {int(effort / 2) + 1} smaller sessions "
            f"to reduce risk and improve testability."
        )

    # Default recommendation if no specific findings
    if not recommendations and not findings:
        recommendations.append(
            "Plan looks reasonable. Proceed with RED phase (create characterization tests)."
        )

    return recommendations


def _overall_assessment(plan: dict[str, Any], findings: list[str]) -> str:
    """Generate overall assessment of the plan.

    Args:
        plan: Structured refactoring plan
        findings: List of review findings

    Returns:
        Overall assessment string
    """
    overview = plan["overview"]

    if len(findings) == 0:
        return "✅ **APPROVED**: Plan is well-structured with clear risks and rollback strategies."

    risk_count = len([f for f in findings if f.startswith(("RISK-", "COMPLEX-", "EFFORT-"))])

    if risk_count > 3:
        return (
            "⚠️ **CONDITIONAL**: Plan has significant risk factors. "
            "Address high-risk findings before proceeding, or split into smaller sessions."
        )

    return (
        "⚠️ **ADVISED**: Plan has some concerns. "
        "Review findings and recommendations before proceeding."
    )


def review_to_markdown(review: dict[str, Any]) -> str:
    """Convert review dict to markdown format for display.

    Args:
        review: Adversarial review findings

    Returns:
        Markdown string
    """
    lines = []

    # Header
    lines.append("# Adversarial Review of Refactoring Plan")
    lines.append("")

    # Overall assessment
    lines.append("## Overall Assessment")
    lines.append("")
    lines.append(review["overall_assessment"])
    lines.append("")

    # Risk factors
    if review["risk_factors"]:
        lines.append("## Risk Factors")
        lines.append("")
        for risk in review["risk_factors"]:
            lines.append(f"- **{risk}**")
        lines.append("")

    # Findings
    if review["findings"]:
        lines.append("## Findings")
        lines.append("")
        for finding in review["findings"]:
            lines.append(f"- {finding}")
        lines.append("")

    # Recommendations
    if review["recommendations"]:
        lines.append("## Recommendations")
        lines.append("")
        for rec in review["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

    # No findings
    if not review["findings"] and not review["risk_factors"]:
        lines.append("## Findings")
        lines.append("")
        lines.append("No concerns identified. Plan is ready for RED phase.")
        lines.append("")

    return "\n".join(lines)
