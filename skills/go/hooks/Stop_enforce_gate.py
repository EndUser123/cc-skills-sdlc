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

# Completion-authority overclaim terms (re-asserted per session; signal=overclaim)
_OVERCLAIM_TERMS = frozenset({
    "complete", "completed", "fix", "fixed", "ship", "shipped", "production",
    "available", "enforced", "absorbed", "cache rebuilt", "tests passed",
    "zero drift", "verified", "runtime-delivered", "live",
})


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


def _detect_overclaim(text: str) -> list[str]:
    """Return list of overclaim terms found in lowercase text."""
    if not text:
        return []
    lower = text.lower()
    return sorted(t for t in _OVERCLAIM_TERMS if t in lower)


def _has_evidence_file(state_dir: Path, run_id: str, kind: str) -> bool:
    """True if a verification-packet artifact exists for this run."""
    for pat in (f".{kind}*{run_id}*", f".{kind}_*", f"{kind}-{run_id}*"):
        if any(state_dir.glob(pat)):
            return True
    return False


def _evaluate_completion_evidence(active: dict, state_dir: Path, run_id: str) -> dict:
    """Map each claim to the highest level the evidence supports.

    Levels: asserted_by_worker < source_inspected < tests_passed <
            real_entrypoint_smoked < cache_or_runtime_verified <
            field_confirmed_against_original_symptom.
    """
    levels = []
    if active:
        levels.append("asserted_by_worker")  # anything in the record is at least worker-asserted
    if active.get("verified_source_paths"):
        for p in active["verified_source_paths"]:
            if Path(p).exists():
                levels.append("source_inspected")
                break
    if _has_evidence_file(state_dir, run_id, "test-pass") or active.get("tests_pass"):
        levels.append("tests_passed")
    if _has_evidence_file(state_dir, run_id, "smoke") or active.get("smoke_ok"):
        levels.append("real_entrypoint_smoked")
    if _has_evidence_file(state_dir, run_id, "cache-rebuild") or active.get("cache_ok"):
        levels.append("cache_or_runtime_verified")
    if active.get("closure_check_passed") is True:
        levels.append("field_confirmed_against_original_symptom")
    return {"levels": levels, "highest": levels[-1] if levels else "asserted_by_worker"}


def _downgrade_from_overclaim(levels: list[str], overclaim_terms: list[str]) -> dict:
    """Map overclaim terms + highest evidence level to a downgrade verdict.

    Downgrade rules (per goal req 4):
      - all overclaim terms + no source_inspected      -> INCOMPLETE
      - shipped/available/absorbed/production/live terms  -> PENDING/UNVERIFIED
      - fixed/complete term without field_confirmed     -> INCOMPLETE
      - else                                            -> ADVISORY
    """
    high = levels[-1] if levels else "asserted_by_worker"
    shipping = {"shipped", "available", "absorbed", "production", "runtime-delivered", "live"}
    fix_or_complete = {"complete", "completed", "fix", "fixed", "tests passed", "zero drift", "cache rebuilt", "verified", "enforced"}

    if not overclaim_terms:
        return {"downgrade": "ADVISORY", "reason": "no overclaim terms detected", "highest": high}

    is_shipping = bool(shipping & set(overclaim_terms))
    is_fix = bool(fix_or_complete & set(overclaim_terms))

    if is_shipping and "source_inspected" not in levels:
        return {"downgrade": "BLOCK", "reason": f"shipping claim without source_inspected (terms: {sorted(shipping & set(overclaim_terms))})", "highest": high}
    if is_shipping:
        return {"downgrade": "INCOMPLETE", "reason": f"shipping claim missing field-confirmed evidence", "highest": high}
    if is_fix and "field_confirmed_against_original_symptom" not in levels:
        return {"downgrade": "BLOCK", "reason": f"fixed/complete claim without field_confirmed (terms: {sorted(fix_or_complete & set(overclaim_terms))})", "highest": high}
    return {"downgrade": "ADVISORY", "reason": f"overclaim present (terms: {overclaim_terms})", "highest": high}


def _write_completion_log(state_dir: Path, run_id: str, verdict: dict) -> None:
    """Append-only log of completion-authority verdicts. Fail-silent on write error."""
    try:
        log_path = state_dir / f"completion-authority_{run_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            entry = {
                "ts": time.time(),
                "run_id": run_id,
                "downgrade": verdict.get("downgrade"),
                "reason": verdict.get("reason"),
                "highest": verdict.get("highest"),
            }
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _select_nearest_target(state_dir: Path, run_id: str) -> dict:
    """Nearest-target binding rule: the most recent completion-authority log
    entry in this run is the target report (the work just declared done)."""
    log_path = state_dir / f"completion-authority_{run_id}.jsonl"
    if not log_path.is_file():
        return {}
    last = None
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            last = json.loads(line)
    except (json.JSONDecodeError, OSError):
        return {}
    return last if isinstance(last, dict) else {}


def evaluate_completion_authority(state_dir: Path, run_id: str) -> dict:
    """Public entry: classify /go's claim-to-done against the evidence record.

    Returns: {downgrade, reason, highest, levels, overclaim_terms, target}.
    """
    active = _read_active_task(state_dir, run_id)
    target = _select_nearest_target(state_dir, run_id) or {}
    # Compose the text the worker used to declare done. Preference order:
    # 1) latest completion-authority log (the report just emitted)
    # 2) active-task summary field
    # 3) status field
    claim_text = " ".join(str(v) for v in [
        target.get("reason") or "",
        active.get("summary") or "",
        active.get("status") or "",
    ]).strip()
    overclaim = _detect_overclaim(claim_text)
    levels = _evaluate_completion_evidence(active, state_dir, run_id)
    downgrade = _downgrade_from_overclaim(levels["levels"], overclaim)
    downgrade["overclaim_terms"] = overclaim
    downgrade["levels"] = levels["levels"]
    downgrade["target"] = "active_task"
    return downgrade
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

    # Completion-authority gate: downgrade overclaim before /go declares done.
    # Fail-soft: advisory downgrade is logged only; block only on
    # "BLOCK" downgrade (incomplete or missing required packet for high-risk).
    try:
        verdict = evaluate_completion_authority(state_dir, run_id)
    except Exception as _e:
        # Fail-silent: don't block /go on a gate failure; log the reason.
        verdict = {"downgrade": "ADVISORY", "reason": f"gate-error: {_e}"}
    _write_completion_log(state_dir, run_id, verdict)
    if verdict.get("downgrade") == "BLOCK":
        reason = verdict.get("reason") or "Completion claim lacks required evidence"
        # cc-skills-sdlc CLAUDE.md stop-output contract: emit {"decision":"block",...}
        # and exit 0. Reason must lead with "continue: " so CC continues the loop.
        print(json.dumps({"decision": "block", "reason": f"continue: {reason}"}))
        sys.exit(0)

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
