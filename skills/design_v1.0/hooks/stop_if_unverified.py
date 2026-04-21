"""Pre-response hook: block design output unless claim verification completed.

Checks for a .verified_<RUNID> state file written by verify_claims.py.
If DESIGN_RUN_ID is set but no verification flag exists, blocks the response.

Allow conditions:
  - DESIGN_RUN_ID not set (non-design session)
  - DESIGN_RUN_ID set and .verified_<RUNID> flag exists

Block conditions:
  - DESIGN_RUN_ID set but .verified_<RUNID> flag missing
"""
import json
import os
import sys
from pathlib import Path


def _state_dir() -> Path:
    """Resolve the arch_decisions directory for verification state files."""
    # Use .claude/arch_decisions/ relative to the design skill root
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root.parent.parent.parent / ".claude" / "arch_decisions"


def main() -> None:
    # Read stdin (hook protocol requires consuming stdin)
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""

    # If no stdin or not JSON, allow — this isn't a design session
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
        # No DESIGN_RUN_ID — not a design session, allow
        print(json.dumps({"decision": "allow"}))
        return

    # Check for verification flag
    state_dir = _state_dir()
    flag_file = state_dir / f".verified_{run_id}"

    if not flag_file.exists():
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"DESIGN VERIFICATION REQUIRED: RUN ID {run_id} has no "
                f"claim verification record. You must run verify_claims.py "
                f"with this RUN ID before presenting architecture output. "
                f"Expected flag: {flag_file}"
            )
        }))
        return

    # Verification passed — clean up the flag and allow
    try:
        os.remove(flag_file)
    except OSError:
        pass

    print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
