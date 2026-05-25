#!/usr/bin/env python3
"""
PreToolUse hook for /code (code_v4.0) — plan consumer gate + shared ledger write.

Authoritative success point: validate_plan_for_execution() returns allowed=True.
At that point, writes consumer_contract_precheck to the shared phase ledger
under skill_id="code_v4.0".
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[3]
_ENFORCE = _ROOT / "enforce"
if str(_ENFORCE) not in sys.path:
    sys.path.insert(0, str(_ENFORCE))
if str(_ROOT / "contract-primitives" / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "contract-primitives" / "src"))


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


def run(input_data: dict) -> dict | None:
    """In-process hook logic for router dispatch."""
    tool_name = input_data.get("tool_name") or input_data.get("name") or ""
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        return None

    tool_input = input_data.get("tool_input") or {}
    file_path = (
        tool_input.get("file_path")
        or os.environ.get("CLAUDE_TOOL_EDIT_FILE")
        or os.environ.get("CLAUDE_TOOL_WRITE_FILE")
        or ""
    )
    if file_path and _should_skip_for_path(file_path):
        return None

    from contract_primitives import discover_local_plan_path, validate_plan_for_execution
    from enforce.phase_ledger import write_phase_marker, read_phase_ledger

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    plan_path = discover_local_plan_path(project_dir=project_dir, cwd=os.getcwd())
    if not plan_path:
        return None

    ledger = read_phase_ledger("code")
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
                "code",
                "consumer_contract_precheck",
                {
                    "result": "pass",
                    "verify_status": result.verify_status,
                    "claimed_status": result.claimed_status,
                },
            )
        return None  # approve — no denial

    return {
        "decision": "deny",
        "reason": result.reason,
        "additionalContext": (
            f"Plan verification failed: verify={result.verify_status}, "
            f"claimed={result.claimed_status}. {result.next_action or ''}"
        ),
    }


def _normalize_stdout(data: dict) -> dict:
    """Normalize hook output to Claude Code Zod-valid schema."""
    if data.get('decision') == 'allow':
        return {'decision': 'approve'}
    if data.get('decision') == 'block':
        return {'decision': 'block', 'reason': data.get('reason', '')}
    if 'allow' in data:
        if data['allow'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'continue' in data:
        if data['continue'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'ok' in data:
        return {'decision': 'approve'}
    return data


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    result = run(payload)
    if result and result.get("decision") in ("deny", "block"):
        print(json.dumps(_normalize_stdout(result)))
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()