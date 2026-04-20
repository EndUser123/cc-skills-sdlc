#!/usr/bin/env python3
r"""
Status report generator for /code skill workflow.

Displays current build status including:
- Phase completion status (BUILD/TRACE/SHIP)
- Task progress summary (complete/pending/blocked)
- Missing evidence per task
- Terminal ownership and lease status
"""

from typing import Optional


def generate_status_report(
    evidence_mgr: Optional["EvidenceManager"] = None,
    phase_mgr: Optional["PhaseStateManager"] = None,
) -> str:
    r"""Generate a comprehensive status report for the /code build workflow.

    Args:
        evidence_mgr: Optional EvidenceManager instance for task/evidence status
        phase_mgr: Optional PhaseStateManager instance for phase status

    Returns:
        Formatted status report string

    Example:
        >>> report = generate_status_report(evidence_mgr, phase_mgr)
        >>> print(report)
        === /code Build Status ===

        Phase Status:
          BUILD: ✅ Complete
          TRACE: ⏸ In Progress
          SHIP: ❌ Not Started

        Task Progress:
          3 complete, 2 pending, 1 blocked

        Missing Evidence:
          task-2: GREEN, REFACTOR
          task-3: RED, GREEN, REFACTOR, VERIFY

        Terminal Ownership:
          Current: terminal-001
          Lease: Expires in 15 minutes
    """
    lines = []
    lines.append("=== /code Build Status ===")
    lines.append("")

    # 1. Phase Status
    if phase_mgr:
        lines.extend(_format_phase_status(phase_mgr))
    else:
        lines.append("Phase Status: Not available")

    lines.append("")

    # 2. Task Progress
    if evidence_mgr:
        lines.extend(_format_task_progress(evidence_mgr))
    else:
        lines.append("Task Progress: Not available")

    lines.append("")

    # 3. Missing Evidence
    if evidence_mgr:
        missing_evidence = _format_missing_evidence(evidence_mgr)
        if missing_evidence:
            lines.extend(missing_evidence)
        else:
            lines.append("Missing Evidence: None - all tasks complete")
    else:
        lines.append("Missing Evidence: Not available")

    lines.append("")

    # 4. Terminal Ownership
    if phase_mgr:
        lines.extend(_format_terminal_ownership(phase_mgr))
    else:
        lines.append("Terminal Ownership: Not available")

    return "\n".join(lines)


def _format_phase_status(phase_mgr) -> list[str]:
    """Format phase status section.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        List of formatted lines
    """
    lines = ["Phase Status:"]
    all_phases = phase_mgr.get_all_phases_status()
    phase_order = ["BUILD", "TRACE", "SHIP"]

    # Check for invalid phases (completed but not in valid list)
    invalid_phases = []
    for phase_name, status in all_phases.items():
        if status.get("completed", False) and phase_name not in phase_order:
            invalid_phases.append(phase_name)

    if invalid_phases:
        for phase_name in invalid_phases:
            lines.append(f"  {phase_name}: ✗ Invalid phase")

    for phase in phase_order:
        status = all_phases.get(phase, {})
        completed = status.get("completed", False)

        if completed:
            # Check if phase is still valid (commit hash matches HEAD)
            if phase_mgr.is_phase_valid(phase):
                lines.append(f"  {phase}: ✅ Complete")
            else:
                lines.append(f"  {phase}: ✗ Complete (invalid: commit mismatch)")
        else:
            # Check if we're in this phase (no later phase is complete)
            phase_idx = phase_order.index(phase)
            later_phases_complete = any(
                all_phases.get(p, {}).get("completed", False)
                for p in phase_order[phase_idx + 1:]
            )
            if later_phases_complete:
                lines.append(f"  {phase}: ⏸ In Progress")
            else:
                lines.append(f"  {phase}: ❌ Not Started")

    return lines


def _format_task_progress(evidence_mgr) -> list[str]:
    """Format task progress section.

    Args:
        evidence_mgr: EvidenceManager instance

    Returns:
        List of formatted lines
    """
    lines = ["Task Progress:"]
    ledger = evidence_mgr._load_ledger()
    tasks = ledger.get("tasks", {})

    if not tasks:
        lines.append("  No tasks in ledger")
        return lines

    # Count tasks by status
    complete_count = 0
    pending_count = 0
    blocked_count = 0

    for task_id, task_data in tasks.items():
        evidence = task_data.get("evidence", {})
        required = ["RED", "GREEN", "REFACTOR", "VERIFY"]
        all_present = all(evidence.get(s, {}).get("completed", False) for s in required)

        if all_present:
            complete_count += 1
        else:
            # Check if blocked (has RED but missing other evidence)
            if evidence.get("RED", {}).get("completed", False):
                pending_count += 1
            else:
                blocked_count += 1

    lines.append(f"  {complete_count} complete, {pending_count} pending, {blocked_count} blocked")

    return lines


def _format_missing_evidence(evidence_mgr) -> list[str] | None:
    """Format missing evidence section.

    Args:
        evidence_mgr: EvidenceManager instance

    Returns:
        List of formatted lines, or None if no missing evidence
    """
    ledger = evidence_mgr._load_ledger()
    tasks = ledger.get("tasks", {})

    if not tasks:
        return None

    missing_by_task = {}
    required = ["RED", "GREEN", "REFACTOR", "VERIFY"]

    for task_id, task_data in tasks.items():
        evidence = task_data.get("evidence", {})
        missing = [
            stage for stage in required
            if not evidence.get(stage, {}).get("completed", False)
        ]

        if missing:
            missing_by_task[task_id] = missing

    if not missing_by_task:
        return None

    lines = ["Missing Evidence:"]
    for task_id, missing in sorted(missing_by_task.items()):
        lines.append(f"  {task_id}: {', '.join(missing)}")

    return lines


def _format_terminal_ownership(phase_mgr) -> list[str]:
    """Format terminal ownership section.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        List of formatted lines
    """
    lines = ["Terminal Ownership:"]
    build_state = phase_mgr._load_build_state()

    current_owner = build_state.get("current_owner")
    lease_expires = build_state.get("lease_expires_at")

    if current_owner:
        lines.append(f"  Current: {current_owner}")
    else:
        lines.append("  Current: None")

    if lease_expires:
        from datetime import datetime

        # Calculate remaining time
        try:
            expires_at = datetime.fromisoformat(lease_expires)
            now = datetime.now()
            remaining = expires_at - now

            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                lines.append(f"  Lease: Expires in {minutes} minutes")
            else:
                lines.append("  Lease: Expired")
        except (ValueError, OSError):
            lines.append(f"  Lease: {lease_expires}")
    else:
        lines.append("  Lease: No active lease")

    return lines


if __name__ == "__main__":
    import sys

    # Add parent directory to path
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    from utils.evidence import EvidenceManager
    from utils.phase_state import PhaseStateManager

    # Generate status report
    terminal_id = "default"
    evidence_mgr = EvidenceManager(terminal_id)
    phase_mgr = PhaseStateManager(terminal_id)

    report = generate_status_report(evidence_mgr, phase_mgr)
    print(report)
