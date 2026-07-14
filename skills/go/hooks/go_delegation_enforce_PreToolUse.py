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


# Path to scripts dir for canonical run_record import
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
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

# TASK-001.4: role-enum drift protection. The authoritative role set lives in
# preflight_propose._ROLE_VALUES; this policy dict MUST cover every role there
# and no role not there. ``test_role_enum_contract.py`` asserts
# ``set(_ROLE_POLICY) == set(preflight_propose._ROLE_VALUES)`` so dropping or
# adding a role in one place without the other fails the drift test.
#
# worker_mode values:
#   orchestrator                  -> allow (claude_main; final auth = evidence gates)
#   path_bound                    -> Edit/Write path-checked against worker_scope
#   path_bound_no_shared_state    -> path_bound + Bash shared-state denied (local_fast)
#   worktree_only                 -> deny direct main-tree mutation; mutates in own worktree
_ROLE_POLICY: dict[str, dict[str, str]] = {
    "claude_main":     {"worker_mode": "orchestrator"},
    "claude_subagent": {"worker_mode": "path_bound"},
    "local_fast":      {"worker_mode": "path_bound_no_shared_state"},
    "pi_ccr":          {"worker_mode": "worktree_only"},
    "agy":             {"worker_mode": "worktree_only"},
}


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

def _format_prewrite_block(reason_code: str, session_id: str, run_id: str) -> str:
    fmt = {
        "RUN_FAILED": "Run identity validation failed: missing or invalid run record",
        "LEASE_FAILED": "Workspace lease validation failed: session does not own this workspace",
        "FOREIGN_SESSION": "Cross-session run access blocked: session does not own this run",
        "WRONG_REPOSITORY": "Repository mismatch detected",
        "WRONG_WORKTREE": "Worktree path mismatch detected",
        "WRONG_CONTRACT": "Contract fingerprint mismatch detected",
        "STALE_RUN": "Run record has expired (stale TTL exceeded)",
        "LEASE_HELD": "Workspace lease is held by another session",
        "NO_LEASE": "No valid workspace lease for this session-run pair",
    }
    base = fmt.get(reason_code, f"Write authorization denied: {reason_code}")
    return f"{base} (session={session_id[:8]}..., run={run_id[:8]}...)"

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


    # Pre-write: use canonical validation from run_record.check_pre_write().
    # This is the single authority chain for write-authorization decisions:
    # pointer + run record + lifecycle + repository + worktree + lease.
    try:
        from run_record import check_pre_write as _canonical_prewrite
        from run_record import repository_root as _rr
        from run_record import current_worktree_path as _cwt

        _pw_result = _canonical_prewrite(
            session_id=session_id, run_id=run_id,
            artifacts_root=_ARTIFACTS_ROOT,
            repository=_rr(), worktree_path=_cwt()
        )
        if not _pw_result.get("allow"):
            return _deny(_format_prewrite_block(
                _pw_result.get("reason_code", "UNKNOWN"),
                session_id, run_id
            ))
    except ImportError:
        pass  # run_record unavailable — fail open
    except Exception as e:
        return _deny(f"PreToolUse: write authorization check failed: {e}")


    role = dp.get("advisory_reviewer") if mode == "advisory" else dp.get("worker")
    scope = list(dp.get("worker_scope") or [])

    if mode == "advisory":
        return _deny(
            f"/go delegation: role '{role}' is ADVISORY (read-only) in this "
            f"phase. Mutation via {tool_name} denied. Advisory output is "
            f"evidence, not authority — regenerate review if scope changed. "
            f"(run_id={run_id})"
        )

    # worker mode — dispatch through _ROLE_POLICY (single source of truth).
    if role is None:
        role = "claude_main"  # missing worker label defaults to orchestrator
    policy = _ROLE_POLICY.get(role)
    if policy is None:
        # Drift between preflight_propose._ROLE_VALUES and this gate. Fail-closed:
        # an unlabeled role is denied, not silently allowed.
        return _deny(
            f"/go delegation: worker role {role!r} has no mutation-authority "
            f"policy in this gate (role-enum drift). Denied pending policy update. "
            f"(run_id={run_id})"
        )
    mode_kind = policy["worker_mode"]
    if mode_kind == "orchestrator":
        return 0  # final authority = evidence gates
    if mode_kind == "worktree_only":
        return _deny(
            f"/go delegation: worker role '{role}' must mutate only in its "
            f"isolated worktree, not via direct {tool_name} on the main tree. "
            f"(run_id={run_id})"
        )
    if mode_kind == "path_bound_no_shared_state" and tool_name == "Bash":
        return _deny(
            f"/go delegation: worker role '{role}' may not touch shared state "
            f"via Bash. Denied: {target[:80]!r}. (run_id={run_id})"
        )
    # path_bound / path_bound_no_shared_state (non-Bash): check target in scope
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