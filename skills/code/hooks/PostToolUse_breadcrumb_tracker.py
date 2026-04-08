#!/usr/bin/env python3
"""
PostToolUse hook for /code skill - Track workflow step completion

Marks workflow steps as complete in breadcrumb trail after tool execution.
This enables tracking progress across the 9-phase /code workflow.

Usage: This hook is automatically called after tool execution during /code skill
Input: JSON via stdin with tool details and results
Output: JSON via stdout with continue decision
"""

import json
import sys
from pathlib import Path

# Add skill-guard to path
skill_guard_path = Path("P:/packages/skill-guard")
if str(skill_guard_path) not in sys.path:
    sys.path.insert(0, str(skill_guard_path))

from skill_guard.breadcrumb.tracker import set_breadcrumb

# Map tool names to workflow steps
# This is a simplified mapping - in production, this would be more sophisticated
TOOL_TO_STEP = {
    "Ask": "analyze_query_intent",
    "Bash": "tdd_implementation",  # Could be various steps
    "Edit": "tdd_implementation",
    "Write": "tdd_implementation",
    "Read": "explore_codebase",
    "Glob": "explore_codebase",
    "Grep": "explore_codebase",
    "Agent": "design_solution",  # Subagent delegation
}


def detect_completed_step(tool_name: str, tool_input: dict) -> str | None:
    """Detect which workflow step completed based on tool usage.

    Args:
        tool_name: Name of the tool that was just executed
        tool_input: Input parameters passed to the tool

    Returns:
        Workflow step name if detected, None otherwise
    """
    # Direct mapping from tool to step
    if tool_name in TOOL_TO_STEP:
        return TOOL_TO_STEP[tool_name]

    # Special cases based on tool_input
    if tool_name == "Skill":
        skill_name = tool_input.get("name", "")
        if skill_name == "test":
            return "full_test_suite"
        elif skill_name == "trace":
            return "trace_manual_verification"

    return None


def main():
    """Track workflow step completion in breadcrumb trail."""
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Extract tool information
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Detect which step completed
        step = detect_completed_step(tool_name, tool_input)

        if step:
            # Mark step as complete in breadcrumb trail
            set_breadcrumb("code", step)

        # Always allow execution to continue
        print(json.dumps({"continue": True}))
        sys.exit(0)

    except Exception as e:
        # Log error but don't block execution
        # Breadcrumb tracking is optional for now
        print(json.dumps({"continue": True}), file=sys.stderr)
        print(f"Breadcrumb tracking failed: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
