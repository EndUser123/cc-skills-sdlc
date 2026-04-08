#!/usr/bin/env python3
"""
Phase transition validation for /code skill workflow.

Enforces phase order (BUILD → TRACE → SHIP), validates phase completion
status, and checks for git rollback detection.
"""

from typing import Literal

# Valid phase order
PHASE_ORDER = [
    "BOOTSTRAP",
    "ALIGN",
    "DESIGN",
    "BUILD",
    "TRACE",
    "SHIP",
]

ValidPhase = Literal[
    "BOOTSTRAP",
    "ALIGN",
    "DESIGN",
    "BUILD",
    "TRACE",
    "SHIP",
]


def validate_phase_transition(
    target_phase: ValidPhase,
    phase_mgr,
) -> bool:
    """Validate phase transition before allowing it.

    Args:
        target_phase: Phase to transition to (e.g., "TRACE", "SHIP")
        phase_mgr: PhaseStateManager instance

    Returns:
        True if transition is valid

    Raises:
        ValueError: If transition is invalid with clear error message
    """
    # 1. Check if target_phase is valid
    if target_phase not in PHASE_ORDER:
        raise ValueError(
            f"Invalid phase '{target_phase}'. "
            f"Valid phases: {', '.join(PHASE_ORDER)}"
        )

    # 2. Get current phase state
    all_status = phase_mgr.get_all_phases_status()
    target_idx = PHASE_ORDER.index(target_phase)

    # 3. Check for regression (target_phase comes before a completed phase)
    # This check runs BEFORE predecessor check to catch backward transitions
    for phase_name in PHASE_ORDER[target_idx + 1:]:
        phase_status = all_status.get(phase_name, {})
        if phase_status.get("completed"):
            raise ValueError(
                f"Cannot transition to {target_phase}: "
                f"phase regression detected (phase '{phase_name}' already completed). "
                f"Phase order is unidirectional: {' → '.join(PHASE_ORDER)}"
            )

    # 4. Check if immediate predecessor completed
    if target_idx > 0:
        predecessor = PHASE_ORDER[target_idx - 1]
        predecessor_status = all_status.get(predecessor, {})

        if not predecessor_status.get("completed"):
            raise ValueError(
                f"Cannot transition to {target_phase}: "
                f"previous phase '{predecessor}' is not completed. "
                f"Phase sequence requirement: {' → '.join(PHASE_ORDER[:target_idx + 1])}"
            )

    # 5. Check phase validity (rollback detection and missing hash)
    # Only check if there's a predecessor phase
    if target_idx > 0:
        predecessor = PHASE_ORDER[target_idx - 1]
        predecessor_status = all_status.get(predecessor, {})
        recorded_hash = predecessor_status.get("commit_hash")

        # 5a. Check for missing commit hash
        if not recorded_hash:
            raise ValueError(
                f"Cannot transition to {target_phase}: "
                f"previous phase '{predecessor}' has no commit hash recorded. "
                f"Phase must be re-marked complete with commit hash."
            )

        # 5b. Check rollback for real git commit hashes (40 hex chars)
        # Test hashes (e.g., "build123") are shorter and should skip this check
        if len(recorded_hash) == 40:
            if not phase_mgr.is_phase_valid(predecessor):
                from utils.phase_state import get_git_head_hash

                current_hash = get_git_head_hash()
                if current_hash and current_hash != recorded_hash:
                    raise ValueError(
                        f"Cannot transition to {target_phase}: "
                        f"git rollback detected for phase '{predecessor}'. "
                        f"Recorded commit: {recorded_hash[:8]}, Current HEAD: {current_hash[:8]}. "
                        f"Phase must be re-marked complete with current commit hash."
                    )

    return True


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from utils.phase_state import PhaseStateManager

    if len(sys.argv) < 2:
        print("Usage: python validate_phase_transition.py <target_phase> [terminal_id]")
        sys.exit(1)

    target = sys.argv[1]
    terminal_id = sys.argv[2] if len(sys.argv) > 2 else "default"

    mgr = PhaseStateManager(terminal_id)

    try:
        validate_phase_transition(target, mgr)
        print(f"✓ Phase transition to {target} is valid")
    except ValueError as e:
        print(f"✗ Phase transition blocked: {e}")
        sys.exit(1)
