#!/usr/bin/env python3
"""Test gap loader for /tdd integration.

Consumes gap files created by /t discovery mode.
Uses terminal-scoped files for multi-terminal safety.
"""

import json
import os
from pathlib import Path


def _get_terminal_id() -> str:
    """
    Get the terminal/session ID for multi-terminal coordination.

    Returns:
        Terminal identifier string
    """
    return os.environ.get("WT_SESSION") or os.environ.get("TERM") or f"pid-{os.getpid()}"


def load_test_gaps(project_root: Path | str) -> dict | None:
    """
    Load test gaps from /t discovery results.

    Checks for terminal-scoped _READY.json files created by /t.
    If found, loads and returns the gap data, then renames to _CONSUMED
    to prevent duplicate consumption.

    Args:
        project_root: Project root directory

    Returns:
        Gap data dict with keys: target, gaps, test_types, coverage_percent, total_tests, timestamp
        Returns None if no gap file exists
    """
    project_root = Path(project_root)
    gaps_dir = project_root / ".claude" / "state" / "test_gaps"

    # Check for terminal-scoped READY file
    terminal_id = _get_terminal_id()
    ready_file = gaps_dir / f"{terminal_id}_gaps_READY.json"

    # Also check for global _READY.json (fallback for single-terminal use)
    global_ready_file = gaps_dir / "_READY.json"

    gap_file = None
    if ready_file.exists():
        gap_file = ready_file
    elif global_ready_file.exists():
        gap_file = global_ready_file
    else:
        # No gap file found
        return None

    # Load gap data
    try:
        with open(gap_file) as f:
            gap_data = json.load(f)

        # Mark as consumed by renaming
        consumed_file = gap_file.with_name(f"{gap_file.stem.replace('_READY', '')}_CONSUMED.json")

        # Atomic rename to prevent re-consumption
        try:
            gap_file.rename(consumed_file)
        except OSError:
            # If rename fails (e.g., concurrent access), try to delete
            try:
                gap_file.unlink()
            except OSError:
                pass

        return gap_data

    except (json.JSONDecodeError, OSError):
        # Corrupt or inaccessible file - clean up and continue
        try:
            gap_file.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def format_gap_summary(gap_data: dict) -> str:
    """
    Format gap data as a readable summary for DISCOVER phase.

    Args:
        gap_data: Gap data from load_test_gaps()

    Returns:
        Formatted summary string
    """
    lines = [
        "## Test Gaps from /t Discovery",
        "",
        f"**Target:** {gap_data.get('target', 'unknown')}",
        f"**Coverage:** {gap_data.get('coverage_percent', 0):.1f}%",
        f"**Total Tests:** {gap_data.get('total_tests', 0)}",
        "",
        "### Test Types",
        ""
    ]

    for test_type, count in gap_data.get("test_types", {}).items():
        lines.append(f"- **{test_type.replace('_', ' ').title()}:** {count}")

    lines.extend([
        "",
        "### Coverage Gaps",
        ""
    ])

    gaps = gap_data.get("gaps", [])
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("*No gaps identified*")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test the gap loader
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    gaps = load_test_gaps(target)

    if gaps:
        print(format_gap_summary(gaps))
    else:
        print("No test gap file found.")
        print("Run `/t` first to generate test gaps.")
