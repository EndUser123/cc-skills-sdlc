#!/usr/bin/env python3
"""
PostToolUse hook for /code (code_v4.0) - Track workflow step completion + phase ledger.

Uses the shared enforce.phase_ledger under skill_id="code_v4.0".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_ENFORCE = _ROOT / "enforce"
if str(_ENFORCE) not in sys.path:
    sys.path.insert(0, str(_ENFORCE))

skill_guard_path = Path("P:\\\\\\packages/skill-guard")
if str(skill_guard_path) not in sys.path:
    sys.path.insert(0, str(skill_guard_path))

from skill_guard.breadcrumb.tracker import set_breadcrumb
from enforce.phase_ledger import write_phase_marker

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

AUDIT_COMMANDS = frozenset([
    "ruff", "ruff check", "ruff format",
    "mypy", "pylint", "tsc", "tsc --noEmit",
    "eslint", "prettier", "ruff --fix",
])


def _is_pytest(cmd: str) -> bool:
    return "pytest" in cmd or "py.test" in cmd


def _is_smoke(cmd: str) -> bool:
    return _is_pytest(cmd) and ("-x" in cmd or "--exitfirst" in cmd or ("test_" in cmd and "tests" not in cmd))


def _is_full_suite(cmd: str) -> bool:
    return _is_pytest(cmd) and not _is_smoke(cmd)


def _audit_exit_from_cmd(cmd: str, stdout: str, stderr: str, exit_code: int) -> int | None:
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
    if tool_name in TOOL_TO_STEP:
        return TOOL_TO_STEP[tool_name]
    if tool_name == "Skill":
        skill_name = tool_input.get("name", "")
        if skill_name == "test":
            return "full_test_suite"
        elif skill_name == "trace":
            return "trace_manual_verification"
    return None


def run(input_data: dict) -> dict | None:
    """In-process hook logic for router dispatch."""
    skill_id = "code"
    try:
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

        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            if _is_full_suite(cmd):
                write_phase_marker(skill_id, "full_test_suite", {"pytest_exit": exit_code}, session_id=session_id)
            elif _is_smoke(cmd):
                write_phase_marker(skill_id, "smoke_validation", {"pytest_exit": exit_code}, session_id=session_id)
            audit_exit = _audit_exit_from_cmd(cmd, stdout, stderr, exit_code)
            if audit_exit is not None:
                write_phase_marker(
                    skill_id, "audit_quality_checks",
                    {"tool_exit": audit_exit, "tool": cmd.split()[0] if cmd else "unknown"},
                    session_id=session_id
                )

    except Exception as e:
        pass  # Non-blocking — breadcrumb/ledger failures shouldn't break workflow

    return None  # PostToolUse hooks never block


def main() -> None:
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)
    run(input_data)
    sys.exit(0)


if __name__ == "__main__":
    main()