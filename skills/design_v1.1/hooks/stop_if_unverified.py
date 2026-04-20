import sys
import os
import json
from pathlib import Path

def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    if not raw:
        print(json.dumps({"decision": "allow"}))
        return
    try:
        json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "allow"}))
        return

    run_id = os.environ.get("DESIGN_RUN_ID", "").strip()
    if not run_id:
        print(json.dumps({"decision": "allow"}))
        return

    state_file = Path(__file__).resolve().parent.parent.parent.parent / "skills" / "design_v1.1" / "design" / f".verified_{run_id}"

    if not state_file.exists():
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"CRITICAL: Attempted to output a design without a passing validation "
                f"state for RUN ID {run_id}. You must run validate_design.py and "
                "receive a SUCCESS message before answering the user."
            )
        }))
        return

    try:
        os.remove(state_file)
    except OSError:
        pass

    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
