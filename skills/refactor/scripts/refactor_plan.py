#!/usr/bin/env python3
"""Refactoring plan creation and management.

Creates structured refactoring plans from findings, tracks complexity,
risk, and rollback strategies for each change.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

# Synthesis module is optional — degrade gracefully if unavailable
if TYPE_CHECKING:
    from synthesize_findings import (
        calculate_health_score,
        group_by_severity,
    )
    _SYNTHESIS_AVAILABLE = True
else:
    try:
        from synthesize_findings import (
            calculate_health_score,
            group_by_severity,
        )
        _SYNTHESIS_AVAILABLE = True
    except ImportError:
        calculate_health_score = None  # type: ignore[assignment]
        group_by_severity = None  # type: ignore[assignment]
        _SYNTHESIS_AVAILABLE = False

# Priority → severity mapping for synthesis integration
# P0 (bugs/race conditions) → CRITICAL
# P1 (error handling)       → HIGH
# P2 (DRY violations)       → MEDIUM
# P3 (conventions)          → LOW
_PRIORITY_TO_SEVERITY = {
    "P0": "CRITICAL",
    "P1": "HIGH",
    "P2": "MEDIUM",
    "P3": "LOW",
}


def create_refactor_plan(
    findings: list[dict[str, Any]],
    target_path: str,
    session_id: str,
) -> dict[str, Any]:
    """Create a structured refactoring plan from findings.

    Args:
        findings: List of refactoring findings from discovery phase
        target_path: Path being refactored
        session_id: Current session ID

    Returns:
        Structured plan dict with overview, changes, execution order, validation
    """
    # Group findings by priority
    by_priority = {"P0": [], "P1": [], "P2": [], "P3": []}
    for finding in findings:
        priority = finding.get("priority", "P3")
        if priority in by_priority:
            by_priority[priority].append(finding)

    # Count findings
    total_findings = len(findings)
    priority_counts = {p: len(by_priority[p]) for p in by_priority}

    # Estimate effort (rough heuristic)
    effort_hours = sum(
        count * multiplier
        for count, multiplier in [
            (priority_counts["P0"], 2.0),  # Bugs take longer
            (priority_counts["P1"], 1.5),  # Error handling
            (priority_counts["P2"], 1.0),  # DRY
            (priority_counts["P3"], 0.5),  # Conventions
        ]
    )

    # Assess risk level
    risk_level = "low"
    if priority_counts["P0"] > 0:
        risk_level = "high"
    elif priority_counts["P1"] > 2 or total_findings > 10:
        risk_level = "medium"

    # Build plan
    plan = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "target_path": target_path,
            "session_id": session_id,
            "plan_version": 1,
        },
        "overview": {
            "total_findings": total_findings,
            "priority_breakdown": priority_counts,
            "estimated_effort_hours": round(effort_hours, 1),
            "risk_level": risk_level,
        },
        "changes_by_priority": {},
        "execution_order": [],
        "validation_strategy": {
            "test_approach": "characterization tests for each change",
            "rollback_trigger": "test failures or syntax errors",
            "validation_tools": ["pytest", "py_compile"],
        },
    }

    # Attach synthesis (Health Score + severity counts) if module is importable
    plan["overview"]["synthesis"] = _attach_synthesis(findings)

    # Add changes by priority
    for priority in ["P0", "P1", "P2", "P3"]:
        if by_priority[priority]:
            plan["changes_by_priority"][priority] = [
                {
                    "id": f.get("id", "unknown"),
                    "title": f.get("title", "Untitled"),
                    "file": f.get("file", "unknown"),
                    "change_description": f.get("description", ""),
                    "risk_analysis": _assess_change_risk(f),
                    "rollback_strategy": _suggest_rollback(f),
                }
                for f in by_priority[priority]
            ]

    # Define execution order
    if priority_counts["P0"] > 0:
        plan["execution_order"].append({
            "step": 1,
            "priority": "P0",
            "reason": "Fix bugs and race conditions first (highest risk)",
            "count": priority_counts["P0"],
        })
    if priority_counts["P1"] > 0:
        plan["execution_order"].append({
            "step": len(plan["execution_order"]) + 1,
            "priority": "P1",
            "reason": "Improve error handling (prevents future bugs)",
            "count": priority_counts["P1"],
        })
    if priority_counts["P2"] > 0:
        plan["execution_order"].append({
            "step": len(plan["execution_order"]) + 1,
            "priority": "P2",
            "reason": "Remove duplication (improves maintainability)",
            "count": priority_counts["P2"],
        })
    if priority_counts["P3"] > 0:
        plan["execution_order"].append({
            "step": len(plan["execution_order"]) + 1,
            "priority": "P3",
            "reason": "Apply conventions (low risk, polish)",
            "count": priority_counts["P3"],
        })

    return plan


def _assess_change_risk(finding: dict[str, Any]) -> str:
    """Assess the risk level of a specific change.

    Args:
        finding: Single refactoring finding

    Returns:
        Risk assessment string
    """
    change_type = finding.get("type", "unknown")
    file_path = finding.get("file_path", "")

    # High-risk changes
    if change_type in ["bug_fix", "race_condition", "concurrency"]:
        return "HIGH: Fixes critical bugs, requires thorough testing"

    # Medium-risk changes
    if change_type in ["error_handling", "duplication_removal"]:
        return "MEDIUM: Affects control flow, characterization tests required"

    # Low-risk changes
    if change_type in ["convention", "type_hints", "formatting"]:
        return "LOW: Cosmetic changes, minimal behavior impact"

    # Default assessment
    if "test" in file_path.lower():
        return "MEDIUM: Test changes require verification"

    return "MEDIUM: Standard refactoring risk"


def _suggest_rollback(finding: dict[str, Any]) -> str:
    """Suggest a rollback strategy for a specific change.

    Args:
        finding: Single refactoring finding

    Returns:
        Rollback strategy description
    """
    change_type = finding.get("type", "unknown")
    file_path = finding.get("file_path", "")

    if change_type == "bug_fix":
        return "Git revert if tests fail. Characterize current behavior before fixing."

    if change_type in ["duplication_removal", "extraction"]:
        return "Keep old code in comments until tests pass. Git revert if issues arise."

    if change_type in ["convention", "type_hints"]:
        return "Low risk, but keep git history for easy revert if needed."

    return "Git revert on test failure. Create characterization test before change."


def _attach_synthesis(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach synthesis block (Health Score + severity counts) to the plan.

    Maps priority-based findings to severity-based synthesis:
        P0 → CRITICAL, P1 → HIGH, P2 → MEDIUM, P3 → LOW

    Args:
        findings: Original findings (with 'priority' field)

    Returns:
        Synthesis dict with 'health_score', 'severity_counts', and
        'module_available' keys. When synthesize_findings is not importable,
        module_available is False and counts are zero.
    """
    if not _SYNTHESIS_AVAILABLE:
        return {
            "module_available": False,
            "health_score": None,
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        }

    # Translate priority → severity for synthesis
    severity_findings = [
        {"severity": _PRIORITY_TO_SEVERITY.get(f.get("priority", "P3"), "LOW")}
        for f in findings
    ]

    health_score = calculate_health_score(severity_findings)
    by_severity = group_by_severity(severity_findings)

    return {
        "module_available": True,
        "health_score": health_score,
        "severity_counts": {
            "CRITICAL": len(by_severity["CRITICAL"]),
            "HIGH": len(by_severity["HIGH"]),
            "MEDIUM": len(by_severity["MEDIUM"]),
            "LOW": len(by_severity["LOW"]),
        },
    }


def plan_to_markdown(plan: dict[str, Any]) -> str:
    """Convert plan dict to markdown format for display.

    Args:
        plan: Structured refactoring plan

    Returns:
        Markdown string
    """
    lines = []

    # Header
    lines.append(f"# Refactoring Plan: {plan['metadata']['target_path']}")
    lines.append("")
    lines.append(f"**Created**: {plan['metadata']['created_at']}")
    lines.append(f"**Session**: {plan['metadata']['session_id']}")
    lines.append("")

    # Overview
    overview = plan["overview"]
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Total findings**: {overview['total_findings']}")
    lines.append(f"- **Priority breakdown**: P0: {overview['priority_breakdown']['P0']}, P1: {overview['priority_breakdown']['P1']}, P2: {overview['priority_breakdown']['P2']}, P3: {overview['priority_breakdown']['P3']}")
    lines.append(f"- **Estimated effort**: {overview['estimated_effort_hours']} hours")
    lines.append(f"- **Risk level**: {overview['risk_level'].upper()}")

    # Synthesis block (Health Score + severity counts) if available
    synthesis = overview.get("synthesis", {})
    if synthesis.get("module_available") and synthesis.get("health_score") is not None:
        lines.append(f"- **Health Score**: {synthesis['health_score']}/100")
        counts = synthesis.get("severity_counts", {})
        lines.append(
            f"- **Severity counts**: CRITICAL: {counts.get('CRITICAL', 0)}, "
            f"HIGH: {counts.get('HIGH', 0)}, "
            f"MEDIUM: {counts.get('MEDIUM', 0)}, "
            f"LOW: {counts.get('LOW', 0)}"
        )
    lines.append("")

    # Changes by priority
    lines.append("## Changes by Priority")
    lines.append("")

    priority_labels = {
        "P0": "### P0: Bugs & Race Conditions (Highest Priority)",
        "P1": "### P1: Error Handling",
        "P2": "### P2: DRY Violations",
        "P3": "### P3: Conventions",
    }

    for priority in ["P0", "P1", "P2", "P3"]:
        if priority in plan["changes_by_priority"]:
            lines.append(priority_labels[priority])
            lines.append("")

            for change in plan["changes_by_priority"][priority]:
                lines.append(f"#### {change['id']}: {change['title']}")
                lines.append("")
                lines.append(f"**File**: `{change['file']}`")
                lines.append("")
                lines.append(f"**Change**: {change['change_description']}")
                lines.append("")
                lines.append(f"**Risk**: {change['risk_analysis']}")
                lines.append("")
                lines.append(f"**Rollback**: {change['rollback_strategy']}")
                lines.append("")

    # Execution order
    lines.append("## Execution Order")
    lines.append("")

    for step in plan["execution_order"]:
        lines.append(f"{step['step']}. **{step['priority']}**: {step['reason']} ({step['count']} changes)")

    lines.append("")

    # Validation strategy
    lines.append("## Validation Strategy")
    lines.append("")
    lines.append(f"- **Test approach**: {plan['validation_strategy']['test_approach']}")
    lines.append(f"- **Rollback trigger**: {plan['validation_strategy']['rollback_trigger']}")
    lines.append(f"- **Validation tools**: {', '.join(plan['validation_strategy']['validation_tools'])}")
    lines.append("")

    return "\n".join(lines)


def save_plan(plan: dict[str, Any], output_dir: Path) -> Path:
    """Save plan to JSON file.

    Args:
        plan: Structured refactoring plan
        output_dir: Directory to save plan in

    Returns:
        Path to saved plan file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_file = output_dir / f"refactor_plan_{timestamp}.json"

    plan_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    return plan_file


def load_plan(plan_path: Path) -> dict[str, Any] | None:
    """Load plan from JSON file.

    Args:
        plan_path: Path to plan file

    Returns:
        Plan dict, or None if file doesn't exist
    """
    plan_path = Path(plan_path)

    if not plan_path.exists():
        return None

    try:
        content = plan_path.read_text(encoding="utf-8")
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


if __name__ == "__main__":
    import argparse, json, sys
    parser = argparse.ArgumentParser(description="Generate refactoring plan from deduplicated findings")
    parser.add_argument("findings_json", type=Path, help="Path to deduplicated.json")
    parser.add_argument("target_path", help="Target being refactored (e.g. csf/)")
    parser.add_argument("session_id", help="Current session ID")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Output directory")
    args = parser.parse_args()

    data = json.loads(args.findings_json.read_text())
    plan = create_refactor_plan(data["findings"], args.target_path, args.session_id)
    out = save_plan(plan, args.output_dir)
    print(f"Plan saved: {out}")
    print(plan_to_markdown(plan))
