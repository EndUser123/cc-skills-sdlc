import json
import logging
import os
import sys
from pathlib import Path

# Setup paths for imports
_HOOKS_DIR = Path(__file__).resolve().parent
_REFACTOR_HOOKS = _HOOKS_DIR.parent / "skills" / "refactor" / "hooks"
_CODE_HOOKS = _HOOKS_DIR.parent / "skills" / "code_v4.0" / "hooks"

if str(_REFACTOR_HOOKS) not in sys.path:
    sys.path.insert(0, str(_REFACTOR_HOOKS))
if str(_CODE_HOOKS) not in sys.path:
    sys.path.insert(0, str(_CODE_HOOKS))

# Import child hooks
import PreToolUse_plan_consumer_gate as plan_gate
import PreToolUse_refactor_gate as refactor_gate

_log = logging.getLogger(__name__)

# SEQUENCE of run() functions
SEQUENCE = [
    ("plan_gate", plan_gate.run),
    ("refactor_gate", refactor_gate.run),
]

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
                # If child hook returns a deny/block, we honor it immediately
                if result.get("decision") in ("deny", "block"):
                    if "additionalContext" not in result:
                        result["additionalContext"] = ""
                    result["additionalContext"] += "\n\n💡 Unexplained block? Run /doctor to check plugin connectivity."
                    print(json.dumps(result))
                    sys.exit(2)
        except Exception as e:
            _log.error(f"PreToolUse child hook '{name}' crashed: {e}", exc_info=True)

    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
