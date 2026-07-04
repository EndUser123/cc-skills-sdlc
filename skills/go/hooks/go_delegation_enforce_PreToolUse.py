#!/usr/bin/env python3
"""PreToolUse hook for /go — delegation mutation-authority enforcer.

Enforces delegation_policy at the actual spawn/tool-call boundary: Claude's
own Edit/Write/Bash calls during a /go session. Advisory roles are denied all
mutating tools; worker roles are path-bounded to worker_scope; pi_ccr is
denied direct main-tree edits (it mutates only in its worktree via harness.py).

Self-scoping reuses G5's pointer model (Stop_enforce_gate.py):
  payload session_id -> go-sessions/{session_id}.json -> go_state_dir/run_id

Fail-silent (print nothing, exit 0) when:
  - no session_id, no pointer, stale pointer, missing state dir
  - no task-proposal_{run_id}.json (run predates delegation_policy)
  - no .delegation-{advisory|worker}_{run_id} phase marker (not a gated phase)
  - read-only tools (Read/Grep/Glob)

Deny (stdout JSON, exit 0) when:
  - advisory role + mutating tool
  - worker role + target path outside worker_scope (when scope resolvable)
  - worker role local_fast + Bash shared-state subcommand
  - worker role pi_ccr + direct Claude mutation (must go via worktree)

Output contract (memory: pretooluse_deny_reason_surfacing):
  deny  -> {"permissionDecision":"deny","permissionDecisionReason":"..."}
  allow -> print NOTHING, exit 0
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")
_SESSIONS_DIR = "go-sessions"
_STALE_TTL_SECONDS = 6 * 3600  # 6h — same as G4/G5

_MUTATING_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
_SHARED_STATE_TOOL_MARKERS = (
    "git push", "git commit", "git reset", "git checkout", "git rebase",
    "git stash", "git merge", "git tag", "git rm",
    "settings.json", "hooks.json", "plugin.json", "marketplace.json",
    "plugin-audit-and-fix", "--bump", "pip install", "npm install",
)


# ---------------------------------------------------------------------------
# Payload + pointer resolution (mirrors G5 — kept local for edit-liveness)
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
# Tool-call classification
# ---------------------------------------------------------------------------

def _norm(path: str) -> str:
    return path.replace("\\", "/").lower().strip("\"' ")


def _is_under_scope(target: str, scope: list[str]) -> bool:
    """True if target path is under any worker_scope prefix.

    Scope entries may be relative (foo.py, src/bar.py) or absolute (P:/...).
    A bare filename scope (foo.py) matches any target ending in that filename;
    a path scope matches targets containing that prefix.
    """
    if not scope:
        return True  # type-bound mode: no path restriction at this layer
    t = _norm(target)
    for entry in scope:
        e = _norm(entry)
        if not e:
            continue
        if t == e or t.endswith("/" + e) or t.endswith(e) or e in t:
            return True
    return False


def _is_mutating(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """Return (is_mutating, target_path_or_command)."""
    name = tool_name or ""
    if name in _MUTATING_TOOLS:
        target = (
            tool_input.get("file_path")
            or tool_input.get("notebook_path")
            or tool_input.get("path")
            or ""
        )
        return True, str(target)
    if name == "Bash":
        cmd = str(tool_input.get("command") or "")
        low = cmd.lower()
        if any(m in low for m in _SHARED_STATE_TOOL_MARKERS):
            return True, cmd
        return False, cmd
    return False, ""


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def _deny(reason: str) -> int:
    print(json.dumps({
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }))
    return 0


def _decide(payload: dict) -> int:
    session_id = _payload_session_id(payload)
    if not session_id:
        return 0  # not a /go session

    pointer = _read_pointer(session_id)
    if pointer is None:
        return 0  # no /go state
    state_dir = _resolve_state_dir(pointer)
    if state_dir is None:
        return 0
    run_id = pointer.get("run_id") or ""
    if not run_id:
        return 0

    # Phase marker gates the enforcement window.
    advisory_marker = state_dir / f".delegation-advisory_{run_id}"
    worker_marker = state_dir / f".delegation-worker_{run_id}"
    if advisory_marker.exists():
        mode = "advisory"
    elif worker_marker.exists():
        mode = "worker"
    else:
        return 0  # not in a delegation-gated phase

    proposal_path = state_dir / f"task-proposal_{run_id}.json"
    if not proposal_path.is_file():
        return 0  # run predates delegation_policy
    try:
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    dp = proposal.get("delegation_policy") or {}
    if not dp:
        return 0

    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    mutating, target = _is_mutating(tool_name, tool_input)
    if not mutating:
        return 0  # read-only tools always pass

    role = dp.get("advisory_reviewer") if mode == "advisory" else dp.get("worker")
    scope = list(dp.get("worker_scope") or [])

    if mode == "advisory":
        return _deny(
            f"/go delegation: role '{role}' is ADVISORY (read-only) in this "
            f"phase. Mutation via {tool_name} denied. Advisory output is "
            f"evidence, not authority — regenerate review if scope changed. "
            f"(run_id={run_id})"
        )

    # worker mode
    if role in (None, "claude_main"):
        return 0  # orchestrator; final authority = evidence gates
    if role == "pi_ccr":
        return _deny(
            f"/go delegation: worker role 'pi_ccr' must mutate only in its "
            f"isolated worktree via the pi harness, not via direct {tool_name} "
            f"on the main tree. (run_id={run_id})"
        )
    if role == "local_fast" and tool_name == "Bash":
        return _deny(
            f"/go delegation: worker role 'local_fast' (local_surgical) may "
            f"not touch shared state via Bash. Denied: {target[:80]!r}. "
            f"(run_id={run_id})"
        )
    # claude_subagent or local_fast Edit/Write: path-bound when scope resolvable
    if scope and target and not _is_under_scope(target, scope):
        return _deny(
            f"/go delegation: worker role '{role}' mutation outside "
            f"worker_scope denied. target={_norm(target)!r} scope={scope}. "
            f"(run_id={run_id})"
        )
    return 0  # in-scope worker mutation


def main() -> None:
    payload = _parse_payload()
    sys.exit(_decide(payload))


if __name__ == "__main__":
    main()
