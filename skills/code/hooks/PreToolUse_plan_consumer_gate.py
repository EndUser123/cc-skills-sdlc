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


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        print(json.dumps({"decision": "allow", "reason": "Invalid hook payload"}))
        sys.exit(0)

    tool_name = payload.get("tool_name") or payload.get("name") or ""
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        print(json.dumps({"decision": "allow", "reason": "Tool does not mutate files"}))
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    file_path = (
        tool_input.get("file_path")
        or os.environ.get("CLAUDE_TOOL_EDIT_FILE")
        or os.environ.get("CLAUDE_TOOL_WRITE_FILE")
        or ""
    )
    if file_path and _should_skip_for_path(file_path):
        print(json.dumps({"decision": "allow", "reason": "Editing the source plan/ADR artifact"}))
        sys.exit(0)

    _add_import_paths()
    from contract_primitives import discover_local_plan_path, validate_plan_for_execution

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    plan_path = discover_local_plan_path(project_dir=project_dir, cwd=os.getcwd())
    if not plan_path:
        print(json.dumps({"decision": "allow", "reason": "No local plan artifact discovered"}))
        sys.exit(0)

    result = validate_plan_for_execution(
        plan_path,
        consumer="/code",
        required_phase=_required_phase(),
    )
    if result.allowed:
        print(
            json.dumps(
                {
                    "decision": "allow",
                    "reason": result.reason,
                    "context": {
                        "plan_path": result.plan_path,
                        "verify_status": result.verify_status,
                        "claimed_status": result.claimed_status,
                    },
                }
            )
        )
        sys.exit(0)

    print(
        json.dumps(
            {
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
        )
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
