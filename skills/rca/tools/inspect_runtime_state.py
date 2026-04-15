#!/usr/bin/env python3
"""
Cross-platform runtime state inspection for rca investigations.

This tool provides runtime state information for silent failure investigations,
with cross-platform compatibility (Windows/Linux/macOS) and error handling
for missing/corrupted files.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def inspect_runtime_state(state_dir: str = None) -> dict[str, Any]:
    """
    Cross-platform runtime state inspection.

    Args:
        state_dir: Path to state directory (default: P:/.claude/hooks/state)

    Returns:
        Dictionary containing:
        - session_terminal: Session and terminal ID information
        - pending_intents: Pending command intent files
        - hook_logs: Hook execution log information
        - evidence_store: Evidence store availability
    """
    if state_dir is None:
        state_dir = "P:/.claude/hooks/state"

    state_path = Path(state_dir)

    results = {"session_terminal": {}, "pending_intents": {}, "hook_logs": {}, "evidence_store": {}}

    # 1. Session/Terminal State
    results["session_terminal"]["session_id"] = os.environ.get("CLAUDE_SESSION_ID", "not_set")
    results["session_terminal"]["terminal_id"] = os.environ.get("CLAUDE_TERMINAL_ID", "not_set")

    session_file = state_path / "session_state.json"
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text())
            results["session_terminal"]["file_session_id"] = data.get("session_id", "not_found")
        except json.JSONDecodeError as e:
            results["session_terminal"]["file_error"] = "Invalid JSON"
            results["session_terminal"]["file_error_detail"] = str(e)
            # Try to show first 500 bytes for diagnosis
            try:
                first_bytes = session_file.read_text()[:500]
                results["session_terminal"]["file_preview"] = first_bytes
            except Exception:
                pass
    else:
        results["session_terminal"]["file_status"] = "not_found"

    # Count stale state files (with caching for performance)
    stale_cache = state_path / ".stale_count_cache"
    cache_valid = False

    if stale_cache.exists():
        cache_mtime = datetime.fromtimestamp(stale_cache.stat().st_mtime)
        if (datetime.now() - cache_mtime).seconds < 300:  # 5-minute TTL
            cache_valid = True
            try:
                results["session_terminal"]["stale_count"] = int(stale_cache.read_text())
                results["session_terminal"]["stale_count_source"] = "cache"
            except (OSError, ValueError):
                cache_valid = False

    if not cache_valid:
        # Find stale files (modified >1 day ago)
        try:
            one_day_ago = datetime.now() - timedelta(days=1)
            stale_files = []

            for f in state_path.glob("*.json"):
                try:
                    f_mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if f_mtime < one_day_ago:
                        stale_files.append(
                            {
                                "name": f.name,
                                "mtime": f_mtime.isoformat(),
                                "age_hours": (datetime.now() - f_mtime).total_seconds() / 3600,
                            }
                        )
                except (OSError, AttributeError):
                    # Skip files we can't stat
                    continue

            results["session_terminal"]["stale_count"] = len(stale_files)
            results["session_terminal"]["stale_count_source"] = "computed"

            # Show first few stale files for diagnosis
            if stale_files:
                results["session_terminal"]["stale_samples"] = stale_files[:5]

            # Update cache
            try:
                stale_cache.write_text(str(len(stale_files)))
            except OSError:
                pass  # Cache write failure is not critical

        except Exception as e:
            results["session_terminal"]["stale_error"] = str(e)

    # 2. Pending Intent Files
    try:
        intent_files = list(state_path.glob("pending_command_intent_*.json"))
        results["pending_intents"]["count"] = len(intent_files)

        if intent_files:
            # Find latest intent file
            try:
                latest = max(intent_files, key=lambda p: p.stat().st_mtime)
                results["pending_intents"]["latest_file"] = latest.name
                results["pending_intents"]["latest_mtime"] = datetime.fromtimestamp(
                    latest.stat().st_mtime
                ).isoformat()

                # Try to parse latest intent
                try:
                    intent_data = json.loads(latest.read_text())
                    results["pending_intents"]["latest_content"] = intent_data
                except json.JSONDecodeError as e:
                    results["pending_intents"]["latest_error"] = "Invalid JSON"
                    results["pending_intents"]["latest_error_detail"] = str(e)
                    # Show first 500 bytes for diagnosis
                    try:
                        first_bytes = latest.read_text()[:500]
                        results["pending_intents"]["latest_preview"] = first_bytes
                    except Exception:
                        pass
            except (OSError, AttributeError) as e:
                results["pending_intents"]["latest_error"] = f"Cannot read latest file: {e}"

    except Exception as e:
        results["pending_intents"]["error"] = str(e)

    # 3. Hook Execution Logs (check if diagnostics available)
    hook_diag = Path("P:/.claude/hooks/hook_diagnostics.py")
    if hook_diag.exists():
        results["hook_logs"]["diagnostics_available"] = True
        results["hook_logs"]["diagnostics_path"] = str(hook_diag)
    else:
        results["hook_logs"]["diagnostics_available"] = False

    # Check for hook log files
    log_dir = Path("P:/.claude/hooks/logs")
    if log_dir.exists():
        try:
            log_files = list(log_dir.glob("*.log"))
            results["hook_logs"]["log_files_count"] = len(log_files)
            if log_files:
                results["hook_logs"]["latest_log"] = max(
                    log_files, key=lambda p: p.stat().st_mtime
                ).name
        except Exception as e:
            results["hook_logs"]["log_error"] = str(e)
    else:
        results["hook_logs"]["log_dir_status"] = "not_found"

    # 4. Evidence Store (check if available)
    evidence_store = Path("P:/.claude/hooks/evidence_store.py")
    if evidence_store.exists():
        results["evidence_store"]["available"] = True
        results["evidence_store"]["path"] = str(evidence_store)

        # Check if evidence store database exists
        evidence_db = Path("P:/__csf/data/cks.db")
        if evidence_db.exists():
            results["evidence_store"]["database"] = "exists"
            try:
                size_mb = evidence_db.stat().st_size / (1024 * 1024)
                results["evidence_store"]["database_size_mb"] = round(size_mb, 2)
            except OSError:
                pass
        else:
            results["evidence_store"]["database"] = "not_found"
    else:
        results["evidence_store"]["available"] = False

    # Add metadata
    results["_metadata"] = {
        "inspection_time": datetime.now().isoformat(),
        "state_dir": str(state_path),
        "state_dir_exists": state_path.exists(),
        "platform": os.name,
    }

    return results


def print_analysis(results: dict[str, Any]) -> None:
    """
    Print analysis of runtime state based on inspection results.

    Args:
        results: Runtime state inspection results from inspect_runtime_state()
    """
    print("\n=== Runtime State Analysis ===\n")

    # Session/Terminal Analysis
    print("1. Session/Terminal State:")
    session = results.get("session_terminal", {})

    session_id = session.get("session_id", "not_set")
    terminal_id = session.get("terminal_id", "not_set")
    file_session_id = session.get("file_session_id", "not_found")

    print(f"   Environment CLAUDE_SESSION_ID: {session_id}")
    print(f"   Environment CLAUDE_TERMINAL_ID: {terminal_id}")
    print(f"   File session_id: {file_session_id}")

    # Pattern 1: Terminal ID Mismatch
    if terminal_id == "not_set":
        print("   ⚠️  PATTERN DETECTED: CLAUDE_TERMINAL_ID not set in environment")
        print("      → Root cause: Terminal ID not initialized by UserPromptSubmit hook")
        print("      → Fix: Check UserPromptSubmit hook sets CLAUDE_TERMINAL_ID")
    elif file_session_id != "not_found" and file_session_id != session_id:
        print("   ⚠️  PATTERN DETECTED: Session ID mismatch")
        print(f"      → Environment: {session_id}")
        print(f"      → State file: {file_session_id}")
        print("      → Root cause: Session state not synchronized")

    # Stale state files
    stale_count = session.get("stale_count", 0)
    print(f"\n   Stale state files (>1 day old): {stale_count}")

    if stale_count > 10:
        print("   ⚠️  PATTERN DETECTED: Excessive stale state files")
        print("      → Root cause: Session cleanup not running, TTL not enforced")
        print("      → Fix: Implement TTL enforcement in intent reading")
        print("      → Action: Consider running state cleanup")

    # Pending Intents Analysis
    print("\n2. Pending Command Intents:")
    intents = results.get("pending_intents", {})
    intent_count = intents.get("count", 0)
    print(f"   Pending intent files: {intent_count}")

    if intent_count > 0:
        latest = intents.get("latest_file", "unknown")
        print(f"   Latest intent: {latest}")

        # Check for terminal ID mismatch in intents
        if "latest_content" in intents:
            content = intents["latest_content"]
            intent_terminal = content.get("terminal_id", "not_found")
            env_terminal = session.get("terminal_id", "not_set")

            if intent_terminal != env_terminal and env_terminal != "not_set":
                print("   ⚠️  PATTERN DETECTED: Terminal ID mismatch in intent")
                print(f"      → Intent terminal_id: {intent_terminal}")
                print(f"      → Environment terminal_id: {env_terminal}")
                print("      → Root cause: Intent file has stale terminal ID")
                print("      → Fix: CLAUDE_TERMINAL_ID should be set when intent is created")

    # Hook Logs Analysis
    print("\n3. Hook Execution Logs:")
    hooks = results.get("hook_logs", {})
    if hooks.get("diagnostics_available"):
        print("   ✓ Hook diagnostics available")
        print("      → Run: python P:/.claude/hooks/hook_diagnostics.py")
    else:
        print("   ✗ Hook diagnostics not found")

    log_count = hooks.get("log_files_count", 0)
    if log_count > 0:
        print(f"   Log files: {log_count}")
        print(f"   Latest log: {hooks.get('latest_log', 'unknown')}")

    # Evidence Store Analysis
    print("\n4. Evidence Store:")
    evidence = results.get("evidence_store", {})
    if evidence.get("available"):
        print("   ✓ Evidence store available")
        if evidence.get("database") == "exists":
            size_mb = evidence.get("database_size_mb", 0)
            print(f"   Database size: {size_mb} MB")
        else:
            print("   ⚠️  Database not found")
    else:
        print("   ✗ Evidence store not available")

    print("\n=== End Analysis ===\n")


def main():
    """Main entry point for command-line usage."""
    import sys

    # Parse arguments
    state_dir = None
    analyze = False

    for arg in sys.argv[1:]:
        if arg == "--analyze" or arg == "-a":
            analyze = True
        elif not arg.startswith("-"):
            state_dir = arg

    # Run inspection
    results = inspect_runtime_state(state_dir)

    if analyze:
        # Print analysis
        print_analysis(results)
    else:
        # Print raw JSON
        import pprint

        pprint.pprint(results, width=120, compact=False)


if __name__ == "__main__":
    main()
