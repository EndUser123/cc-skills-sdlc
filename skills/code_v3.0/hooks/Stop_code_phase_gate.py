#!/usr/bin/env python3
"""
Stop hook for /code skill — phase gate verification.

Checks that gateable phases were recorded in the phase ledger before
allowing DONE. Reuses code_phase_ledger.py for state access.

Exit codes (Claude Code hook semantics):
  0  = allow stop (no ledger yet — conservative on cold start)
  1  = non-blocking warning (e.g. advisory phase missing)
  2  = blocking (critical gate failed — prevents DONE)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# HARD-gated phases: must be marked done in ledger or Stop is blocked.
HARD_GATES = [
    "consumer_contract_precheck",
    "smoke_validation",
    "full_test_suite",
    "audit_quality_checks",
]

# ADVISORY phases: logged as warnings but do not block.
ADVISORY_GATES = [
    "producer_consumer_trace_verification",
]


def _ledger_path() -> Path:
    tid = os.environ.get("CLAUDE_TERMINAL_ID", "")
    if not tid:
        import hashlib
        tid = hashlib.md5(os.getcwd().encode()).hexdigest()[:8]
    state = Path.home() / ".claude" / ".state" / "code" / tid
    return state / "phase-ledger.json"


def _read_ledger() -> dict | None:
    path = _ledger_path()
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _check_fast_mode() -> bool:
    """Return True if /code ran with --fast (skip full test suite)."""
    return os.environ.get("CLAUDE_CODE_FAST_MODE", "").lower() in ("1", "true", "yes")


def main() -> None:
    ledger = _read_ledger()

    # Conservative: no ledger yet means /code never ran — allow stop
    if ledger is None:
        sys.exit(0)

    phases = ledger.get("phases", {})
    hard_failures: list[str] = []
    advisory_failures: list[str] = []
    fast_mode = _check_fast_mode()

    for phase in HARD_GATES:
        entry = phases.get(phase, {})
        if fast_mode and phase == "full_test_suite":
            continue
        if entry.get("done") is not True:
            hard_failures.append(phase)

    for phase in ADVISORY_GATES:
        entry = phases.get(phase, {})
        if entry.get("done") is not True:
            advisory_failures.append(phase)

    # Advisory warnings to stderr (exit 1)
    if advisory_failures:
        warn = (
            f"WARNING (advisory): /code completed without {len(advisory_failures)} "
            f"advisory checks: {', '.join(advisory_failures)}. "
            f"These do not block DONE but should be reviewed."
        )
        print(warn, file=sys.stderr)

    # Hard gate failures to stderr (exit 2 = blocking)
    if hard_failures:
        block = (
            f"BLOCKED: /code completed without all required phase gates.\n"
            f"Missing: {', '.join(hard_failures)}\n"
            f"Run /code --no-loop to complete all gates, "
            f"or /code --fast to acknowledge fast-mode skipping."
        )
        print(block, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
