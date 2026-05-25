"""Pre-response hook: block design output unless claim verification completed.

Reads .state.json from the session artifact directory.
No DESIGN_RUN_ID env var needed — state is session-scoped.

Allow conditions:
  - No stdin (non-design session)
  - stdin not JSON (non-design session)
  - No state file (not a design session)

Block conditions:
  - State file exists but verified flag is not True
"""
import json
import os
import sys
from pathlib import Path


def _terminal_id() -> str:
    """Resolve terminal ID, falling back to WT_SESSION or 'default'."""
    tid = os.environ.get("CLAUDE_TERMINAL_ID", "").strip()
    if tid:
        return tid
    tid = os.environ.get("WT_SESSION", "").strip()
    if tid:
        return tid
    return "default"


def _state_dir() -> Path:
    """Resolve the design artifact directory for this terminal session."""
    skill_root = Path(__file__).resolve().parent.parent
    tid = _terminal_id()
    return skill_root / ".claude" / ".artifacts" / tid / "design"


def _state_file() -> Path:
    """Path to the session state file."""
    return _state_dir() / ".state.json"


def main() -> None:
    # Read stdin (hook protocol requires consuming stdin)
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""

    # If no stdin or not JSON, allow — this isn't a design session
    if not raw:
        print(json.dumps({"decision": "approve"}))
        return
    try:
        json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "approve"}))
        return

    state_file = _state_file()

    if not state_file.exists():
        print(json.dumps({"decision": "approve"}))
        return

    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        print(json.dumps({"decision": "approve"}))
        return

    if state.get("verified") is True:
        # Clean up and allow
        try:
            state_file.unlink()
        except OSError:
            pass
        print(json.dumps({"decision": "approve"}))
        return

    print(json.dumps({
        "decision": "block",
        "reason": (
            "DESIGN VERIFICATION REQUIRED: Session has no verified flag. "
            "You must run verify_claims.py before presenting architecture output. "
            f"Expected state: {state_file}"
        )
    }))


if __name__ == "__main__":
    main()
