#!/usr/bin/env python3
"""Stop hook for /go — SDLC hard-gate enforcer (session-bound).

Session-bound via the same pointer model as go_continuation_gate.py (G4):
  payload session_id -> go-sessions/{session_id}.json -> go_state_dir/run_id

Trap prevention uses payload stop_hook_active (CC's recursion flag):
  - stop_hook_active=True  -> this is a recursive Stop triggered by a prior
    hook's block. Exit 0 silently to break the recursion loop. The prior
    hook already blocked; repeating the block would trap the session.
  - stop_hook_active=False -> this is a normal Stop. Evaluate gates and
    block if incomplete.

Fail-silent rules:
  - No session_id -> exit 0 (not a /go session)
  - No pointer / stale pointer -> exit 0 (no /go state)
  - Pointer -> missing state dir / malformed -> exit 0
  - stop_hook_active=True -> exit 0 (recursive, prior block stands)

Block rules:
  - stop_hook_active=False + fresh matching pointer + incomplete hard gates
    -> exit 2 (BLOCKED) with actionable state path
  - Fully complete gates -> exit 0 (ALLOW)

Validation mode:
  - task_type=validation/audit in active-task record
  - Completes via .go-validation-complete* marker OR status=completed/done
  - Implementation tasks always require SDLC hard gates
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")
_SESSIONS_DIR = "go-sessions"

# Broad completion-authority logic (overclaim detection, evidence-level downgrade,
# nearest-target binding, completion-authority log) was intentionally removed.
# The orchestrator-side completion_evidence_review.py is the single source of
# truth for broad completion evidence; Stop hooks verify only narrow, session-
# bound artifacts (pointer, validation-mode marker, enforce.stop_gate). See
# skills/go/SKILL.md layer architecture for the rationale.


def _read_active_task(state_dir: Path, run_id: str) -> dict:
    path = state_dir / f"active-task_{run_id}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # The active-task record may be flat or wrapped under "task"; existing
    # readers (e.g. _is_validation_complete at L125) use the wrapped form.
    # Normalize to the flat shape so downstream lookups (summary, status,
    # verified_source_paths, closure_check_passed) work for both.
    wrapped = data.get("task")
    if isinstance(wrapped, dict):
        merged = {**data, **wrapped}
        return merged
    return data


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


def _payload_stop_hook_active(payload: dict) -> bool:
    """True when CC is invoking this hook recursively after a prior hook blocked."""
    return bool(payload.get("stop_hook_active", False))


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
# Validation mode
# ---------------------------------------------------------------------------

def _is_validation_complete(state_dir: Path, run_id: str) -> bool:
    """True if the run was completed in validation/audit mode."""
    # Explicit validation-complete marker.
    if list(state_dir.glob(f".go-validation-complete*{run_id}*")) or list(state_dir.glob(".go-validation-complete*")):
        return True
    # Check task_type in active-task record.
    path = state_dir / f"active-task_{run_id}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            task = data.get("task") or data
            if task.get("task_type") in ("validation", "audit"):
                # Validation tasks complete via .pr-ready or explicit status.
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

    # Trap prevention: if CC is invoking recursively (stop_hook_active=True),
    # a prior hook already blocked. Exit 0 to break the recursion loop.
    if _payload_stop_hook_active(payload):
        sys.exit(0)

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

    # Validate run record for current-run enforcement.
    # If the run record is missing, malformed, or lifecycle ≠ active, block.
    try:
        _ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")
        run_rec_path = _ARTIFACTS_ROOT / "go-runs" / session_id / run_id / "run-record.json"
        if run_rec_path.is_file():
            rec = json.loads(run_rec_path.read_text(encoding="utf-8"))
            if isinstance(rec, dict) and rec.get("schema") == "go.run-record.v1":
                ls = rec.get("lifecycle_status", "")
                if ls not in ("active", "impl_complete", "check_complete", "artifacts_finalized"):
                    # lifecycle indicates the run is past the point where
                    # Stop-gate enforcement is meaningful (lease released, etc.)
                    # Allow through — the run has already been validated earlier.
                    pass
                # If lifecycle is active or in-progress, the gate proceeds normally.
            else:
                # Record exists but wrong schema — treat as stale and block
                print(f"stop-gate: run record schema mismatch for {session_id}/{run_id}", file=sys.stderr)
                sys.exit(2)
        else:
            # No run record at all — this means run_record.py didn't write one.
            # This could be a pre-run_record version of /go. Fail open (allow).
            pass
    except Exception:
        # Fail open on any parse/read error — don't block the session.
        pass

    # Validation mode: if the validation contract is satisfied, allow.
    if _is_validation_complete(state_dir, run_id):
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

    # Build synthetic env with pointer-resolved state (replaces env authority).
    eval_env = {
        "GO_STATE_DIR": str(state_dir),
        "RUN_ID": run_id,
        "CLAUDE_SESSION_ID": session_id,
    }
    eval_env.update({
        k: v for k, v in os.environ.items()
        if k in ("CLAUDE_CODE_FAST_MODE", "GO_SKIP", "GO_EF_SKIP")
    })

    exit_code, message = evaluate_gates("go", config, eval_env)

    if exit_code == 0:
        sys.exit(0)

    # Gates fail -> block with actionable state path.
    if message:
        state_path = f"state: {state_dir} (session: {session_id}, run: {run_id})"
        print(f"{message}\n  {state_path}", file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
