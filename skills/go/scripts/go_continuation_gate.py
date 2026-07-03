#!/usr/bin/env python3
"""Session-bound deterministic continuation gate for /go task-completion goals.

Identity binding: payload session_id -> pointer file -> state dir. No env
lookup, no terminal_id, no mtime selection, no machine-wide globbing.

Strict Stop-hook contract:
  - Work remaining for the matching, fresh, in-identity run:
    print {"decision":"block","reason":"continue: <next step>"}; exit 0.
  - Done / allow / no-state / foreign / stale / missing pointer:
    print NOTHING; exit 0.
  - Never prints {}, {"decision":"approve"}, or any other allow payload.

Pointer model
-------------
/orchestrate.py writes ``{artifacts}/go-sessions/{session_id}.json`` at run
start containing ``{"go_state_dir": "...", "run_id": "...", "updated_at": "..."}``.
The gate reads this pointer (atomic write, no race), resolves the state dir,
and inspects the active-task record and completion markers there.

Stale rule
----------
A run whose pointer has not been updated in STALE_TTL_SECONDS (6h) is treated
as abandoned. Justification: a healthy /go run updates its pointer on every
orchestration step (minutes); even slow dispatches finish well under 6h; 6h
survives manual review pauses while ensuring yesterday's abandoned run cannot
block today's session. Stale + incomplete -> silent (never block).

Continuation semantics
----------------------
- done = .pr_ready OR explicit "completed"/"done" in active-task status -> silent
- active task present, not done -> work remaining -> BLOCK
- .blocked_* refines the reason string but is NOT required to block
- No hardcoded phase lists; semantics are driven by the task record state

Self-scoping & fail-silent
--------------------------
This is a direct project-settings entry (P:/.claude/settings.json hooks.Stop[3]
-> source path), NOT wired through the plugin's hooks/hooks.json. It prints
nothing whenever session_id is absent, pointer is missing, pointer is stale,
or state is foreign -> inert in every non-/go session. ADDITIVE to the native
goal-loop evaluator; does not replace it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")
SESSIONS_DIR_NAME = "go-sessions"
STALE_TTL_SECONDS = 6 * 3600  # 6h — see module docstring justification.

_DONE_STATUSES = {"completed", "done", "pr_ready"}


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------

def _parse_payload() -> dict:
    """Read and parse the Stop stdin payload. Empty/invalid -> {}."""
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _payload_session_id(payload: dict) -> str:
    """Extract session_id from the Stop payload (may be empty)."""
    sid = payload.get("session_id") or payload.get("sessionId") or ""
    return sid if isinstance(sid, str) else ""


# ---------------------------------------------------------------------------
# Pointer resolution
# ---------------------------------------------------------------------------

def _pointer_path(session_id: str) -> Path:
    return ARTIFACTS_ROOT / SESSIONS_DIR_NAME / f"{session_id}.json"


def _read_pointer(session_id: str) -> dict | None:
    """Read the session pointer file, or None if missing/malformed/stale."""
    ptr = _pointer_path(session_id)
    if not ptr.is_file():
        return None
    try:
        data = json.loads(ptr.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    # Stale check on the pointer itself.
    updated = data.get("updated_at") or ""
    ts = _parse_iso_timestamp(updated)
    if ts is not None and (time.time() - ts) > STALE_TTL_SECONDS:
        return None
    return data


def _resolve_state_dir(pointer: dict) -> Path | None:
    """Resolve the state dir from the pointer, verifying it exists."""
    raw = pointer.get("go_state_dir")
    if not raw or not isinstance(raw, str):
        return None
    d = Path(raw)
    return d if d.is_dir() else None


# ---------------------------------------------------------------------------
# Active-task inspection
# ---------------------------------------------------------------------------

def _load_active_task(state_dir: Path, run_id: str) -> dict | None:
    """Load the active-task record for the given run, or None."""
    path = state_dir / f"active-task_{run_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _is_done(record: dict, state_dir: Path, run_id: str) -> bool:
    """True if the run is complete (.pr_ready or explicit task status)."""
    # Completion marker on disk.
    if list(state_dir.glob(f".pr_ready*{run_id}*")) or list(state_dir.glob(".pr_ready*")):
        return True
    # Explicit status in the task record.
    task = record.get("task") or record
    status = (task.get("status") or "").lower()
    return status in _DONE_STATUSES


def _block_reason(record: dict, state_dir: Path, run_id: str) -> str:
    """Build the 'continue: ...' reason string."""
    title = (record.get("task") or {}).get("title", "go run")
    # If .blocked_* exists, refine reason with its content.
    for bf in state_dir.glob(f".blocked*{run_id}*"):
        bj = state_dir / f"blocked_{bf.stem.replace('.', '')}.json"
        if bj.exists():
            try:
                bd = json.loads(bj.read_text(encoding="utf-8"))
                reason = bd.get("reason_code", bd.get("phase", "blocked"))
                return f"continue: {reason} — {title}"
            except (json.JSONDecodeError, OSError):
                pass
    # No .blocked_* — still work remaining (active, not done).
    return f"continue: active — {title}"


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def check_go_completion(payload: dict | None = None) -> dict | None:
    """Return a block dict only when THIS session's fresh /go run has work left.

    Binding: payload session_id -> pointer file -> state dir -> active-task.
    Returns {"decision":"block","reason":"continue: ..."} when the run is
    active and not done. Returns None (print nothing) for all other cases:
    done, no payload session_id, no pointer, stale pointer, missing state dir,
    no active task, malformed data.
    """
    payload = payload if payload is not None else _parse_payload()
    if not isinstance(payload, dict):
        return None

    session_id = _payload_session_id(payload)
    if not session_id:
        return None  # absent/malformed identity -> silent

    pointer = _read_pointer(session_id)
    if pointer is None:
        return None  # no pointer / stale pointer -> silent

    state_dir = _resolve_state_dir(pointer)
    if state_dir is None:
        return None  # pointer points to missing state dir -> silent

    run_id = pointer.get("run_id") or ""
    if not run_id:
        return None  # malformed pointer -> silent

    record = _load_active_task(state_dir, run_id)
    if record is None:
        return None  # no active task -> silent (done or never started)

    if _is_done(record, state_dir, run_id):
        return None  # completed -> silent

    # Active, not done -> work remaining -> BLOCK.
    return {"decision": "block", "reason": _block_reason(record, state_dir, run_id)}


def main() -> None:
    """CLI entry. Prints ONLY on block; silent on allow/fail-open."""
    result = check_go_completion()
    if isinstance(result, dict) and result.get("decision") == "block":
        sys.stdout.write(json.dumps(result))
        sys.stdout.flush()
    # Otherwise: print nothing (strict Stop allow/fail-open contract).


def _parse_iso_timestamp(value) -> float | None:
    """Parse an ISO-8601 timestamp to epoch seconds, or None."""
    if not value or not isinstance(value, str):
        return None
    try:
        from datetime import datetime
        ts = value.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).timestamp()
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    main()
