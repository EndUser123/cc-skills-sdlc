#!/usr/bin/env python3
"""
Stop hook for /go (go_v3.0) — shared enforce layer.

Uses the shared stop_gate.evaluate_gates() with go_v3.0 config.
Evidence checked via Gen 2 flag files + JSON artifacts in
.claude/.artifacts/{TERMINAL_ID}/go/

INVOCATION DETECTION (v2):
- PRIMARY: Phase ledger check for go_invoked receipt (written by
  PreToolUse_go_invocation_receipt.py at /go invocation time)
- FALLBACK: Artifact age check (<60s old) only if ledger unavailable

This two-tier approach is immune to crashes, slow runs, and prose mentions.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # skills/go-ct -> cc-skills-sdlc
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforce.stop_gate import load_config_for_skill, evaluate_gates
from enforce.phase_ledger import read_phase_ledger

_SKILL_ID = "go_v3.0"
_INVOKED_PHASE = "go_invoked"


def _skill_invoked_via_ledger(session_id: str | None) -> bool:
    """Check phase ledger for invocation receipt (primary signal).

    The go_invoked phase is written by PreToolUse_go_invocation_receipt.py
    at the moment /go is invoked — BEFORE any work begins. This makes it
    immune to crashes that happen after invocation.

    SESSION VERIFICATION: Receipt is scoped to session_id. A stale receipt
    from a previous session (e.g., after session restart) will not match the
    current session_id and is ignored — preventing false enforcement.
    """
    ledger = read_phase_ledger(_SKILL_ID, session_id)
    if ledger is None:
        return False
    entry = ledger.get("phases", {}).get(_INVOKED_PHASE, {})
    if entry.get("done") is not True:
        return False
    # Verify receipt belongs to this session (prevents cross-session false enforcement)
    receipt_session_id = entry.get("session_id", "")
    if receipt_session_id and receipt_session_id != session_id:
        return False
    return True


def _skill_invoked_via_artifacts() -> bool:
    """Fallback: check for recent phase artifacts (<60s old).

    This is a secondary signal used only when the phase ledger is not
    available. It checks for recently-created flag files as a proxy for
    invocation, but cannot distinguish a crash-before-receipt from
    genuine non-invocation.
    """
    terminal_id = os.environ.get("CLAUDE_TERMINAL_ID", "")
    run_id = os.environ.get("RUN_ID", os.environ.get("CLAUDE_GO_RUN_ID", ""))

    if not terminal_id:
        return False

    go_dir = Path.home() / ".claude" / ".artifacts" / terminal_id / "go"
    now = time.time()
    age_cutoff = 60.0

    if go_dir.exists():
        for flag_pattern in (".worktree-ready_*", ".task-selected_*",
                             ".coded_*", ".verified_*"):
            for flag in go_dir.glob(flag_pattern):
                if now - flag.stat().st_mtime < age_cutoff:
                    return True

    if run_id:
        task_result = go_dir / f"task-result_{run_id}.json"
        if task_result.exists() and (now - task_result.stat().st_mtime < age_cutoff):
            return True

    return False


def _skill_actually_invoked() -> bool:
    """Return True if go_v3.0 was actually invoked this turn.

    Two-tier detection:
    1. PRIMARY: Phase ledger receipt (written at invocation time)
    2. FALLBACK: Artifact age check (<60s old) if ledger unavailable

    The ledger check is preferred because it is written at invocation
    time (not completion), making it robust to crashes and slow runs.
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID") or None

    # Tier 1: Ledger receipt (authoritative, written at invocation)
    if _skill_invoked_via_ledger(session_id):
        return True

    # Tier 2: Artifact age (fallback only)
    if _skill_invoked_via_artifacts():
        return True

    return False


def main() -> None:
    skill_id = _SKILL_ID

    if not _skill_actually_invoked():
        sys.exit(0)  # No invocation evidence = skip enforcement

    try:
        config = load_config_for_skill(skill_id)
    except KeyError:
        print(f"ERROR: no enforce config for {skill_id}", file=sys.stderr)
        sys.exit(2)

    exit_code, message = evaluate_gates(skill_id, config, os.environ)
    if message:
        print(message, file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
