#!/usr/bin/env python3
"""Deterministic continuation gate for /go task-completion goals.

Reads machine-readable /go state (active-task JSON, phase markers, completion
markers) and emits the strict Claude Code Stop-hook contract:

  - Work remaining: print {"decision":"block","reason":"continue: <next step>"}
  - Done / allow / fail-open / no /go state: print NOTHING.

NEVER prints {}, {"decision":"approve"}, {"continue":true}, or any other allow
payload — those violate the Stop contract and surface as "JSON validation
failed". stderr is diagnostics-only.

SELF-SCOPING: this is a direct project-settings entry
(``P:/.claude/settings.json`` Stop[3]) into a plugin skill script. It is NOT
wired through ``cc-skills-sdlc/hooks/hooks.json`` (kept dormant). The gate
fails silent on every non-/go session because ``_find_state_dir()`` returns
None when no ``console_go_*/go`` state tree exists.

This is a mitigation, not an upstream fix. It is ADDITIVE to the native
goal-loop evaluator — it does not replace it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_state_dir() -> Path | None:
    """Find the most recent /go state directory, or None if none exists."""
    artifacts = Path("P:/.claude/.artifacts")
    if not artifacts.exists():
        return None

    go_dirs = sorted(artifacts.glob("console_go_*/go"), key=lambda p: p.stat().st_mtime)
    if go_dirs:
        return go_dirs[-1]

    go_dirs = sorted(artifacts.glob("go-*/go"), key=lambda p: p.stat().st_mtime)
    if go_dirs:
        return go_dirs[-1]

    return None


def _find_active_task(state_dir: Path) -> dict | None:
    """Find the most recent active-task JSON, or None."""
    tasks = sorted(state_dir.glob("active-task_*.json"), key=lambda p: p.stat().st_mtime)
    if not tasks:
        return None
    try:
        return json.loads(tasks[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def check_go_completion() -> dict | None:
    """Return a block dict when /go work remains, else None (allow).

    Returns:
        ``{"decision":"block","reason":"continue: <next step>"}`` if state
        shows an incomplete /go run; ``None`` if done, no state, no active
        task, or the run is complete. ``None`` means main() must print
        nothing.
    """
    state_dir = _find_state_dir()
    if state_dir is None:
        return None  # Not a /go session — fail silent.

    task_data = _find_active_task(state_dir)
    if task_data is None:
        return None  # No active task — fail silent.

    task = task_data.get("task", task_data)
    title = task.get("title", "unknown task")

    # Completion marker — run is done. Allow (print nothing).
    ready_files = list(state_dir.glob(".pr_ready*"))
    if ready_files:
        return None

    # Explicit block marker — work remains (blocked on a known reason).
    blocked_files = list(state_dir.glob(".blocked*"))
    if blocked_files:
        for bf in blocked_files:
            block_json = state_dir / f"blocked_{bf.stem.replace('.', '')}.json"
            if block_json.exists():
                try:
                    bd = json.loads(block_json.read_text(encoding="utf-8"))
                    reason = bd.get("reason_code", bd.get("phase", "unknown"))
                    return {"decision": "block", "reason": f"continue: {reason} — {title}"}
                except (json.JSONDecodeError, OSError):
                    pass
        return {"decision": "block", "reason": f"continue: blocked — {title}"}

    # Phase markers — block until every expected phase is recorded.
    phases = sorted(state_dir.glob("phase-marker_*.json"), key=lambda p: p.stat().st_mtime)
    phase_names = []
    for pf in phases:
        try:
            pd = json.loads(pf.read_text(encoding="utf-8"))
            phase_names.append(pd.get("phase", pf.stem))
        except (json.JSONDecodeError, OSError):
            pass

    expected_phases = ["task-selected", "classified", "dispatched", "coded", "verified"]
    completed = set(phase_names)
    remaining = [p for p in expected_phases if p not in completed]

    if not remaining:
        return None  # All phases complete — allow.

    next_phase = remaining[0]
    return {"decision": "block", "reason": f"continue: {next_phase} — {title}"}


def main() -> None:
    """CLI entry point. Prints ONLY on block; silent on allow/fail-open.

    stdin is the hook payload (ignored). stderr is diagnostics-only.
    """
    result = check_go_completion()
    if isinstance(result, dict) and result.get("decision") == "block":
        sys.stdout.write(json.dumps(result))
        sys.stdout.flush()
    # Otherwise: print nothing (strict Stop allow/fail-open contract).


if __name__ == "__main__":
    main()
