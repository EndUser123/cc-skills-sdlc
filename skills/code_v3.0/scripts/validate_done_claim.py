#!/usr/bin/env python3
"""
Done claim validation for /code skill workflow.

Validates that all tasks have complete TDD evidence (RED, GREEN, REFACTOR, VERIFY)
and TSR (Task Success Rate) is ≥ 95% before allowing SHIP phase completion.
"""

from typing import Optional


def calculate_tsr(evidence_mgr) -> dict:
    """
    Calculate Task Success Rate (TSR) from evidence ledger.

    TSR = (Successfully Completed Tasks / Total Attempted Tasks) × 100

    Args:
        evidence_mgr: EvidenceManager instance

    Returns:
        Dict with TSR statistics (total_attempted, completed, failed, blocked, tsr)
    """
    return evidence_mgr.get_completion_statistics()


def validate_done_claim(
    evidence_mgr,
    task_ids: Optional[list[str]] = None,
    tsr_threshold: float = 95.0,
) -> bool:
    """Validate that all tasks have complete TDD evidence and TSR ≥ 95% before SHIP.

    Args:
        evidence_mgr: EvidenceManager instance
        task_ids: Optional list of specific task IDs to check. If None, checks all tasks.
        tsr_threshold: Minimum TSR percentage required (default: 95.0)

    Returns:
        True if all tasks have all 4 evidence types AND TSR ≥ threshold

    Raises:
        ValueError: If validation fails with detailed report (TSR too low or missing evidence)
    """
    # Calculate TSR first
    stats = calculate_tsr(evidence_mgr)

    # Check TSR threshold
    if stats["tsr"] < tsr_threshold:
        # TSR too low - block DONE claim
        report_lines = [
            f"Cannot proceed to SHIP: Task Success Rate (TSR) is {stats['tsr']}%, below {tsr_threshold}% threshold.",
            "",
            "Task Breakdown:",
            f"  - Total attempted: {stats['total_attempted']}",
            f"  - Completed: {stats['completed']}",
            f"  - Failed: {stats['failed']}",
            f"  - Blocked: {stats['blocked']}",
            "",
            f"TSR must be ≥ {tsr_threshold}% to proceed to SHIP phase.",
            "Complete failed or blocked tasks before marking done."
        ]

        error_message = "\n".join(report_lines)
        raise ValueError(error_message)

    # Get all task IDs from ledger if not specified
    if task_ids is None:
        ledger = evidence_mgr._load_ledger()
        task_ids = list(ledger.get("tasks", {}).keys())

    # If no tasks, validation passes (nothing to check)
    if not task_ids:
        return True

    # Check each task's evidence completeness
    missing_evidence_report = []

    for task_id in task_ids:
        can_done, msg = evidence_mgr.can_mark_done(task_id)

        if not can_done:
            # Parse missing evidence types from message
            # Message format: "Cannot mark task done: missing evidence for RED, GREEN"
            if "missing evidence for" in msg:
                missing_str = msg.split("missing evidence for")[1].strip()
                missing_types = [m.strip() for m in missing_str.split(",")]

                missing_evidence_report.append({
                    "task_id": task_id,
                    "missing_evidence": missing_types,
                })

    # If all complete, return True with TSR report
    if not missing_evidence_report:
        return True

    # Otherwise, raise ValueError with detailed report
    report_lines = [
        f"Cannot proceed to SHIP: {len(missing_evidence_report)} task(s) missing evidence.",
        "",
        f"TSR Report: {stats['tsr']}% (threshold: {tsr_threshold}%)",
        f"  - Total attempted: {stats['total_attempted']}",
        f"  - Completed: {stats['completed']}",
        f"  - Failed: {stats['failed']}",
        f"  - Blocked: {stats['blocked']}",
        "",
        "Complete all 4 evidence types (RED, GREEN, REFACTOR, VERIFY) for each task.",
        "",
        "Missing Evidence Details:"
    ]

    for item in missing_evidence_report:
        task_id = item["task_id"]
        missing = item["missing_evidence"]
        report_lines.append(f"  - {task_id}: missing {', '.join(missing)}")

    error_message = "\n".join(report_lines)
    raise ValueError(error_message)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from utils.evidence import EvidenceManager

    if len(sys.argv) < 2:
        print("Usage: python validate_done_claim.py <terminal_id> [task_id1,task_id2,...]")
        sys.exit(1)

    terminal_id = sys.argv[1]
    task_ids = sys.argv[2].split(",") if len(sys.argv) > 2 else None

    mgr = EvidenceManager(terminal_id)

    try:
        validate_done_claim(mgr, task_ids)
        print("✓ All tasks validated - ready for SHIP phase")
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)
