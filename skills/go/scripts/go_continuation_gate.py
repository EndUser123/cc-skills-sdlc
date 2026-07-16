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
Wired via the plugin's __lib/router.py (settings.json hooks.Stop -> router Stop
-> this script), keeping the central hooks config free of plugin-script paths.
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

# telemetry is optional (fail-open); imported lazily in _emit.
_emit = None  # deferred import of emit_gate_telemetry

ARTIFACTS_ROOT = Path(os.environ.get("GO_ARTIFACTS_ROOT", "P:/.claude/.artifacts"))
SESSIONS_DIR_NAME = "go-sessions"
STALE_TTL_SECONDS = 6 * 3600  # 6h — see module docstring justification.

_DONE_STATUSES = {"completed", "done", "pr_ready"}

# ── /check blocker contract (explicit, versioned) ──────────────────────────
CHECK_BLOCKER_SCHEMA = "check-blocker.v1"


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


def _check_pointer_path(session_id: str) -> Path:
    """Path to the /check session pointer for this session."""
    return ARTIFACTS_ROOT / "check-sessions" / f"{session_id}.json"


def _read_check_pointer(session_id: str) -> dict | None:
    """Read the /check session pointer. None if missing/malformed."""
    path = _check_pointer_path(session_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


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
    # Completion marker on disk. Check both underscore and hyphen conventions:
    # - .pr_ready_{run_id} (underscore — used by orchestrate.py)
    # - .pr-ready_{run_id} (hyphen — used by SKILL.md STEP 7)
    if list(state_dir.glob(f".pr_ready*{run_id}*")) or list(state_dir.glob(".pr_ready*")):
        return True
    if list(state_dir.glob(f".pr-ready*{run_id}*")) or list(state_dir.glob(".pr-ready*")):
        return True
    # Explicit status in the task record.
    task = record.get("task") or record
    status = (task.get("status") or "").lower()
    return status in _DONE_STATUSES


def _check_blocker(state_dir: Path, run_id: str) -> dict | None:
    """Read the explicit /check blocker contract.

    Exact path, versioned schema. Returns the blocker dict or None if
    missing, malformed, or version-mismatched.
    """
    path = state_dir / f".check_blocker_{run_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != CHECK_BLOCKER_SCHEMA:
        return None  # version mismatch -> fail-open (do not block on unknown)
    return data


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
# Telemetry (fail-open)
# ---------------------------------------------------------------------------

def _telemetry(event: str, session_id: str = "", decision: str = "silent",
               reason: str = "") -> None:
    """Emit continuation_gate telemetry. Fail-open; never blocks the gate."""
    global _emit
    if _emit is None:
        try:
            import importlib
            _mod = importlib.import_module("orchestrate")
            _emit = getattr(_mod, "emit_gate_telemetry", None)
        except Exception:
            _emit = False  # sentinel: import failed, don't retry
    if _emit and _emit is not False:
        try:
            _emit(event=event, session_id=session_id, decision=decision, reason=reason)
        except Exception:
            pass


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
        _telemetry("no_session_id", "", "silent")
        return None  # absent/malformed identity -> silent

    pointer = _read_pointer(session_id)
    if pointer is None:
        _telemetry("no_pointer", session_id, "silent")
        return None  # no pointer / stale pointer -> silent

    state_dir = _resolve_state_dir(pointer)
    if state_dir is None:
        _telemetry("missing_state_dir", session_id, "silent")
        return None  # pointer points to missing state dir -> silent

    run_id = pointer.get("run_id") or ""
    if not run_id:
        _telemetry("malformed_pointer", session_id, "silent")
        return None  # malformed pointer -> silent

    # ── /check blocker check (independent of active-task state) ──────────
    # The blocker is the /check contract file. If it says terminal=false,
    # /check has work remaining even if no active task exists.
    blocker = _check_blocker(state_dir, run_id)
    if blocker is not None:
        # Generation check: only block if the blocker's ownership_generation
        # matches the check pointer's current generation. Otherwise the
        # blocker is from a stale /go generation (adoption has transferred
        # ownership to /check) and must be ignored.
        blocker_gen = blocker.get("ownership_generation")
        if blocker_gen is not None:
            check_ptr = _read_check_pointer(session_id)
            current_gen = (check_ptr or {}).get("ownership_generation")
            if current_gen is not None and blocker_gen != current_gen:
                # Generation mismatch → stale blocker; ignore and fall through
                # to normal active-task detection.
                _telemetry("check_blocker_stale", session_id, "silent",
                           f"gen {blocker_gen} != {current_gen}")
            elif not blocker.get("terminal", True):
                # /check says it's not done — block with its reason
                next_phase = blocker.get("next_phase", "unknown")
                reason_code = blocker.get("reason_code", "REQUIRED_PHASE_INCOMPLETE")
                reason = f"continue: {next_phase} — {reason_code} (check)"
                _telemetry("check_blocker", session_id, "block", reason)
                return {"decision": "block", "reason": reason}
        elif not blocker.get("terminal", True):
            # No generation field in blocker — legacy blocker without generation.
            # Block (conservative) since we can't verify freshness.
            next_phase = blocker.get("next_phase", "unknown")
            reason_code = blocker.get("reason_code", "REQUIRED_PHASE_INCOMPLETE")
            reason = f"continue: {next_phase} — {reason_code} (check)"
            _telemetry("check_blocker_legacy", session_id, "block", reason)
            return {"decision": "block", "reason": reason}
        else:
            # /check says terminal — clean up the blocker and proceed normally
            blocker_path = state_dir / f".check_blocker_{run_id}.json"
            try:
                blocker_path.unlink(missing_ok=True)
            except OSError:
                pass

    record = _load_active_task(state_dir, run_id)
    if record is None:
        _telemetry("no_active_task", session_id, "silent")
        return None  # no active task -> silent (done or never started)

    if _is_done(record, state_dir, run_id):
        _telemetry("done", session_id, "silent")
        return None  # completed -> silent

    # Active, not done -> work remaining -> BLOCK.
    reason = _block_reason(record, state_dir, run_id)
    _telemetry("block", session_id, "block", reason)
    return {"decision": "block", "reason": reason}


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
