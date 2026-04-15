#!/usr/bin/env python3
"""
Show Recent Skill Invocations Tool

Displays the last N Skill() tool invocations from the log file.
This makes "Did Skill run?" a cheap, reliable query.

GLM5 Analysis Recommendation: "Add a debug skill 'show_recent_skill_invocations'
that reads that log and prints the last N calls in the conversation."

Usage:
    python show_skill_invocations.py [--limit N] [--session-id SESSION_ID]

Output Format:
    Recent Skill Invocations (last 5):
    [1] rca (2026-03-11T15:30:45) - Session: console_abc123
        Arguments: {"query": "investigate issue"}
    [2] gto (2026-03-11T15:28:30) - Session: console_abc123
        Arguments: {}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def get_default_log_path() -> Path:
    """Get the default log file path."""
    return Path("P:/.claude/state/skill_invocations.jsonl")


def read_skill_invocations(log_path: Path, limit: int = 5) -> list[dict]:
    """
    Read the last N skill invocations from the log file.

    Args:
        log_path: Path to the JSONL log file
        limit: Maximum number of recent invocations to return

    Returns:
        List of log entry dicts (most recent first)
    """
    if not log_path.exists():
        return []

    invocations = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    invocations.append(entry)
                except json.JSONDecodeError:
                    # Skip malformed log entries
                    continue

        # Return most recent first (reverse chronological order)
        return invocations[-limit:][::-1]
    except Exception as e:
        print(f"Error reading log file: {e}", file=sys.stderr)
        return []


def format_invocation(entry: dict, index: int) -> str:
    """
    Format a single invocation for display.

    Args:
        entry: Log entry dict
        index: Index number for display

    Returns:
        Formatted string
    """
    timestamp = entry.get("timestamp", "unknown")
    skill_name = entry.get("skill_name", "unknown")
    arguments = entry.get("arguments", {})
    session_id = entry.get("session_id", "unknown")
    terminal_id = entry.get("terminal_id", "unknown")

    # Parse timestamp for relative time display
    try:
        dt = datetime.fromisoformat(timestamp)
        now = datetime.now(UTC)
        delta = now - dt

        if delta.seconds < 60:
            time_ago = f"{delta.seconds} seconds ago"
        elif delta.seconds < 3600:
            minutes = delta.seconds // 60
            time_ago = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            hours = delta.seconds // 3600
            time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
    except Exception:
        time_ago = timestamp

    lines = [
        f"[{index}] {skill_name} ({time_ago}) - Session: {session_id}",
        f"    Terminal: {terminal_id}",
    ]

    if arguments:
        args_str = json.dumps(arguments, indent=8)
        lines.append(f"    Arguments: {args_str}")

    return "\n".join(lines)


def show_recent_invocations(limit: int = 5, session_id: str | None = None) -> int:
    """
    Display recent skill invocations.

    Args:
        limit: Number of recent invocations to show
        session_id: Filter by session ID (optional)

    Returns:
        Number of invocations shown
    """
    log_path = get_default_log_path()

    # Read invocations
    invocations = read_skill_invocations(log_path, limit=limit * 2)  # Read extra for filtering

    # Filter by session_id if provided
    if session_id:
        invocations = [inv for inv in invocations if inv.get("session_id") == session_id]

    # Limit after filtering
    invocations = invocations[:limit]

    if not invocations:
        print("No skill invocations found in log.")
        if session_id:
            print(f"Filtered by session_id: {session_id}")
        return 0

    # Display header
    filter_msg = f" (filtered by session: {session_id})" if session_id else ""
    print(f"Recent Skill Invocations (last {len(invocations)}){filter_msg}:")
    print()

    # Display each invocation
    for i, entry in enumerate(invocations, 1):
        print(format_invocation(entry, i))
        print()

    return len(invocations)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Show recent Skill() tool invocations", epilog=__doc__
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=5,
        help="Number of recent invocations to show (default: 5)",
    )
    parser.add_argument("--session-id", "-s", type=str, default=None, help="Filter by session ID")

    args = parser.parse_args()

    count = show_recent_invocations(limit=args.limit, session_id=args.session_id)
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
