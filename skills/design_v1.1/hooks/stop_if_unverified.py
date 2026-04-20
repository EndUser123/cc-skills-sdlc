import sys
import os
import json

def main() -> None:
    payload = json.load(sys.stdin)
    run_id = os.environ.get("DESIGN_RUN_ID", "").strip()

    if not run_id:
        print(json.dumps({"decision": "allow"}))
        return

    state_file = os.path.join(
        os.path.dirname(__file__),
        "..", "skills", "design", f".verified_{run_id}"
    )

    if not os.path.exists(state_file):
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
