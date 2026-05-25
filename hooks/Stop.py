import json
import logging
import os
import sys
from pathlib import Path

# Setup paths for imports
_HOOKS_DIR = Path(__file__).resolve().parent
_REFACTOR_HOOKS = _HOOKS_DIR.parent / "skills" / "refactor" / "hooks"
_PREMORTEM_HOOKS = _HOOKS_DIR.parent / "skills" / "pre-mortem" / "hooks"
_CODE_HOOKS = _HOOKS_DIR.parent / "skills" / "code" / "hooks"

if str(_REFACTOR_HOOKS) not in sys.path:
    sys.path.insert(0, str(_REFACTOR_HOOKS))
if str(_PREMORTEM_HOOKS) not in sys.path:
    sys.path.insert(0, str(_PREMORTEM_HOOKS))
if str(_CODE_HOOKS) not in sys.path:
    sys.path.insert(0, str(_CODE_HOOKS))

# Import child hooks
import Stop_refactor_verifier as refactor_stop
import Stop_hook_premortem_quality_gate as premortem_stop
import Stop_enforce_gate as code_stop

_log = logging.getLogger(__name__)

# SEQUENCE of run() functions
SEQUENCE = [
    ("refactor_stop", refactor_stop.run),
    ("premortem_stop", premortem_stop.run),
    ("code_stop", code_stop.run),
]

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


def main():
    raw_input = sys.stdin.read().strip()
    if not raw_input:
        sys.exit(0)

    try:
        data = json.loads(raw_input.lstrip("\ufeff"))
    except json.JSONDecodeError:
        sys.exit(0)

    for name, run_func in SEQUENCE:
        try:
            result = run_func(data)
            if result:
                # If child hook returns a block, we honor it immediately
                if result.get("decision") == "block":
                    if "additionalContext" not in result:
                        result["additionalContext"] = ""
                    result["additionalContext"] += "\n\n💡 Cluster issue? Run /doctor to diagnose plugin health."
                    print(json.dumps(_normalize_stdout(result)))
                    sys.exit(2)
        except Exception as e:
            _log.error(f"Stop child hook '{name}' crashed: {e}", exc_info=True)

    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
