#!/usr/bin/env python3
r"""
Repair stale phase markers for /code skill workflow.

Detects and invalidates phase markers that have stale commit hashes (i.e., markers
that were recorded when git HEAD was at a different commit than current HEAD).

This handles rollback detection - when code is rolled back to an earlier commit,
phase markers from the newer commit become invalid and must be re-completed.

Usage:
    python -m scripts.repair_markers [--yes] [--dry-run]

Options:
    --yes      Auto-confirm repair without prompting
    --dry-run  Show what would be repaired without making changes
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.phase_state import PhaseStateManager

# Configure logging for CLI usage
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def detect_stale_markers(phase_mgr: "PhaseStateManager") -> list[str]:
    """Detect phase markers with stale commit hashes.

    Scans all phase markers in state and compares their recorded commit_hash
    against the current git HEAD. Returns a list of phase names that have
    stale markers.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        List of phase names with stale markers

    Example:
        >>> stale = detect_stale_markers(phase_mgr)
        >>> print(stale)
        ['BUILD', 'TRACE']
    """
    stale_markers = []

    try:
        all_phases = phase_mgr.get_all_phases_status()

        for phase_name, status in all_phases.items():
            # Check if phase is marked complete but not valid
            if status.get("completed", False) and not status.get("valid", False):
                stale_markers.append(phase_name)

    except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
        # Handle corrupted or missing state files
        logger.error(f"Error reading phase state: {e}")
        raise

    return stale_markers


def invalidate_stale_markers(phase_mgr: "PhaseStateManager") -> int:
    """Invalidate all stale phase markers.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        Count of markers invalidated

    Example:
        >>> count = invalidate_stale_markers(phase_mgr)
        >>> print(f"Invalidated {count} markers")
    """
    stale_markers = detect_stale_markers(phase_mgr)
    count = 0

    for phase_name in stale_markers:
        try:
            phase_mgr.invalidate_phase(phase_name)
            count += 1
            logger.info(f"  {phase_name}: invalidated (commit mismatch)")
        except Exception as e:
            logger.error(f"Failed to invalidate {phase_name}: {e}")

    return count


def repair_markers_dry_run(phase_mgr: "PhaseStateManager") -> str:
    """Generate a dry-run report of stale markers without modifying state.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        Report string describing what would be repaired

    Example:
        >>> report = repair_markers_dry_run(phase_mgr)
        >>> print(report)
        Stale markers detected: BUILD, TRACE
    """
    stale_markers = detect_stale_markers(phase_mgr)

    if not stale_markers:
        return "No stale markers detected."

    # Get commit details for report
    all_phases = phase_mgr.get_all_phases_status()
    details = []

    for phase_name in stale_markers:
        status = all_phases.get(phase_name, {})
        old_commit = status.get("commit_hash", "unknown")

        details.append(f"  {phase_name}: {old_commit} (stale)")

    report_lines = ["Stale markers detected:", *details, ""]
    report_lines.append(f"Total: {len(stale_markers)} stale marker(s)")

    return "\n".join(report_lines)


def repair_markers_interactive(
    phase_mgr: "PhaseStateManager",
    confirm: bool = True
) -> dict:
    """Repair stale markers with optional confirmation prompt.

    Args:
        phase_mgr: PhaseStateManager instance
        confirm: If True, prompt user before repairing (default: True)

    Returns:
        Dict with repair results:
        {
            "invalidated": list[str],  # Phase names that were invalidated
            "invalidated_count": int,  # Count of invalidated markers
            "skipped": bool            # True if user declined confirmation
        }

    Example:
        >>> result = repair_markers_interactive(phase_mgr, confirm=False)
        >>> print(result["invalidated_count"])
        2
    """
    stale_markers = detect_stale_markers(phase_mgr)

    if not stale_markers:
        return {
            "invalidated": [],
            "invalidated_count": 0,
            "skipped": False
        }

    # Show what will be repaired
    all_phases = phase_mgr.get_all_phases_status()
    print("\nStale markers detected:")
    for phase_name in stale_markers:
        status = all_phases.get(phase_name, {})
        old_commit = status.get("commit_hash", "unknown")
        print(f"  {phase_name}: {old_commit} (stale)")
    print()

    # Confirm if requested
    if confirm:
        response = input(f"Repair {len(stale_markers)} marker(s)? [y/N]: ")
        if response.lower() != 'y':
            print("Repair cancelled.")
            return {
                "invalidated": [],
                "invalidated_count": 0,
                "skipped": True
            }

    # Perform repair
    invalidated = []
    for phase_name in stale_markers:
        try:
            phase_mgr.invalidate_phase(phase_name)
            invalidated.append(phase_name)
        except Exception as e:
            logger.error(f"Failed to invalidate {phase_name}: {e}")

    return {
        "invalidated": invalidated,
        "invalidated_count": len(invalidated),
        "skipped": False
    }


def repair_stale_markers(
    phase_mgr: "PhaseStateManager",
    stale_markers: list[str] | None = None,
    confirm: bool = True,
    dry_run: bool = False
) -> dict:
    """Repair stale phase markers (high-level API).

    This is the main repair function that coordinates detection, confirmation,
    and invalidation of stale markers.

    Args:
        phase_mgr: PhaseStateManager instance
        stale_markers: Optional list of specific markers to repair (default: detect all)
        confirm: If True, require user confirmation before repair (default: True)
        dry_run: If True, report changes without executing (default: False)

    Returns:
        Dict with repair results:
        {
            "detected": list[str],     # All stale markers detected
            "invalidated": list[str],  # Markers that were invalidated
            "invalidated_count": int,  # Count of invalidated markers
            "dry_run": bool,           # True if this was a dry run
            "skipped": bool            # True if user declined confirmation
        }

    Example:
        >>> result = repair_stale_markers(
        ...     phase_mgr,
        ...     confirm=False,
        ...     dry_run=False
        ... )
        >>> print(f"Repaired {result['invalidated_count']} markers")
    """
    # Detect stale markers if not provided
    if stale_markers is None:
        stale_markers = detect_stale_markers(phase_mgr)

    if not stale_markers:
        return {
            "detected": [],
            "invalidated": [],
            "invalidated_count": 0,
            "dry_run": dry_run,
            "skipped": False
        }

    # Dry run mode - just report
    if dry_run:
        report = repair_markers_dry_run(phase_mgr)
        print(report)
        return {
            "detected": stale_markers,
            "invalidated": [],
            "invalidated_count": 0,
            "dry_run": True,
            "skipped": False
        }

    # Interactive repair
    result = repair_markers_interactive(phase_mgr, confirm=confirm)

    # Add detected list to result
    result["detected"] = stale_markers

    # Print summary
    if result["invalidated_count"] > 0:
        print("\nRepaired:")
        for phase_name in result["invalidated"]:
            print(f"  {phase_name}: invalidated (commit mismatch)")

    return result


def main() -> int:
    """CLI entry point for repair markers command.

    Returns:
        Exit code (0 for success, 1 for error)

    Example:
        >>> # Auto-confirm repair
        >>> exit_code = main()  # Called via CLI with --yes
    """
    parser = argparse.ArgumentParser(
        description="Repair stale phase markers in /code workflow"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-confirm repair without prompting"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be repaired without making changes"
    )

    args = parser.parse_args()

    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from utils.phase_state import PhaseStateManager

        # Use default terminal ID
        terminal_id = "default"
        phase_mgr = PhaseStateManager(terminal_id)

        print("Repairing stale phase markers...\n")

        # Run repair
        result = repair_stale_markers(
            phase_mgr,
            confirm=not args.yes,
            dry_run=args.dry_run
        )

        # Report results
        if args.dry_run:
            # Dry run already printed its report
            pass
        elif result["skipped"]:
            print("Repair cancelled by user.")
        elif result["invalidated_count"] == 0:
            print("No stale markers found.")
        else:
            print(f"\nRepaired {result['invalidated_count']} marker(s).")

        return 0

    except json.JSONDecodeError as e:
        logger.error(f"Error: Corrupted state file - {e}")
        return 1
    except FileNotFoundError as e:
        logger.error(f"Error: State file not found - {e}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
