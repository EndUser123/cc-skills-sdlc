#!/usr/bin/env python3
"""
PreToolUse hook for /code skill - Verification phase order enforcement

Enforces critical path: BUILD → STATIC ANALYSIS → TRACE → SHIP
Planning phases (BOOTSTRAP, ALIGN, DESIGN) are flexible.

Usage: This hook is automatically called when /code skill is invoked
Input: JSON via stdin with tool details
Output: JSON via stdout with allow/deny decision
"""

import json
import sys
from pathlib import Path

# State directory for phase markers (home-directory based, not project-relative)
STATE_DIR = Path.home() / ".claude" / ".state" / "code"

# Phase marker files
BUILD_MARKER = STATE_DIR / "code-build-complete.marker"
STATIC_ANALYSIS_MARKER = STATE_DIR / "code-static-analysis-complete.marker"
TRACE_MARKER = STATE_DIR / "code-trace-complete.marker"


def main():
    # Read JSON input from stdin
    input_data = json.loads(sys.stdin.read())

    # Extract phase from input (e.g., --phase=3)
    args = input_data.get("tool_input", {}).get("args", [])
    phase = "auto"

    for arg in args:
        if arg.startswith("--phase="):
            phase = arg.split("=")[1]
            break

    # Extract tool name
    tool = input_data.get("tool_name", "")

    # Only validate Skill() calls for /code skill
    if tool != "Skill":
        # Not a Skill call - allow it
        print(json.dumps({"continue": True}))
        sys.exit(0)

    # Extract skill name
    skill = input_data.get("tool_input", {}).get("name", "")

    if skill != "code":
        # Not /code skill - allow it
        print(json.dumps({"continue": True}))
        sys.exit(0)

    # Validate phase order based on explicit --phase flag or detected phase
    if phase in ("0", "bootstrap"):
        # Phase 0 (BOOTSTRAP) - always allowed, no prerequisites
        print(json.dumps({"continue": True}))
        sys.exit(0)

    elif phase in ("1", "align"):
        # Phase 1 (ALIGN) - always allowed (first planning phase)
        print(json.dumps({"continue": True}))
        sys.exit(0)

    elif phase in ("2", "design"):
        # Phase 2 (DESIGN) - always allowed (planning phases are flexible)
        print(json.dumps({"continue": True}))
        sys.exit(0)

    elif phase in ("3", "build"):
        # Phase 3 (BUILD) - always allowed (first execution phase)
        print(json.dumps({"continue": True}))
        sys.exit(0)

    elif phase in ("3.4", "static-analysis"):
        # Phase 3.4 (STATIC ANALYSIS) - requires BUILD marker
        if not BUILD_MARKER.exists():
            result = {
                "continue": False,
                "reason": "Cannot run STATIC ANALYSIS before BUILD completes. Run /code without --phase flag to auto-detect phase.",
            }
            print(json.dumps(result), file=sys.stderr)
            sys.exit(2)

    elif phase in ("3.5", "trace"):
        # Phase 3.5 (TRACE) - requires BUILD + STATIC ANALYSIS markers
        if not BUILD_MARKER.exists():
            result = {
                "continue": False,
                "reason": "Cannot run TRACE before BUILD completes. TRACE needs built code to analyze. Run /code without --phase flag to auto-detect phase.",
            }
            print(json.dumps(result), file=sys.stderr)
            sys.exit(2)

        # Note: STATIC ANALYSIS is recommended but not blocking for TRACE
        # TRACE can run without STATIC ANALYSIS if user wants manual verification first

    elif phase in ("4", "ship"):
        # Phase 4 (SHIP) - requires BUILD + TRACE markers (STATIC ANALYSIS is recommended)
        if not BUILD_MARKER.exists():
            result = {
                "continue": False,
                "reason": "Cannot SHIP before BUILD completes. Run /code without --phase flag to auto-detect phase.",
            }
            print(json.dumps(result), file=sys.stderr)
            sys.exit(2)

        if not TRACE_MARKER.exists():
            result = {
                "continue": False,
                "reason": "Cannot SHIP before TRACE completes. TRACE catches 60-80% of logic errors that tests miss. This is a critical safety gate.",
            }
            print(json.dumps(result), file=sys.stderr)
            sys.exit(2)

    elif phase in ("auto", ""):
        # Auto-detect mode - always allowed (workflow will determine phase)
        print(json.dumps({"continue": True}))
        sys.exit(0)

    else:
        # Unknown phase - allow it (will be handled by workflow)
        print(json.dumps({"continue": True}))
        sys.exit(0)

    # If we get here, all checks passed
    print(json.dumps({"continue": True}))
    sys.exit(0)


if __name__ == "__main__":
    main()
