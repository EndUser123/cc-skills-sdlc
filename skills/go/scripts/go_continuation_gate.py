#!/usr/bin/env python3
"""Deterministic continuation gate for /go task-completion goals.

Mitigates native goal-loop evaluator JSON failures by reading machine-readable
state instead of using LLM transcript judgment.

Reads:
  - active-task JSON (completion status, phase markers)
  - gate results / orchestrate.py state files
  - completion markers (.pr_ready, .blocked)

Emits:
  - Work remaining: {"decision":"block","reason":"continue: <next step>"}
  - Done: {"decision":"approve","reason":"goal met: <completed tasks>"}
  - No state: {} (allow — cannot determine, fail open)

This is a mitigation, not an upstream fix. Do not claim to fix Claude Code's
evaluator bug.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_state_dir() -> Path | None:
    """Find the most recent go state directory."""
    artifacts = Path("P:/.claude/.artifacts")
    if not artifacts.exists():
        return None

    # Look for console_go_*/go directories
    go_dirs = sorted(artifacts.glob("console_go_*/go"), key=lambda p: p.stat().st_mtime)
    if go_dirs:
        return go_dirs[-1]

    # Also check go-* directories
    go_dirs = sorted(artifacts.glob("go-*/go"), key=lambda p: p.stat().st_mtime)
    if go_dirs:
        return go_dirs[-1]

    return None


def _find_active_task(state_dir: Path) -> dict | None:
    """Find the most recent active-task JSON."""
    tasks = sorted(state_dir.glob("active-task_*.json"), key=lambda p: p.stat().st_mtime)
    if not tasks:
        return None
    try:
        return json.loads(tasks[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def check_go_completion() -> dict:
    """Check /go task completion state and return appropriate Stop output."""
    state_dir = _find_state_dir()
    if state_dir is None:
        return {}  # No state — fail open

    task_data = _find_active_task(state_dir)
    if task_data is None:
        return {}  # No active task — fail open

    task = task_data.get("task", task_data)
    status = task.get("status", "")
    title = task.get("title", "unknown task")

    # Check for completion markers
    blocked_files = list(state_dir.glob(".blocked*"))
    ready_files = list(state_dir.glob(".pr_ready*"))

    if ready_files:
        return {"decision": "approve", "reason": f"goal met: {title}"}

    if blocked_files:
        # Find the block reason
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

    # Check phase markers
    phases = sorted(state_dir.glob("phase-marker_*.json"), key=lambda p: p.stat().st_mtime)
    phase_names = []
    for pf in phases:
        try:
            pd = json.loads(pf.read_text(encoding="utf-8"))
            phase_names.append(pd.get("phase", pf.stem))
        except (json.JSONDecodeError, OSError):
            pass

    # Determine what's left
    expected_phases = ["task-selected", "classified", "dispatched", "coded", "verified"]
    completed = set(phase_names)
    remaining = [p for p in expected_phases if p not in completed]

    if not remaining:
        return {"decision": "approve", "reason": f"goal met: {title} (all phases complete)"}

    next_phase = remaining[0]
    return {"decision": "block", "reason": f"continue: {next_phase} — {title}"}


def main() -> None:
    """CLI entry point. Reads stdin (ignored), outputs Stop hook JSON."""
    result = check_go_completion()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
