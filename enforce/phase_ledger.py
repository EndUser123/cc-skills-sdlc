#!/usr/bin/env python3
"""
Shared phase ledger — skill-agnostic, config-driven phase tracking.

State lives at: ~/.claude/.state/enforce/{skill_id}/{terminal_id}/phase-ledger.json

Key design:
- One ledger per (skill_id, terminal_id) pair — fully concurrent-safe.
- Append-only per phase: once marked done:true, never overwritten unless
  payload is provided (merge-instead-of-clobber).
- Atomic writes via os.replace() for cross-platform safety.
- skill_id is the namespace — the library is completely reusable across skills.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any

_STATE_ROOT = Path.home() / ".claude" / ".state" / "enforce"


def get_verified_identity(session_id: str | None = None) -> dict | None:
    """Read and verify the global identity cache for the current terminal.

    This implements a 'Handshake' pattern: we only trust the cached identity
    if it matches our live session_id. This prevents using stale data from
    a previous session in the same terminal.
    """
    # 1. Start with the fastest heuristic-based ID (CLAUDE_TERMINAL_ID or CWD hash)
    terminal_id = _get_terminal_id()
    if not terminal_id:
        return None

    # 2. Locate the identity.json file in the canonical artifacts root
    # Matching $CLAUDE_ROOT/hooks\SessionStart_identity_capture.py
    # Fixed to use drive root .claude/.artifacts
    artifacts_root = Path(Path.cwd().anchor) / ".claude" / ".artifacts"
    safe_tid = terminal_id.replace("/", "-").replace("\\", "-").replace(":", "-")
    identity_file = artifacts_root / safe_tid / "identity.json"

    if not identity_file.exists():
        return None

    # 3. THE HANDSHAKE: Verify against live session_id
    try:
        identity = json.loads(identity_file.read_text(encoding="utf-8"))
        if session_id:
            cached_sid = identity.get("claude", {}).get("session_id")
            if cached_sid and cached_sid != session_id:
                # Stale data: identity file belongs to a DIFFERENT session
                return None
        return identity
    except (json.JSONDecodeError, OSError):
        return None


def _get_terminal_id(session_id: str | None = None) -> str:
    # Opportunistic Handshake: use identity.json if verified
    if session_id:
        identity = get_verified_identity(session_id)
        if identity:
            tid = identity.get("terminal", {}).get("id")
            if tid:
                return tid

    tid = os.environ.get("CLAUDE_TERMINAL_ID", "")
    if tid:
        return tid
    # Fallback: hash of CWD so concurrent terminals get separate ledgers
    return hashlib.md5(os.getcwd().encode()).hexdigest()[:8]


def _ledger_path(skill_id: str, session_id: str | None = None) -> Path:
    tid = _get_terminal_id(session_id)
    state = _STATE_ROOT / skill_id / tid
    state.mkdir(parents=True, exist_ok=True)
    return state / "phase-ledger.json"


def read_phase_ledger(skill_id: str, session_id: str | None = None) -> dict[str, Any] | None:
    """Return the current ledger dict for skill_id, or None if not initialized."""
    path = _ledger_path(skill_id, session_id)
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_phase_marker(
    skill_id: str,
    phase_name: str,
    payload: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> None:
    """Write or update a phase entry in the ledger.

    - Creates ledger with session_id if it doesn't exist.
    - If phase already done:true and no payload provided, skips (append-only guard).
    - If payload provided, merges on top of existing phase entry.
    """
    path = _ledger_path(skill_id, session_id)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    phases: dict[str, Any] = existing.get("phases", {})
    current = phases.get(phase_name, {})

    # Append-only guard: don't clobber existing done:true without payload
    if current.get("done") is True and payload is None:
        return

    new_entry: dict[str, Any] = {"done": True}
    if payload:
        new_entry.update(payload)

    phases[phase_name] = new_entry

    ledger: dict[str, Any] = {
        "session_id": existing.get("session_id") or session_id or _get_terminal_id(session_id),
        "skill_id": skill_id,
        "phases": phases,
    }
    if "started_at" not in ledger:
        ledger["started_at"] = datetime.datetime.now().isoformat()

    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    # os.replace() is atomic on both POSIX and Windows
    os.replace(tmp, path)


def reset_phase_ledger(skill_id: str, session_id: str | None = None) -> None:
    """Best-effort delete of the ledger for skill_id + current terminal."""
    path = _ledger_path(skill_id, session_id)
    if path.exists():
        path.unlink()