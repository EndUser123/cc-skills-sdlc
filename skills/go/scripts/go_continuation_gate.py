#!/usr/bin/env python3
"""Session-bound deterministic continuation gate for /go task-completion goals.

Multi-terminal safe, stale-state immune. Reads the Stop stdin payload and binds
decisions to the CURRENT session/terminal identity — it never selects state
machine-wide by mtime.

Strict Stop-hook contract:
  - Work remaining for the matching, fresh, in-identity run:
    print {"decision":"block","reason":"continue: <next step>"}; exit 0.
  - Done / allow / no-state / foreign / stale / ambiguous / malformed identity:
    print NOTHING; exit 0.
  - Never prints {}, {"decision":"approve"}, or any other allow payload.

Binding model
-------------
The Stop payload carries ``session_id`` (and ``transcript_path``). The gate
derives ``terminal_id`` from its own env (same process tree as the session).
The /go state tree is namespaced as ``{artifacts}/{terminal_id}/go/`` — so the
gate reads ONLY that one dir. Within it, if the payload carries a session_id
and the recorded state carries one, they must match (else foreign → silent).
If multiple active-task files exist in the bound dir, the payload session_id
disambiguates; absent that, the newest WITHIN the bound dir is used (this is
NOT machine-wide selection — the dir is already terminal-scoped).

Stale rule
----------
A run whose state has not been touched in ``STALE_TTL_SECONDS`` (6h) is treated
as abandoned. Justification: a healthy /go run writes a phase marker every
step (minutes); even a slow pi dispatch updates well under 6h. 6h survives long
dispatches and manual review pauses while ensuring yesterday's abandoned run
cannot block today's session. Stale + incomplete → silent (never block).

Self-scoping & fail-silent
--------------------------
This is a direct project-settings entry (``P:/.claude/settings.json``
``hooks.Stop[3]`` → source path), NOT wired through the plugin's
``hooks/hooks.json``. It prints nothing whenever identity is absent, the bound
dir is missing, or state is foreign/stale/ambiguous — so it is inert in every
non-/go session. It is ADDITIVE to the native goal-loop evaluator and does not
replace it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")
STALE_TTL_SECONDS = 6 * 3600  # 6h — see module docstring justification.


# ---------------------------------------------------------------------------
# Identity + payload parsing
# ---------------------------------------------------------------------------

def _parse_payload() -> dict:
    """Read and parse the Stop stdin payload. Empty/invalid → {}."""
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


def _terminal_id() -> str:
    """Derive the current terminal identity from env (best-effort)."""
    for var in ("CLAUDE_TERMINAL_ID", "WT_SESSION", "ITERM_SESSION_ID",
                "WEZTERM_SESSION_ID", "TMUX"):
        val = os.environ.get(var)
        if val:
            return val if val.startswith("console_") else f"console_{val}"
    return ""


def _payload_session_id(payload: dict) -> str:
    """Extract session_id from the Stop payload (may be empty)."""
    sid = payload.get("session_id") or payload.get("sessionId") or ""
    return sid if isinstance(sid, str) else ""


# ---------------------------------------------------------------------------
# State discovery (bound, never machine-wide)
# ---------------------------------------------------------------------------

def _bound_state_dir(terminal_id: str) -> Path | None:
    """Return THIS terminal's go state dir, or None if absent."""
    if not terminal_id:
        return None
    d = ARTIFACTS_ROOT / terminal_id / "go"
    return d if d.is_dir() else None


def _select_active_task(state_dir: Path, payload_session_id: str) -> tuple[dict, Path] | None:
    """Select the in-identity active-task record, or None.

    Selection order:
      1. Foreign-session records (payload has session_id, record has a
         different non-empty session_id) are dropped.
      2. If >=1 record exactly matches the payload session_id -> that set.
      3. Else all remaining records in the bound dir.
      4. Within the chosen set, newest by mtime (bound-dir scope only).
    """
    candidates: list[tuple[dict, Path]] = []
    for p in state_dir.glob("active-task_*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        rec_sid = data.get("session_id") or ""
        if payload_session_id and rec_sid and rec_sid != payload_session_id:
            continue  # foreign session — exclude
        candidates.append((data, p))
    if not candidates:
        return None
    if payload_session_id:
        exact = [(d, p) for (d, p) in candidates if d.get("session_id") == payload_session_id]
        if exact:
            candidates = exact
    # Ambiguous: no session_id to bind AND multiple candidate runs in the bound
    # dir. Cannot safely determine the current run → fail silent.
    if not payload_session_id and len(candidates) > 1:
        return None
    candidates.sort(key=lambda dp: dp[1].stat().st_mtime)
    return candidates[-1]


def _is_stale(record: dict, path: Path) -> bool:
    """True if the record has not been touched within STALE_TTL_SECONDS."""
    now = time.time()
    updated = record.get("updated_at") or record.get("selected_at") or record.get("created_at")
    ts = _parse_iso_timestamp(updated)
    if ts is None:
        try:
            ts = path.stat().st_mtime
        except OSError:
            return True  # unreadable mtime -> treat as stale (conservative silent)
    return (now - ts) > STALE_TTL_SECONDS


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


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def check_go_completion(payload: dict | None = None) -> dict | None:
    """Return a block dict only when THIS session's fresh /go run has work left.

    Returns ``{"decision":"block","reason":"continue: ..."}`` when the bound,
    in-identity, fresh run is explicitly blocked. Returns ``None`` (print
    nothing) for done, no-state, foreign, stale, or ambiguous cases.
    """
    payload = payload if payload is not None else _parse_payload()
    if not isinstance(payload, dict):
        return None  # malformed payload — fail silent

    terminal_id = _terminal_id()
    state_dir = _bound_state_dir(terminal_id)
    if state_dir is None:
        return None  # no bound state dir / not a /go terminal — fail silent

    payload_sid = _payload_session_id(payload)
    selected = _select_active_task(state_dir, payload_sid)
    if selected is None:
        return None  # no in-identity active task — fail silent
    record, task_path = selected

    # Stale incomplete state must NOT block.
    if _is_stale(record, task_path):
        return None

    run_id = record.get("run_id") or task_path.stem.replace("active-task_", "")
    title = (record.get("task") or {}).get("title", "go run")

    # Completion marker — done. Allow (print nothing).
    if list(state_dir.glob(f".pr_ready*{run_id}*")) or list(state_dir.glob(".pr_ready*")):
        return None

    # Explicit block marker for THIS run — work remains.
    blocked = list(state_dir.glob(f".blocked*{run_id}*"))
    if blocked:
        reason = "blocked"
        for bf in blocked:
            bj = state_dir / f"blocked_{bf.stem.replace('.', '')}.json"
            if bj.exists():
                try:
                    bd = json.loads(bj.read_text(encoding="utf-8"))
                    reason = bd.get("reason_code", bd.get("phase", "blocked"))
                    break
                except (json.JSONDecodeError, OSError):
                    pass
        return {"decision": "block", "reason": f"continue: {reason} — {title}"}

    # No explicit completion or block signal — do not speculate. Allow.
    return None


def main() -> None:
    """CLI entry. Prints ONLY on block; silent on allow/fail-open."""
    result = check_go_completion()
    if isinstance(result, dict) and result.get("decision") == "block":
        sys.stdout.write(json.dumps(result))
        sys.stdout.flush()
    # Otherwise: print nothing (strict Stop allow/fail-open contract).


if __name__ == "__main__":
    main()
