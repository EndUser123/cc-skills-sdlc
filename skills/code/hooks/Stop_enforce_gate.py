#!/usr/bin/env python3
"""
Stop hook for /code — shared enforce layer.

Uses the shared stop_gate.evaluate_gates() with code config.
"""

import os
import sys
from pathlib import Path

# Add enforce library to path
_ROOT = Path(__file__).resolve().parents[3]  # skills/code -> cc-skills-sdlc
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforce.stop_gate import load_config_for_skill, evaluate_gates


def run(input_data: dict) -> dict | None:
    """In-process hook logic for router dispatch."""
    skill_id = "code"
    try:
        config = load_config_for_skill(skill_id)
    except KeyError:
        return {"decision": "block", "reason": f"No enforce config for {skill_id}"}

    exit_code, message = evaluate_gates(skill_id, config, os.environ)
    if exit_code == 2:
        return {"decision": "block", "reason": message}
    if exit_code == 1 and message:
        return {"decision": "approve"}
    return None  # clean — no message


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
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}
    result = run(input_data)
    if result and result.get("decision") == "block":
        if "additionalContext" not in result:
            result["additionalContext"] = ""
        result["additionalContext"] += "\n\nRun /code to completion, or use --fast to skip heavy gates."
        print(json.dumps(_normalize_stdout(result)))
        sys.exit(2)
    elif result and result.get("additionalContext"):
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()