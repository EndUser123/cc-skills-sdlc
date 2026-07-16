#!/usr/bin/env python3
"""Deterministic Stop-gate for comma-separated skill chains.

Contract (same as go_continuation_gate):
  - Active chain, current step is "running" (injected by the UPS hook,
    waiting for the model to execute it):
    print {"decision":"block","reason":"continue: <reason>"}; exit 0.
  - No active chain / step not running / chain complete:
    print NOTHING; exit 0.
  - Never prints {} or {"decision":"approve"}.

Self-scoping
------------
Reads the same CHAIN_STEPS_DIR (or default P:/.artifacts/skill-chains) as
chain_advance_ups.py. Only activates when a chain manifest exists and its
current step is in the "running" state. Inert in every other session.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent  # skills/go/scripts
_manifest_mod = None


def _get_manifest_module():
    global _manifest_mod
    if _manifest_mod is not None:
        return _manifest_mod
    spec = importlib.util.spec_from_file_location(
        "chain_manifest", PLUGIN_ROOT / "chain_manifest.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["chain_manifest"] = mod
    spec.loader.exec_module(mod)
    _manifest_mod = mod
    return mod


def _session_id(payload: dict) -> str:
    return (
        payload.get("sessionId")
        or payload.get("session_id")
        or os.environ.get("CLAUDE_CODE_SESSION_ID")
        or ""
    )


def main() -> None:
    raw = sys.stdin.buffer.read()
    if not raw:
        return
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return

    sid = _session_id(payload)
    if not sid:
        return  # no session identity -> silent

    cm = _get_manifest_module()
    chains = cm.list_chains(session_id=sid)
    if not chains:
        return  # no chain -> silent

    # Find the active (in_progress) chain
    for chain in chains:
        if chain.status != "in_progress":
            continue

        step = chain.steps[chain.current_step]
        if step.status != "running":
            continue

        # Chain has work: current step was set to "running" by the UPS
        # hook, meaning the model was told to execute it but hasn't
        # confirmed completion yet.
        cmd_str = f"/{step.skill}"
        if step.args:
            cmd_str += f" {step.args}"
        result = {
            "decision": "block",
            "reason": f"continue: {cmd_str} — chain step pending",
        }
        sys.stdout.write(json.dumps(result))
        sys.stdout.flush()
        return

    # Not blocking: chain may be complete, failed, or current step not running
    return


if __name__ == "__main__":
    main()
