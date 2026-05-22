#!/usr/bin/env python3
"""
PreToolUse hook for /go (go_v3.0) — invocation receipt writer.

Writes an atomic invocation receipt to the phase ledger when /go is invoked.
This is the authoritative invocation signal for Stop_enforce_gate.py.

The receipt is written BEFORE any skill work begins, making it immune to:
- Skill crashes (receipt written at invocation, not completion)
- Slow runs (receipt exists immediately, no 60s delay)
- Prose mentions (receipt only exists for actual invocations)
"""

from __future__ import annotations

import os
import sys
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # skills/go-ct -> cc-skills-sdlc
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforce.phase_ledger import write_phase_marker

_SKILL_ID = "go_v3.0"
_INVOKED_PHASE = "go_invoked"


def _is_go_invocation(prompt: str) -> bool:
    """Return True if the user prompt is a /go command invocation."""
    if not prompt:
        return False
    # Match /go at the start of the prompt (with optional whitespace)
    # Covers: "/go", "/go fix auth", "/go\nimplement feature", etc.
    return bool(re.match(r"^\s*/go\b", prompt.strip()))


def main() -> None:
    """Write invocation receipt if this turn is a /go invocation."""
    # Read user prompt from stdin
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)  # No input = allow

    try:
        data = __import__("json").loads(raw.lstrip("﻿"))
    except Exception:
        sys.exit(0)  # Malformed input = allow

    if not isinstance(data, dict):
        sys.exit(0)

    # Check user_prompt field (canonical field name per hook protocol)
    user_prompt = data.get("user_prompt", "")
    if not _is_go_invocation(user_prompt):
        sys.exit(0)  # Not a /go invocation = allow

    # Get terminal and session IDs for ledger scoping
    terminal_id = os.environ.get("CLAUDE_TERMINAL_ID", "")
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    run_id = os.environ.get("RUN_ID", os.environ.get("CLAUDE_GO_RUN_ID", ""))

    if not terminal_id:
        sys.exit(0)  # Cannot scope = allow (fail-open)

    # Write the invocation receipt to the phase ledger
    # This is written BEFORE any skill work begins, so it survives crashes
    write_phase_marker(
        skill_id=_SKILL_ID,
        phase_name=_INVOKED_PHASE,
        payload={
            "run_id": run_id,
            "terminal_id": terminal_id,
            "session_id": session_id,
        },
        session_id=session_id,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
