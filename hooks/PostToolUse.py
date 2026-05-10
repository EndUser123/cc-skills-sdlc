import json
import logging
import os
import sys
from pathlib import Path

# Setup paths for imports
_HOOKS_DIR = Path(__file__).resolve().parent
_REFACTOR_HOOKS = _HOOKS_DIR.parent / "skills" / "refactor" / "hooks"
if str(_REFACTOR_HOOKS) not in sys.path:
    sys.path.insert(0, str(_REFACTOR_HOOKS))

# Import child hooks
import PostToolUse_refactor_transition as transition
import PostToolUse_refactor_validator as validator

_log = logging.getLogger(__name__)

# SEQUENCE of run() functions
SEQUENCE = [
    ("validator", validator.run),
    ("transition", transition.run),
]

def main():
    raw_input = sys.stdin.read().strip()
    if not raw_input:
        sys.exit(0)

    try:
        data = json.loads(raw_input.lstrip("\ufeff"))
    except json.JSONDecodeError:
        sys.exit(0)

    results = []
    for name, run_func in SEQUENCE:
        try:
            result = run_func(data)
            if result:
                # If child hook returns a block or specific decision, we honor it
                if result.get("decision") == "block":
                    print(json.dumps(result))
                    sys.exit(1)
                results.append(result)
        except Exception as e:
            _log.error(f"PostToolUse child hook '{name}' crashed: {e}", exc_info=True)

    # Summarize results
    if results:
        # Taking the first non-None result for decision protocol
        print(json.dumps(results[0]))
    else:
        print(json.dumps({"decision": "allow"}))
    
    sys.exit(0)

if __name__ == "__main__":
    main()
