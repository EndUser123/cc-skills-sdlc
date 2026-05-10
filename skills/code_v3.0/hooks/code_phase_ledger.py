#!/usr/bin/env python3
"""
Phase ledger for /code skill — records gateable phase completion.

Concurrent-session safe: one ledger per terminal_id under ~/.claude/.state/code/.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_STATE_DIR = Path.home() / ".claude" / ".state" / "code"


def get_verified_identity(session_id: str | None = None) -> dict | None:
    """Read and verify the global identity cache for the current terminal."""
    # 1. Start with the fastest heuristic-based ID (CLAUDE_TERMINAL_ID or CWD hash)
    terminal_id = _get_terminal_id()
    if not terminal_id:
        return None

    # 2. Locate the identity.json file in the canonical artifacts root
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
    """Return TERMINAL_ID env var or a hashed fallback."""
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
    cwd = os.getcwd()
    import hashlib

    return hashlib.md5(cwd.encode()).hexdigest()[:8]


def _ledger_path(session_id: str | None = None) -> Path:
    tid = _get_terminal_id(session_id)
    state = _STATE_DIR / tid
    state.mkdir(parents=True, exist_ok=True)
    return state / "phase-ledger.json"


def read_phase_ledger(session_id: str | None = None) -> dict[str, Any] | None:
    """Return the current ledger dict, or None if not yet initialized."""
    path = _ledger_path(session_id)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_phase_marker(
    phase_name: str, payload: dict[str, Any] | None = None, session_id: str | None = None
) -> None:
    """Write or update a phase entry in the ledger.

    - If ledger does not exist, create it with a session_id.
    - If phase already marked done:true, do NOT overwrite it (append-only per phase).
    - Merge payload on top of existing phase entry if present.
    """
    path = _ledger_path(session_id)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    phases: dict[str, Any] = existing.get("phases", {})
    current = phases.get(phase_name, {})

    # Append-only: don't clobber an existing done:true
    if current.get("done") is True and payload is None:
        return

    new_entry: dict[str, Any] = {"done": True}
    if payload:
        new_entry.update(payload)

    phases[phase_name] = new_entry

    ledger = {
        "session_id": existing.get("session_id") or session_id or _get_terminal_id(session_id),
        "phases": phases,
    }
    if "started_at" not in ledger:
        import datetime

        ledger["started_at"] = datetime.now().isoformat()

    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    # os.replace() is atomic on POSIX; on Windows it can overwrite existing
    # files unlike Path.rename(). Use os.replace as the cross-platform atomic
    # write primitive.
    os.replace(tmp_path, path)


def reset_ledger(session_id: str | None = None) -> None:
    """Delete the ledger file for the current terminal."""
    path = _ledger_path(session_id)
    if path.exists():
        path.unlink()
