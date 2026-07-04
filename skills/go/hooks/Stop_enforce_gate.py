#!/usr/bin/env python3
"""Stop hook for /go — SDLC hard-gate enforcer (session-bound).

Session-bound via the same pointer model as go_continuation_gate.py (G4):
  payload session_id -> go-sessions/{session_id}.json -> go_state_dir/run_id

Replaces the old env-based authority (GO_STATE_DIR, CLAUDE_TERMINAL_ID,
mtime globs) which was unreliable in hook subprocesses where those env
vars are empty.

Fail-silent rules:
  - No session_id in payload -> exit 0 (not a /go session)
  - No pointer file -> exit 0 (no /go state)
  - Stale pointer (>6h) -> exit 0 (abandoned run)
  - Pointer points to missing state dir -> exit 0
  - Malformed pointer/state -> exit 0

Block rules:
  - Fresh matching pointer + incomplete hard gates -> exit 2 (BLOCKED)
  - Validation mode (go-validation-complete marker) -> exit 0 (ALLOW)

Prevent hook trap:
  - If the same session_id+run_id blocked on the PREVIOUS Stop call
    (tracked via a temp file), emit the block only once and exit 0 on
    subsequent calls to avoid infinite blocking.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")
_SESSIONS_DIR = "go-sessions"
_STALE_TTL_SECONDS = 6 * 3600  # 6h — same as G4

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Payload + pointer resolution (same model as G4)
# ---------------------------------------------------------------------------

def _parse_payload() -> dict:
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
    sid = payload.get("session_id") or payload.get("sessionId") or ""
    return sid if isinstance(sid, str) else ""


def _read_pointer(session_id: str) -> dict | None:
    ptr = _ARTIFACTS_ROOT / _SESSIONS_DIR / f"{session_id}.json"
    if not ptr.is_file():
        return None
    try:
        data = json.loads(ptr.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    updated = data.get("updated_at") or ""
    ts = _parse_iso_timestamp(updated)
    if ts is not None and (time.time() - ts) > _STALE_TTL_SECONDS:
        return None  # stale
    return data


def _resolve_state_dir(pointer: dict) -> Path | None:
    raw = pointer.get("go_state_dir")
    if not raw or not isinstance(raw, str):
        return None
    d = Path(raw)
    return d if d.is_dir() else None


def _parse_iso_timestamp(value) -> float | None:
    if not value or not isinstance(value, str):
        return None
    try:
        from datetime import datetime
        ts = value.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).timestamp()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Hook-trap prevention
# ---------------------------------------------------------------------------

def _block_fingerprint(session_id: str, run_id: str) -> Path:
    """Temp file that tracks the last block for this session+run."""
    return _ARTIFACTS_ROOT / ".go-g5-last-block.json"


def _was_already_blocked(session_id: str, run_id: str) -> bool:
    fp = _block_fingerprint(session_id, run_id)
    if not fp.is_file():
        return False
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return data.get("session_id") == session_id and data.get("run_id") == run_id
    except (json.JSONDecodeError, OSError):
        return False


def _record_block(session_id: str, run_id: str) -> None:
    fp = _block_fingerprint(session_id, run_id)
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(".tmp")
        tmp.write_text(json.dumps({"session_id": session_id, "run_id": run_id}), encoding="utf-8")
        tmp.replace(fp)
    except OSError:
        pass


def _clear_block(session_id: str, run_id: str) -> None:
    fp = _block_fingerprint(session_id, run_id)
    try:
        fp.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Validation mode
# ---------------------------------------------------------------------------

def _is_validation_complete(state_dir: Path, run_id: str) -> bool:
    """True if the run was completed in validation/audit mode."""
    # Check for go-validation-complete marker
    if list(state_dir.glob(f".go-validation-complete*{run_id}*")) or list(state_dir.glob(".go-validation-complete*")):
        return True
    # Check task_type in active-task record
    path = state_dir / f"active-task_{run_id}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            task = data.get("task") or data
            if task.get("task_type") in ("validation", "audit"):
                # Validation tasks: check if the validation contract is satisfied
                # (at minimum: .pr-ready or status=completed)
                if list(state_dir.glob(f".pr-ready*{run_id}*")) or list(state_dir.glob(f".pr_ready*{run_id}*")):
                    return True
                status = (task.get("status") or "").lower()
                if status in ("completed", "done"):
                    return True
        except (json.JSONDecodeError, OSError):
            pass
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    payload = _parse_payload()
    session_id = _payload_session_id(payload)

    # No session_id -> not a /go session -> fail silent.
    if not session_id:
        sys.exit(0)

    pointer = _read_pointer(session_id)
    # No pointer / stale pointer -> fail silent.
    if pointer is None:
        sys.exit(0)

    state_dir = _resolve_state_dir(pointer)
    # Missing state dir -> fail silent.
    if state_dir is None:
        sys.exit(0)

    run_id = pointer.get("run_id") or ""
    # Malformed pointer (no run_id) -> fail silent.
    if not run_id:
        sys.exit(0)

    # Validation mode: if the validation contract is satisfied, allow.
    if _is_validation_complete(state_dir, run_id):
        _clear_block(session_id, run_id)
        sys.exit(0)

    # Load enforce config.
    try:
        from enforce.stop_gate import load_config_for_skill, evaluate_gates
    except ImportError:
        sys.exit(0)  # enforce module unavailable -> fail silent

    try:
        config = load_config_for_skill("go")
    except KeyError:
        sys.exit(0)  # no config -> fail silent

    # Build a synthetic env with the resolved state for evaluate_gates.
    # This replaces the unreliable env-based authority with the pointer-resolved
    # state dir and run_id.
    eval_env = {
        "GO_STATE_DIR": str(state_dir),
        "RUN_ID": run_id,
        "CLAUDE_SESSION_ID": session_id,
    }
    # Also include actual env for fast_mode, GO_SKIP, etc.
    eval_env.update({
        k: v for k, v in os.environ.items()
        if k in ("CLAUDE_CODE_FAST_MODE", "GO_SKIP", "GO_EF_SKIP")
    })

    exit_code, message = evaluate_gates("go", config, eval_env)

    if exit_code == 0:
        # Gates pass -> clear any previous block record.
        _clear_block(session_id, run_id)
        sys.exit(0)

    # Gates fail -> block.
    # Check if we already blocked for this session+run (prevent hook trap).
    if _was_already_blocked(session_id, run_id):
        # Already blocked once -> fail silent to prevent infinite blocking.
        sys.exit(0)

    # Record this block and emit.
    _record_block(session_id, run_id)
    if message:
        # Add actionable state path to the message.
        state_path = f"state: {state_dir} (session: {session_id}, run: {run_id})"
        enhanced = f"{message}\n  {state_path}"
        print(enhanced, file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
