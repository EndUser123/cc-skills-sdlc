"""Event logging helpers for contract-sensitive boundary crossings."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _detect_terminal_id() -> str:
    """Detect terminal identifier using the same logic as hook_ledger.py."""
    wt = os.environ.get("WT_SESSION", "")
    if wt:
        return f"console_{wt}"
    return "unknown"


def _get_event_log_path() -> Path:
    """Return the terminal-scoped event log path."""
    state_dir = Path("P:\\\\\\.claude/state")
    terminal_id = _detect_terminal_id()
    return state_dir / f"contract_events_{terminal_id}.jsonl"


def log_contract_event(
    event_type: str,
    boundary_id: str,
    payload: dict[str, Any],
    validator: str = "",
    result: str = "",
) -> Path:
    """Append a contract event to the terminal-scoped JSONL log.

    Parameters
    ----------
    event_type : str
        Type of event (e.g., "validation_pass", "validation_fail",
        "boundary_crossed").
    boundary_id : str
        Identifier of the boundary being crossed.
    payload : dict
        Event payload data.
    validator : str
        Name of the validator that produced this event.
    result : str
        Outcome of the validation (e.g., "pass", "fail", "block").

    Returns
    -------
    Path
        Path to the event log file that was written.
    """
    log_path = _get_event_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "event_type": event_type,
        "boundary_id": boundary_id,
        "validator": validator,
        "result": result,
        "timestamp": int(time.time()),
        "payload": payload,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return log_path
