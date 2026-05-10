#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _add_import_paths() -> None:
    root = Path(__file__).resolve().parents[2]
    package_src = root / "contract-primitives" / "src"
    if str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))
    hooks_dir = root / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))


def _should_skip_for_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lower()
    return (
        "/.claude/plans/" in normalized
        or "/.claude/arch_decisions/" in normalized
        or normalized.endswith("/plan.md")
        or normalized.endswith("/.claude/plan.md")
    )


def _required_phase() -> int:
    raw = os.environ.get("CLAUDE_REQUIRED_PLAN_PHASE", "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return 1


def run(payload: dict) -> dict | None:
    """In-process hook logic."""
    tool_name = payload.get("tool_name") or payload.get("name") or ""
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        return None

    tool_input = payload.get("tool_input") or {}
    file_path = (
        tool_input.get("file_path")
        or os.environ.get("CLAUDE_TOOL_EDIT_FILE")
        or os.environ.get("CLAUDE_TOOL_WRITE_FILE")
        or ""
    )
    if file_path and _should_skip_for_path(file_path):
        return None

    _add_import_paths()
    from contract_primitives import discover_local_plan_path, validate_plan_for_execution

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    plan_path = discover_local_plan_path(project_dir=project_dir, cwd=os.getcwd())
    if not plan_path:
        return None

    from code_phase_ledger import write_phase_marker, read_phase_ledger

    session_id = payload.get("session_id")
    ledger = read_phase_ledger(session_id=session_id)
    precheck_done = False
    if ledger:
        precheck_phase = ledger.get("phases", {}).get("consumer_contract_precheck", {})
        precheck_done = bool(precheck_phase.get("done"))

    result = validate_plan_for_execution(
        plan_path,
        consumer="/code",
        required_phase=_required_phase(),
    )
    if result.allowed:
        if not precheck_done:
            write_phase_marker(
                "consumer_contract_precheck",
                {
                    "result": "pass",
                    "verify_status": result.verify_status,
                    "claimed_status": result.claimed_status,
                },
                session_id=session_id
            )
        return {
            "decision": "approve",
            "reason": result.reason,
            "context": {
                "plan_path": result.plan_path,
                "verify_status": result.verify_status,
                "claimed_status": result.claimed_status,
            },
        }

    return {
        "decision": "deny",
        "reason": result.reason,
        "context": {
            "plan_path": result.plan_path,
            "verify_status": result.verify_status,
            "claimed_status": result.claimed_status,
            "next_action": result.next_action,
            "blocking_findings": result.blocking_findings,
        },
    }


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        print(json.dumps({"decision": "approve", "reason": "Invalid hook payload"}))
        sys.exit(0)

    result = run(payload)
    if result:
        print(json.dumps(result))
        if result.get("decision") == "deny":
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
