"""UserPromptSubmit hook for skill-chaining advancement.

Contract:
    stdin:  JSON  {prompt, sessionId, ...}
    stdout: JSON  {} (pass-through) or {hookSpecificOutput: {...}} (with injection)

Flow:
    - Prompt contains ", /<skill>" -> parse chain, create manifest,
      abandon any existing active chain for this session first.
      First step is dispatched by SlashCommand routing; trailing chain text
      bleeds into first step's args (acceptable v1 limitation).
    - Empty/blank prompt while chain active -> advance last step,
      inject next command via additionalContext.
    - Non-blank input while chain active -> abandon chain, pass through.
    - No active chain -> pass through unchanged.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

# Per-process stable session id fallback (generated once at module load)
_INSTANCE_ID: str = str(uuid.uuid4())

PLUGIN_ROOT = Path(__file__).resolve().parent.parent  # skills/go
_manifest_mod = None


def _get_manifest_module():
    global _manifest_mod
    if _manifest_mod is not None:
        return _manifest_mod
    import sys as _sys_m
    import importlib.util as _util
    scripts_dir = PLUGIN_ROOT / "scripts"
    spec = _util.spec_from_file_location("chain_manifest", scripts_dir / "chain_manifest.py")
    mod = _util.module_from_spec(spec)
    _sys_m.modules["chain_manifest"] = mod
    spec.loader.exec_module(mod)
    _manifest_mod = mod
    return mod


def parse_chain(prompt: str) -> list[tuple[str, str]]:
    """Parse a prompt into skill-chain steps, or return [] if no chain detected.

    Handles "/go task, /check" and "/go, /check" (no space before comma).
    """
    stripped = prompt.strip()
    m = re.match(r"/([a-z0-9-]+(?::[a-z0-9-]+)?)\s*(.*)", stripped, re.IGNORECASE)
    if not m:
        return []
    primary_cmd = m.group(1)
    remaining = m.group(2).strip()
    spans = list(re.finditer(r",\s*/", remaining))
    if not spans:
        return []
    first_end = spans[0].start()
    first_args = remaining[:first_end].strip()
    result: list[tuple[str, str]] = [(primary_cmd, first_args)]
    for i, span in enumerate(spans):
        seg_start = span.end()
        seg_end = spans[i + 1].start() if i + 1 < len(spans) else len(remaining)
        segment = remaining[seg_start:seg_end].strip()
        cmd_match = re.match(r"([a-z0-9-]+(?::[a-z0-9-]+)?)(?:\s+(.*))?", segment, re.IGNORECASE)
        if cmd_match:
            result.append((cmd_match.group(1), cmd_match.group(2) or ""))
        elif segment:
            result.append((segment, ""))
    return result


def _session_id(payload: dict) -> str:
    """Extract stable session id from payload.

    Priority:
    1. Payload sessionId (camelCase, from Claude Code internal)
    2. Payload session_id (snake_case, from some hook contexts)
    3. CLAUDE_CODE_SESSION_ID env var (set by Claude Code per-session)
    4. Per-process instance UUID (generated once at module load)

    NOT using CLAUDE_TERMINAL_ID: that env var is the Windows Terminal
    session id which is shared across concurrent Claude Code sessions
    in the same terminal. Using it would cause cross-terminal chain
    contamination.
    """
    return (
        payload.get("sessionId")
        or payload.get("session_id")
        or os.environ.get("CLAUDE_CODE_SESSION_ID")
        or _INSTANCE_ID
    )


def _abandon_chain(cm, session_id: str) -> None:
    """Mark all in_progress chains for this session as abandoned."""
    chains = cm.list_chains(session_id=session_id)
    for c in chains:
        if c.status == "in_progress":
            try:
                cm.clear_chain(c.chain_id, force=True)
            except Exception:
                pass


def main() -> None:
    raw = sys.stdin.buffer.read()
    if not raw:
        print("{}")
        return
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except json.JSONDecodeError:
        print("{}")
        return

    prompt: str = payload.get("prompt", "")
    sid = _session_id(payload)

    cm = _get_manifest_module()

    # --- Chain creation ---
    steps = parse_chain(prompt)
    if steps:
        # Abandon any existing active chain for this session before creating
        _abandon_chain(cm, sid)
        try:
            cm.create_manifest(steps, session_id=sid, origin_command=prompt)
        except FileExistsError:
            pass
        print("{}")
        return

    # --- Check for active chain ---
    chain = _active_chain_for_session(cm, sid)
    if not chain:
        print("{}")
        return

    # --- Empty input -> advance chain ---
    if not prompt.strip():
        current = chain.steps[chain.current_step]
        if current.status == "running":
            cm.advance_step(chain.chain_id, new_status="complete")
            chain = cm.get_chain(chain.chain_id)

        if chain.status != "in_progress":
            cm.clear_chain(chain.chain_id, force=True)
            print("{}")
            return

        next_step = chain.steps[chain.current_step]
        if next_step.status == "pending":
            cm.advance_step(chain.chain_id, new_status="running", step_index=next_step.index)
            cmd_line = f"/{next_step.skill}"
            if next_step.args:
                cmd_line += f" {next_step.args}"
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": cmd_line,
                }
            }
            print(json.dumps(output))
            return
        print("{}")
        return

    # --- Non-blank input while chain active -> abandon ---
    _abandon_chain(cm, sid)
    print("{}")


def _active_chain_for_session(cm, session_id: str):
    chains = cm.list_chains(session_id=session_id)
    for c in chains:
        if c.status == "in_progress":
            return c
    return None


if __name__ == "__main__":
    main()
