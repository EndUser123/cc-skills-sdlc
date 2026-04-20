import sys
import json
import re

def main() -> None:
    payload = json.load(sys.stdin)
    prompt = (payload.get("prompt") or "").lower()

    keywords = [
        "architecture", "architectural", "system design", "system-design",
        "adr", "architecture decision", "root cause analysis", "rca",
        "multi-terminal", "contract authority", "cap", "planning handoff",
        "/design "
    ]

    is_design_like = any(k in prompt for k in keywords)

    if "/design" in prompt:
        print(json.dumps({"decision": "allow"}))
        return

    if is_design_like:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "Detected an architecture/design-style request. "
                "Please re-run this query using the /design_v1.1 skill, e.g.\n"
                "/design_v1.1 system all \"<your original question>\""
            )
        }))
        return

    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
