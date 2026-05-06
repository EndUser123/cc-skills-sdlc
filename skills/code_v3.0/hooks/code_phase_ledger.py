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


def _get_terminal_id() -> str:
    """Return TERMINAL_ID env var or a hashed fallback."""
    tid = os.environ.get("CLAUDE_TERMINAL_ID", "")
    if tid:
        return tid
    cwd = os.getcwd()
    import hashlib

    return hashlib.md5(cwd.encode()).hexdigest()[:8]


def _ledger_path() -> Path:
    tid = _get_terminal_id()
    state = _STATE_DIR / tid
    state.mkdir(parents=True, exist_ok=True)
    return state / "phase-ledger.json"


def read_phase_ledger() -> dict[str, Any] | None:
    """Return the current ledger dict, or None if not yet initialized."""
    path = _ledger_path()
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_phase_marker(phase_name: str, payload: dict[str, Any] | None = None) -> None:
    """Write or update a phase entry in the ledger.

    - If ledger does not exist, create it with a session_id.
    - If phase already marked done:true, do NOT overwrite it (append-only per phase).
    - Merge payload on top of existing phase entry if present.
    """
    path = _ledger_path()
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
        "session_id": existing.get("session_id") or _get_terminal_id(),
        "phases": phases,
    }
    if "started_at" not in ledger:
        import datetime

        ledger["started_at"] = datetime.datetime.now().isoformat()

    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    # os.replace() is atomic on POSIX; on Windows it can overwrite existing
    # files unlike Path.rename(). Use os.replace as the cross-platform atomic
    # write primitive.
    os.replace(tmp_path, path)


def reset_ledger() -> None:
    """Delete the ledger file for the current terminal."""
    path = _ledger_path()
    if path.exists():
        path.unlink()
