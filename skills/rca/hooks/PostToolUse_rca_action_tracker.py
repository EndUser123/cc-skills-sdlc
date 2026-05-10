#!/usr/bin/env python3
"""
PostToolUse: Action tracker for /rca workflow.
Records each tool usage as an Action in the action graph for divergence detection.

This hook runs for ALL tools during active RCA sessions, building a complete
trace of the investigation path.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
STATE_FILE = STATE_DIR / "rca_workflow.json"

# Import auto-logging decorator (optional)
_hooks_lib = CLAUDE_HOME / "hooks" / "__lib"
if _hooks_lib.exists():
    sys.path.insert(0, str(_hooks_lib))
    try:
        from hook_base import hook_main
    except ImportError:
        hook_main = lambda f: f  # Fallback: no-op decorator
else:
    hook_main = lambda f: f  # Fallback: no-op decorator

# Import action_tracer from rca package
ActionTracer = None
ActionType = None
classify_action = None
try:
    # Add package src to path for import
    _hook_dir = Path(__file__).parent.parent.parent.parent / "src"
    if str(_hook_dir) not in sys.path:
        sys.path.insert(0, str(_hook_dir))
    from rca.action_tracer import (
        ActionTracer,
        ActionType,
        classify_action,
        get_expected_path,
    )
except ImportError:
    # Fallback: try CSF path for development environments
    CSF_SRC = os.environ.get("CSF_SRC", "P:\\\\\\__csf/src")
    if os.path.exists(CSF_SRC):
        sys.path.insert(0, CSF_SRC)
        try:
            from rca.action_tracer import (
                ActionTracer,
                ActionType,
                classify_action,
                get_expected_path,
            )
        except ImportError:
            ActionTracer = None
    else:
        ActionTracer = None


def get_current_terminal_id() -> str:
    """Get the current Claude Code terminal ID from environment."""
    return os.environ.get("CLAUDE_TERMINAL_ID", "").strip()


def get_action_file_path(session_id: str) -> Path:
    """Get the path to the actions file for a session."""
    return STATE_DIR / f"actions_{session_id}.json"


def truncate_for_preview(text: str, max_length: int = 1024) -> str:
    """Truncate text for preview storage."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "... (truncated)"


def sanitize_tool_input(tool_input: dict) -> dict:
    """Sanitize tool input for storage (remove/truncate sensitive data)."""
    sanitized = {}
    for key, value in tool_input.items():
        value_str = str(value)
        if len(value_str) > 500:
            sanitized[key] = value_str[:500] + "... (truncated)"
        else:
            sanitized[key] = value
    return sanitized


def load_actions_graph(
    session_id: str,
    terminal_id: str,
) -> dict:
    """Load existing actions graph or create new one."""
    actions_file = get_action_file_path(session_id)

    if actions_file.exists():
        try:
            data = json.loads(actions_file.read_text(encoding="utf-8"))
            # Verify terminal ownership
            if data.get("terminal_id") == terminal_id:
                return data
        except (OSError, json.JSONDecodeError):
            pass

    # Create new graph
    now = datetime.now().isoformat()
    return {
        "session_id": session_id,
        "actions": [],
        "divergence_point": None,
        "expected_path": None,
        "created_at": now,
        "updated_at": now,
        "terminal_id": terminal_id,
    }


def save_actions_graph(graph: dict, session_id: str) -> None:
    """Save actions graph to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    actions_file = get_action_file_path(session_id)
    graph["updated_at"] = datetime.now().isoformat()
    actions_file.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def record_action(
    graph: dict,
    action_type: str,
    tool_used: str,
    tool_input: dict,
    tool_output: str,
    phase: int,
    terminal_id: str,
) -> dict:
    """Record a new action in the graph.

    Returns the created action dict.
    """
    import uuid

    # Generate action ID
    action_id = f"act_{uuid.uuid4().hex[:8]}"

    # Create action
    action = {
        "action_id": action_id,
        "action_type": action_type,
        "timestamp": datetime.now().isoformat(),
        "tool_used": tool_used,
        "tool_input": sanitize_tool_input(tool_input),
        "tool_output_hash": f"{len(tool_output)}:{tool_output[:32] if tool_output else ''}...{tool_output[-32:] if tool_output and len(tool_output) > 64 else ''}",
        "tool_output_preview": truncate_for_preview(tool_output),
        "parent_id": graph["actions"][-1]["action_id"] if graph["actions"] else None,
        "phase": phase,
        "session_id": graph["session_id"],
        "terminal_id": terminal_id,
    }

    # Add to graph
    graph["actions"].append(action)

    return action


def check_divergence(graph: dict, expected_path: list[str]) -> dict | None:
    """Check if actual actions diverged from expected path.

    Returns the diverging action if found, None otherwise.
    """
    actual_types = [a["action_type"] for a in graph["actions"]]

    # Find first mismatch
    for i, (expected, actual) in enumerate(zip(expected_path, actual_types, strict=False)):
        if expected != actual:
            if i < len(graph["actions"]):
                diverging_action = graph["actions"][i]
                graph["divergence_point"] = diverging_action
                return diverging_action

    # Check if actual is shorter
    if len(actual_types) < len(expected_path):
        if graph["actions"]:
            return graph["actions"][-1]

    # No divergence
    graph["divergence_point"] = None
    return None


@hook_main
def main():
    """Entry point - record action for each tool usage during RCA."""
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({}))
        sys.exit(0)

    # Check if RCA workflow is active
    if not STATE_FILE.exists():
        print(json.dumps({}))
        sys.exit(0)

    try:
        state = json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        print(json.dumps({}))
        sys.exit(0)

    # Skip if RCA complete
    if state.get("complete", False):
        print(json.dumps({}))
        sys.exit(0)

    # Multi-terminal safety: check ownership
    current_terminal_id = get_current_terminal_id()
    rca_terminal_id = state.get("claude_terminal_id")

    if rca_terminal_id and current_terminal_id:
        if rca_terminal_id != current_terminal_id:
            # State belongs to different terminal - don't track
            print(json.dumps({}))
            sys.exit(0)

    # Extract tool info
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    tool_output = payload.get("tool_output", "")

    # Get current phase
    current_phase = state.get("current_phase", 0)

    # Classify the action
    if ActionTracer is None:
        # Can't import action_tracer, skip tracking
        print(json.dumps({}))
        sys.exit(0)

    action_type = classify_action(tool_name, tool_input, tool_output)

    # Skip unknown actions (noise)
    if action_type == ActionType.UNKNOWN:
        print(json.dumps({}))
        sys.exit(0)

    # Get session info
    session_id = state.get("session_id", "")

    # Load or create actions graph
    graph = load_actions_graph(session_id, current_terminal_id)

    # Record the action
    record_action(
        graph,
        action_type=action_type.value,
        tool_used=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        phase=current_phase,
        terminal_id=current_terminal_id,
    )

    # Check for divergence if we have enough actions
    # (wait until at least 3 actions before checking)
    divergence_info = None
    if len(graph["actions"]) >= 3:
        # Get problem type for expected path
        problem_type = state.get("problem_type", "error")
        expected_path = [at.value for at in get_expected_path(problem_type)]

        diverging_action = check_divergence(graph, expected_path)
        if diverging_action:
            divergence_info = {
                "divergence_action_id": diverging_action["action_id"],
                "expected_type": expected_path[len(graph["actions"]) - 1]
                if len(graph["actions"]) <= len(expected_path)
                else "end_of_expected",
                "actual_type": diverging_action["action_type"],
            }

    # Save updated graph
    save_actions_graph(graph, session_id)

    # Report action recorded
    result = {
        "message": f"📝 Action recorded: {action_type.value} (Phase {current_phase})",
    }

    if divergence_info:
        result["divergence_detected"] = True
        result["divergence_info"] = divergence_info

    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
