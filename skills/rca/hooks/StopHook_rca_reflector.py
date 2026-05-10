#!/usr/bin/env python3
"""StopHook_rca_reflector — TASK-003.

Advisory Stop hook detecting:
  - Premature convergence: Root Cause present, hypothesis count < 3
  - Catch-22 spiral: same tool+error 3+ consecutive RCA turns
  - Evidence-free fix: Fix present, Evidence empty
  - Zero-plan: No Executed Path after 3+ tool calls

State: state/rca_reflector_{terminal_id}_{session_id}.json with 2-hour TTL.
Fires BEFORE StopHook_rca_contract.py in the hook sequence.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

STATE_DIR = Path(r"$CLAUDE_ROOT/state")
STATE_TTL_SECONDS = 2 * 3600  # 2 hours


def _get_state_file(session_id: str, terminal_id: str) -> Path:
    """Return path to state file for this session/terminal."""
    # Sanitize to prevent path traversal
    safe_session = re.sub(r"[^a-zA-Z0-9_\-]", "", session_id)
    safe_terminal = re.sub(r"[^a-zA-Z0-9_\-]", "", terminal_id)
    return STATE_DIR / f"rca_reflector_{safe_terminal}_{safe_session}.json"


def _load_state(session_id: str, terminal_id: str) -> dict:
    """Load state, returning empty dict if missing or stale."""
    state_file = _get_state_file(session_id, terminal_id)
    if not state_file.exists():
        return {}
    try:
        age = time.time() - state_file.stat().st_mtime
        if age > STATE_TTL_SECONDS:
            state_file.unlink()
            return {}
        with open(state_file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(session_id: str, terminal_id: str, state: dict) -> None:
    """Save state to disk."""
    state_file = _get_state_file(session_id, terminal_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
    except OSError:
        pass


def _cleanup_stale_state_files() -> None:
    """Delete all rca_reflector state files older than TTL on load."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for f in STATE_DIR.glob("rca_reflector_*.json"):
            try:
                if now - f.stat().st_mtime > STATE_TTL_SECONDS:
                    f.unlink()
            except OSError:
                pass
    except OSError:
        pass


def _detect_premature_convergence(response: str, alt_count: int) -> str | None:
    """Return advisory if Root Cause declared with fewer than 3 hypotheses."""
    if alt_count >= 3:
        return None
    if re.search(r"(?i)^##\s*Root\s+Cause\s*\n", response, re.MULTILINE):
        return (
            "3+ hypotheses required before declaring Root Cause. "
            f"Found {alt_count} alternative(s). "
            "Recurring RCA pattern detected — try alternative strategies."
        )
    return None


def _is_catch22_spiral(state: dict, tool_name: str, error: str) -> bool:
    """Return True if same tool+error 3+ consecutive times."""
    if (
        state.get("last_tool") == tool_name
        and state.get("last_error") == error
        and state.get("consecutive_count", 0) >= 3
    ):
        return True
    return False


def _update_catch22_state(state: dict, tool_name: str, error: str) -> dict:
    """Update catch-22 tracking state."""
    if state.get("last_tool") == tool_name and state.get("last_error") == error:
        new_count = state.get("consecutive_count", 1) + 1
    else:
        new_count = 1
    return {
        "last_tool": tool_name,
        "last_error": error,
        "consecutive_count": new_count,
    }


def _has_evidence_free_fix(response: str) -> bool:
    """Return True if Fix declared without Evidence content."""
    fix_match = re.search(
        r"(?i)^##\s*Fix\s*\n(.+?)(?=^##|\Z)",
        response,
        re.MULTILINE | re.DOTALL,
    )
    if not fix_match:
        return False
    evidence_match = re.search(
        r"(?i)^##\s*Evidence\s*\n(.+?)(?=^##|\Z)",
        response,
        re.MULTILINE | re.DOTALL,
    )
    if not evidence_match:
        return True  # Evidence section missing entirely
    evidence_content = evidence_match.group(1).strip()
    return len(evidence_content) == 0


def _detect_zero_plan(response: str, tool_event_count: int) -> str | None:
    """Return advisory if no Executed Path after 3+ tool calls."""
    if tool_event_count < 3:
        return None
    has_path = bool(
        re.search(
            r"(?i)^##\s*Executed\s+Path\s*\n",
            response,
            re.MULTILINE,
        )
    )
    if not has_path:
        return (
            "Executed Path missing despite investigation. "
            "Document the path taken to reach the Root Cause."
        )
    return None


def check(data: dict) -> dict | None:
    """Main guard — advisory only, never blocks."""
    rca_turn = data.get("rca_turn", False)
    if not rca_turn:
        return None

    session_id = data.get("session_id", "unknown")
    terminal_id = data.get("terminal_id", "unknown")
    response = data.get("response", "")
    tool_events = data.get("tool_events", [])

    # TTL cleanup on every invocation
    _cleanup_stale_state_files()

    state = _load_state(session_id, terminal_id)
    advisories: list[str] = []

    # --- Premature convergence ---
    alt_count = len(re.findall(r"(?i)^##\s+Alternative\s+Hypothesis", response, re.MULTILINE))
    prem_conv = _detect_premature_convergence(response, alt_count)
    if prem_conv:
        advisories.append(prem_conv)

    # --- Evidence-free fix ---
    if _has_evidence_free_fix(response):
        advisories.append(
            "Evidence required before fix declaration. "
            "Document what was observed before proposing a fix."
        )

    # --- Zero-plan ---
    zero_plan = _detect_zero_plan(response, len(tool_events))
    if zero_plan:
        advisories.append(zero_plan)

    # --- Catch-22 spiral ---
    catch22_advisory = None
    for event in tool_events:
        tool_name = event.get("name", "")
        # Extract error summary from tool call
        error = ""
        output = event.get("output", "") or event.get("error", "") or ""
        # Truncate to first line for comparison
        error = output.split("\n", 1)[0].strip()[:100]

        if _is_catch22_spiral(state, tool_name, error):
            catch22_advisory = (
                "Recursive failure detected — try alternative strategy. "
                "The same tool has failed 3+ consecutive times."
            )
            break

    # Update catch-22 state for next turn
    if tool_events:
        last_event = tool_events[-1]
        tool_name = last_event.get("name", "")
        output = last_event.get("output", "") or last_event.get("error", "") or ""
        error = output.split("\n", 1)[0].strip()[:100]
        state = _update_catch22_state(state, tool_name, error)
        _save_state(session_id, terminal_id, state)

    if catch22_advisory:
        advisories.append(catch22_advisory)

    if advisories:
        return {
            "allow": True,
            "systemMessage": " | ".join(advisories),
        }

    return None


def run(data: dict) -> dict | None:
    """Router entry point — delegates to check()."""
    return check(data)
