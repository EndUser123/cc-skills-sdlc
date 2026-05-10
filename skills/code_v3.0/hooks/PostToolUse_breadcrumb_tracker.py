#!/usr/bin/env python3
"""
PostToolUse hook for /code skill - Track workflow step completion + phase ledger.

Marks workflow steps as complete in breadcrumb trail AND writes phase markers
to the ledger for gateable phases (smoke, full tests, audit).

Usage: This hook is automatically called after tool execution during /code skill
Input: JSON via stdin with tool details and results
Output: JSON via stdout with continue decision
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add skill-guard to path
skill_guard_path = Path("P:\\\\\\packages/skill-guard")
if str(skill_guard_path) not in sys.path:
    sys.path.insert(0, str(skill_guard_path))

from skill_guard.breadcrumb.tracker import set_breadcrumb

# Import the phase ledger helper
_hooks_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_hooks_dir))
from code_phase_ledger import write_phase_marker

# Map tool names to workflow steps
TOOL_TO_STEP = {
    "Ask": "analyze_query_intent",
    "Bash": "tdd_implementation",
    "Edit": "tdd_implementation",
    "Write": "tdd_implementation",
    "Read": "explore_codebase",
    "Glob": "explore_codebase",
    "Grep": "explore_codebase",
    "Agent": "design_solution",
}

# Bash commands that indicate gateable phases
AUDIT_COMMANDS = frozenset([
    "ruff", "ruff check", "ruff format",
    "mypy", "pylint", "tsc", "tsc --noEmit",
    "eslint", "prettier", "ruff --fix",
])


def _is_pytest(cmd: str) -> bool:
    """Return True if cmd is a pytest invocation."""
    return "pytest" in cmd or "py.test" in cmd


def _is_smoke(cmd: str) -> bool:
    """Return True if cmd looks like a quick/smoke pytest run."""
    return _is_pytest(cmd) and ("-x" in cmd or "--exitfirst" in cmd or "test_" in cmd and "tests" not in cmd)


def _is_full_suite(cmd: str) -> bool:
    """Return True if cmd looks like a full test suite run."""
    return _is_pytest(cmd) and not _is_smoke(cmd)


def _audit_exit_from_cmd(cmd: str, stdout: str, stderr: str, exit_code: int) -> int | None:
    """Map tool invocation to an audit exit code."""
    combined = stdout + stderr
    tool = None
    if "ruff" in cmd:
        tool = "ruff"
    elif "mypy" in cmd:
        tool = "mypy"
    elif "pylint" in cmd:
        tool = "pylint"
    elif "tsc" in cmd:
        tool = "tsc"
    if tool:
        return exit_code
    return None


def detect_completed_step(tool_name: str, tool_input: dict) -> str | None:
    """Detect which workflow step completed based on tool usage."""
    if tool_name in TOOL_TO_STEP:
        return TOOL_TO_STEP[tool_name]
    if tool_name == "Skill":
        skill_name = tool_input.get("name", "")
        if skill_name == "test":
            return "full_test_suite"
        elif skill_name == "trace":
            return "trace_manual_verification"
    return None


def main() -> None:
    """Track workflow step completion and write ledger markers."""
    try:
        input_data = json.loads(sys.stdin.read())
        session_id = input_data.get("session_id")
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        tool_result = input_data.get("result", {})
        stdout = str(tool_result.get("stdout", ""))
        stderr = str(tool_result.get("stderr", ""))
        exit_code = int(tool_result.get("exit_code") or 0)

        step = detect_completed_step(tool_name, tool_input)
        if step:
            set_breadcrumb("code", step)

        # Wire gateable phases into the ledger
        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            if _is_full_suite(cmd):
                write_phase_marker("full_test_suite", {"pytest_exit": exit_code}, session_id=session_id)
            elif _is_smoke(cmd):
                write_phase_marker("smoke_validation", {"pytest_exit": exit_code}, session_id=session_id)
            audit_exit = _audit_exit_from_cmd(cmd, stdout, stderr, exit_code)
            if audit_exit is not None:
                write_phase_marker("audit_quality_checks", {"tool_exit": audit_exit, "tool": cmd.split()[0] if cmd else "unknown"}, session_id=session_id)

        print(json.dumps({"continue": True}))
        sys.exit(0)

    except Exception as e:
        print(json.dumps({"continue": True}), file=sys.stderr)
        print(f"Breadcrumb tracking failed: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
