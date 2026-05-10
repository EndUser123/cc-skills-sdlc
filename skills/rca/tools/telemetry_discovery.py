#!/usr/bin/env python3
"""
Telemetry Discovery Tool for RCA investigations.

Enumerates all known telemetry sources (logs, state files, evidence stores)
and returns their paths, sizes, and modification times. Used in Step 0.85
to ensure RCA has full visibility into available diagnostic data.

Usage:
    python telemetry_discovery.py [--analyze]
    python telemetry_discovery.py [--match PATH] [--since DAYS]

Output:
    Dict of telemetry sources with metadata (path, size_mb, mtime, entry_count)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# Known telemetry source definitions
TELEMETRY_SOURCES: list[dict[str, Any]] = [
    {
        "name": "hook_execution_logs",
        "path": "P:\\\\\\.claude/hooks/logs",
        "pattern": "*.log",
        "description": "Hook execution logs from P:\\\\\\.claude/hooks/logs/",
        "format": "text",
    },
    {
        "name": "hook_state_files",
        "path": "P:\\\\\\.claude/hooks/state",
        "pattern": "*.json",
        "description": "Session/terminal state files from P:\\\\\\.claude/hooks/state/",
        "format": "json",
    },
    {
        "name": "skill_invocations",
        "path": "P:\\\\\\.claude/state/skill_invocations.jsonl",
        "pattern": "*.jsonl",
        "description": "Skill invocation audit log",
        "format": "jsonl",
    },
    {
        "name": "evidence_store_db",
        "path": "P:\\\\\\__csf/data/cks.db",
        "pattern": "*.db",
        "description": "CKS evidence store SQLite database",
        "format": "sqlite",
    },
    {
        "name": "session_transcripts",
        "path": "P:\\\\\\.claude/transcripts",
        "pattern": "*.jsonl",
        "description": "Session transcript files",
        "format": "jsonl",
    },
    {
        "name": "claude_logs",
        "path": "P:\\\\\\.claude/logs",
        "pattern": "*.log",
        "description": "Claude Code general logs",
        "format": "text",
    },
    {
        "name": "hook_diagnostics",
        "path": "P:\\\\\\.claude/hooks/hook_diagnostics.py",
        "pattern": None,
        "description": "Hook diagnostics script (existence check)",
        "format": "script",
    },
    {
        "name": "rca_workflow_state",
        "path": "~/.claude/state/rca/rca_workflow.json",
        "pattern": None,
        "description": "RCA workflow state file",
        "format": "json",
    },
    {
        "name": "intent_files",
        "path": "P:\\\\\\.claude/hooks/state",
        "pattern": "pending_command_intent_*.json",
        "description": "Pending command intent files",
        "format": "json",
    },
    {
        "name": "hook_events_db",
        "path": "P:\\\\\\.claude/hooks/events.db",
        "pattern": None,
        "description": "Hook observability SQLite database (constitutional_events, BloatAnalysis, TruthValidation)",
        "format": "sqlite",
    },
]


def discover_telemetry(since_days: int | None = None) -> dict[str, Any]:
    """
    Discover all available telemetry sources.

    Args:
        since_days: If set, only return sources modified in last N days.
                    None = return all.

    Returns:
        Dict with 'sources' list and 'summary' metadata.
    """
    home = Path.home()
    results: dict[str, Any] = {
        "sources": [],
        "summary": {
            "total_sources": 0,
            "available_sources": 0,
            "total_size_mb": 0.0,
            "inspection_time": datetime.now().isoformat(),
        },
    }

    cutoff_time = None
    if since_days is not None:
        cutoff_time = datetime.now() - timedelta(days=since_days)

    for source in TELEMETRY_SOURCES:
        # Resolve path with home directory expansion
        raw_path = source["path"].replace("~", str(home))
        base_path = Path(raw_path)

        entry: dict[str, Any] = {
            "name": source["name"],
            "description": source["description"],
            "format": source["format"],
            "path": str(base_path),
            "available": False,
            "files": [],
        }

        # Check if path exists
        if not base_path.exists():
            results["sources"].append(entry)
            continue

        # Handle single file vs directory
        pattern = source.get("pattern")

        if pattern and base_path.is_dir():
            # Directory with glob pattern
            try:
                matched_files = list(base_path.glob(pattern))
            except OSError:
                matched_files = []
            entry["files"] = [str(f) for f in matched_files]
        elif base_path.is_file():
            # Single file
            entry["files"] = [str(base_path)]
        elif base_path.is_dir():
            # Directory, no pattern - list all files
            try:
                all_files = list(base_path.iterdir())
            except OSError:
                all_files = []
            entry["files"] = [str(f) for f in all_files if f.is_file()]
            pattern = "*"

        # Compute metadata for matched files
        total_size = 0
        latest_mtime = None
        file_count = 0

        for file_path_str in entry["files"]:
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue

            try:
                stat = file_path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)

                # Filter by cutoff time if specified
                if cutoff_time and mtime < cutoff_time:
                    continue

                total_size += stat.st_size
                file_count += 1

                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime

            except OSError:
                continue

        # Update availability
        if entry["files"] and file_count > 0:
            entry["available"] = True
            entry["total_size_mb"] = round(total_size / (1024 * 1024), 3)
            entry["file_count"] = file_count
            entry["latest_mtime"] = latest_mtime.isoformat() if latest_mtime else None
            results["summary"]["available_sources"] += 1
            results["summary"]["total_size_mb"] += entry["total_size_mb"]

        results["sources"].append(entry)
        results["summary"]["total_sources"] += 1

    return results


def print_telemetry_summary(results: dict[str, Any]) -> None:
    """Print a human-readable summary of discovered telemetry."""
    print("\n=== Telemetry Discovery Summary ===\n")

    summary = results["summary"]
    print(f"Sources found: {summary['available_sources']}/{summary['total_sources']}")
    print(f"Total size: {summary['total_size_mb']:.2f} MB")
    print(f"Inspection time: {summary['inspection_time']}")
    print()

    for source in results["sources"]:
        status = "✓" if source["available"] else "✗"
        if source["available"]:
            size_str = f"{source.get('total_size_mb', 0):.2f} MB"
            count_str = source.get("file_count", 0)
            mtime_str = source.get("latest_mtime", "unknown")
            print(f"  {status} {source['name']}")
            print(f"      Path: {source['path']}")
            print(f"      Files: {count_str} ({size_str}), latest: {mtime_str}")
        else:
            print(f"  {status} {source['name']} (not available)")
            print(f"      Path: {source['path']}")

    print("\n=== End Telemetry Discovery ===\n")


def query_events_db(keyword: str, since_days: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """
    Query the hook events database for matching constitutional events.

    Args:
        keyword: Search term (case-insensitive, searches event_type, layer, payload)
        since_days: If set, only return events from last N days. None = all.
        limit: Maximum number of results to return.

    Returns:
        List of matching event records with id, sessionid, event_type, timestamp, layer, payload
    """
    import sqlite3
    from datetime import datetime

    db_path = Path("P:\\\\\\.claude/hooks/events.db")
    if not db_path.exists():
        return []

    keyword_lower = keyword.lower()
    cutoff_ts = None
    if since_days is not None:
        cutoff_ts = int((datetime.now() - timedelta(days=since_days)).timestamp())

    matches: list[dict[str, Any]] = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
    except Exception as e:
        # DB not accessible — return error marker so caller knows it's unavailable
        return [{"error": f"db_connect_failed", "detail": str(e), "db_path": str(db_path)}]

    try:
        if cutoff_ts:
            cur.execute(
                "SELECT id, sessionid, event_type, timestamp, layer, payload, created_at "
                "FROM constitutional_events WHERE timestamp >= ? ORDER BY id DESC LIMIT ?",
                (cutoff_ts, limit),
            )
        else:
            cur.execute(
                "SELECT id, sessionid, event_type, timestamp, layer, payload, created_at "
                "FROM constitutional_events ORDER BY id DESC LIMIT ?",
                (limit,),
            )

        for row in cur.fetchall():
            payload_str = row["payload"] or ""
            if keyword_lower in row["event_type"].lower() or \
               keyword_lower in (row["layer"] or "").lower() or \
               keyword_lower in payload_str.lower():
                matches.append({
                    "id": row["id"],
                    "sessionid": row["sessionid"],
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "layer": row["layer"],
                    "payload": payload_str[:300],
                    "created_at": row["created_at"],
                })
                if len(matches) >= limit:
                    break

        conn.close()
    except Exception:
        pass

    return matches


def find_relevant_logs(results: dict[str, Any], keyword: str) -> list[dict[str, Any]]:
    """
    Find log entries matching a keyword across all available telemetry sources.

    Args:
        results: Output from discover_telemetry()
        keyword: Search term (case-insensitive)

    Returns:
        List of matching entries with source, file, and context
    """
    matches: list[dict[str, Any]] = []
    keyword_lower = keyword.lower()

    for source in results["sources"]:
        if not source["available"]:
            continue

        for file_path_str in source["files"][:10]:  # Limit to first 10 files per source
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue

            try:
                if source["format"] == "jsonl":
                    # JSONL: parse and search
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            if keyword_lower in line.lower():
                                matches.append({
                                    "source": source["name"],
                                    "file": str(file_path),
                                    "line_num": line_num,
                                    "preview": line[:200],
                                })
                                if len(matches) >= 100:  # Cap results
                                    return matches
                elif source["format"] in ("text", "log"):
                    # Text log: read and search
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if keyword_lower in line.lower():
                                matches.append({
                                    "source": source["name"],
                                    "file": str(file_path),
                                    "line_num": line_num,
                                    "preview": line[:200],
                                })
                                if len(matches) >= 100:
                                    return matches
            except (OSError, UnicodeDecodeError):
                continue

    return matches


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Telemetry Discovery for RCA")
    parser.add_argument("--analyze", "-a", action="store_true", help="Print human-readable summary")
    parser.add_argument("--match", "-m", type=str, help="Search for keyword across logs")
    parser.add_argument("--since", "-s", type=int, default=None, help="Only show sources modified in last N days")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    parser.add_argument("--events-db", "-e", type=str, help="Query hook events DB for keyword (instead of sweeping all sources)")
    parser.add_argument("--events-since", type=int, default=None, help="Days back for events DB query")
    args = parser.parse_args()

    if args.events_db:
        matches = query_events_db(args.events_db, since_days=args.events_since)
        print(f"\n=== Hook Events DB: '{args.events_db}' (since={args.events_since or 'all'}) ===\n")
        print(f"Found {len(matches)} matches:\n")
        for m in matches:
            print(f"  [{m['event_type']}] session={m['sessionid']} layer={m['layer']}")
            print(f"    ts={m['timestamp']} id={m['id']} payload={m['payload'][:100]}...")
        print()
        return

    results = discover_telemetry(since_days=args.since)

    if args.match:
        matches = find_relevant_logs(results, args.match)
        print(f"\n=== Log Search: '{args.match}' ===\n")
        print(f"Found {len(matches)} matches:\n")
        for m in matches:
            print(f"  [{m['source']}] {m['file']}:{m['line_num']}")
            print(f"    {m['preview']}")
        print()
        return

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    elif args.analyze:
        print_telemetry_summary(results)
    else:
        # Default: print summary line
        s = results["summary"]
        print(f"Telemetry: {s['available_sources']}/{s['total_sources']} sources available "
              f"({s['total_size_mb']:.2f} MB total)")


if __name__ == "__main__":
    main()
