#!/usr/bin/env python3
"""
PostToolUse: State initializer for /rca workflow.
Called after Skill tool runs - creates initial state if /rca was invoked.

This ensures SessionEnd has valid state to clean up.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
STATE_FILE = STATE_DIR / "rca_workflow.json"
ACTIVE_SESSION_FILE = STATE_DIR / "active_session.json"
HANDOFF_FILE = STATE_DIR / "debug_handoff.json"

# Import auto-logging decorator (optional)
_hooks_lib = CLAUDE_HOME / "hooks" / "__lib"
if _hooks_lib.exists():
    sys.path.insert(0, str(_hooks_lib))
    try:
        from hook_base import hook_main
    except ImportError:
        hook_main = lambda f: f  # Fallback: no-op decorator
else:
    hook_main = lambda f: f  # Fallback: no-op decorator

# Import metrics_tracker (optional - from rca package)
record_delegation_event = None
try:
    # Add package src to path for import
    _hook_dir = Path(__file__).parent.parent.parent.parent / "src"
    if str(_hook_dir) not in sys.path:
        sys.path.insert(0, str(_hook_dir))
    from rca.metrics_tracker import record_delegation_event
except ImportError:
    # Fallback: try CSF path for development environments
    CSF_SRC = os.environ.get("CSF_SRC", "P:\\\\\\__csf/src")
    if os.path.exists(CSF_SRC):
        sys.path.insert(0, CSF_SRC)
        try:
            from rca.metrics_tracker import record_delegation_event
        except ImportError:
            record_delegation_event = None
    else:
        record_delegation_event = None


# FileLock for cross-terminal state file safety
try:
    import portalocker

    class FileLock:
        def __init__(self, lock_path, timeout=5.0):
            self.lock_path = Path(lock_path)
            self.timeout = timeout
            self.lock_file = None

        def __enter__(self):
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.lock_file = open(self.lock_path, "w")
                portalocker.lock(self.lock_file, portalocker.LOCK_EX)
            except Exception:
                return self
            return self

        def __exit__(self, *args):
            if self.lock_file:
                try:
                    self.lock_file.close()
                except Exception:
                    pass
except ImportError:

    class FileLock:
        def __init__(self, lock_path, timeout=5.0):
            self.lock_path = lock_path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass


# Constants for stdin validation
MAX_STDIN_SIZE = 1 * 1024 * 1024  # 1MB max payload size


def validate_stdin_payload(raw_stdin: str) -> dict:
    """Validate stdin payload with size and schema checks.

    Returns empty dict on validation failure (graceful degradation).
    Logs errors to stderr for debugging.
    """
    # Check size limit
    if len(raw_stdin.encode("utf-8")) > MAX_STDIN_SIZE:
        sys.stderr.write(f"[RCA_INIT] Payload exceeds {MAX_STDIN_SIZE} bytes, rejected.\n")
        return {}

    # Parse JSON
    try:
        payload = json.loads(raw_stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[RCA_INIT] JSON decode error: {e}\n")
        return {}

    # Validate required keys for PostToolUse
    required_keys = {"tool_name", "tool_input", "tool_response"}
    missing_keys = required_keys - payload.keys()
    if missing_keys:
        sys.stderr.write(f"[RCA_INIT] Missing required keys: {missing_keys}\n")
        return {}

    # Ensure tool_name is a string
    if not isinstance(payload.get("tool_name"), str):
        sys.stderr.write("[RCA_INIT] tool_name must be a string\n")
        return {}

    return payload


# RCA phases from SKILL.md
RCA_PHASES = [
    "0_system_context",
    "1_data_flow_trace",
    "2_hypothesis_ledger",
    "3_five_whys",
    "4_invariant_check",
    "5_counterfactual_test",
    "6_timeboxing_escalation",
]


def normalize_skill_name(value: str) -> str:
    """Normalize skill identifiers from hook payloads.

    Supports values like:
    - "rca"
    - "/rca"
    - "/rca \""
    - "rca --debate"
    """
    if not isinstance(value, str):
        return ""
    token = value.strip().split()[0] if value.strip() else ""
    token = token.strip("\"'")
    if token.startswith("/"):
        token = token[1:]
    return token.lower()


def extract_skill_name(data: dict) -> str:
    """Extract normalized skill name from PostToolUse payload."""
    tool_input = data.get("tool_input", {})

    # Handle dict format
    if isinstance(tool_input, dict):
        for key in ("skill", "name", "command", "input"):
            if key in tool_input:
                normalized = normalize_skill_name(str(tool_input[key]))
                if normalized:
                    return normalized

    # Handle string format
    if isinstance(tool_input, str):
        return normalize_skill_name(tool_input)

    return ""


def get_current_terminal_id() -> str:
    """Get the current Claude Code terminal ID from environment.

    Multi-terminal safety: each terminal has a unique CLAUDE_TERMINAL_ID.
    Terminal ID persists across compaction, unlike CLAUDE_SESSION_ID which changes.
    This ensures Terminal A's RCA state is recognized even after compaction.
    """
    return os.environ.get("CLAUDE_TERMINAL_ID", "").strip()


def initialize_state() -> dict:
    """Initialize workflow state for /rca."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Get current terminal ID for multi-terminal safety
    current_terminal_id = get_current_terminal_id()

    # Check if state already exists and is active
    if STATE_FILE.exists():
        try:
            with FileLock(STATE_FILE.parent / ".lock"):
                existing = json.loads(STATE_FILE.read_text())
                existing_terminal_id = existing.get("claude_terminal_id")

                # Multi-terminal safety: only reuse state if it belongs to THIS terminal
                if existing_terminal_id and existing_terminal_id != current_terminal_id:
                    # State belongs to a different terminal - don't reuse it
                    # Fall through to create new state for this terminal
                    pass
                else:
                    # Backfill new enforcement fields for older state schema.
                    existing.setdefault("delegation_expected", True)
                    existing.setdefault("delegation_satisfied", False)
                    existing.setdefault("delegation_tool", None)
                    existing.setdefault("delegation_time", None)
                    # If RCA in progress, don't reset
                    if existing.get("current_phase", 0) > 0 and not existing.get("complete", False):
                        STATE_FILE.write_text(json.dumps(existing, indent=2))
                        return existing
        except (OSError, json.JSONDecodeError):
            pass

    state = {
        "skill": "rca",
        "current_phase": 0,
        "phases_completed": [],
        "delegation_expected": True,
        "delegation_satisfied": False,
        "delegation_tool": None,
        "delegation_time": None,
        "root_cause_found": False,
        "root_cause": None,
        "hypotheses": [],
        "complete": False,
        "started_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # Store Claude Code terminal ID for multi-terminal safety
    if current_terminal_id:
        state["claude_terminal_id"] = current_terminal_id

    # Attach active session id if available for outcome tracking (legacy).
    if ACTIVE_SESSION_FILE.exists():
        try:
            active = json.loads(ACTIVE_SESSION_FILE.read_text(encoding="utf-8"))
            if active.get("session_id"):
                state["session_id"] = active["session_id"]
        except (OSError, json.JSONDecodeError):
            pass

    # Import handoff state from /debug if available (context continuity)
    if HANDOFF_FILE.exists():
        try:
            handoff = json.loads(HANDOFF_FILE.read_text(encoding="utf-8"))
            if handoff.get("hypotheses"):
                state["hypotheses"] = handoff["hypotheses"]
            if handoff.get("session_id") and not state.get("session_id"):
                state["session_id"] = handoff["session_id"]
            if handoff.get("evidence"):
                state["debug_evidence"] = handoff["evidence"]
            state["handoff_source"] = handoff.get("source", "debug")
            state["handoff_confidence"] = handoff.get("confidence", 0)
            # Consume the handoff file (one-time transfer)
            HANDOFF_FILE.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            pass

    with FileLock(STATE_FILE.parent / ".lock"):
        STATE_FILE.write_text(json.dumps(state, indent=2))
    return state


@hook_main
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
    """Entry point - initialize state if /rca skill invoked."""
    # Read and validate stdin
    raw_stdin = sys.stdin.read()
    # Empty stdin is a normal no-op for many hook invocations.
    if not raw_stdin.strip():
        print(json.dumps({}))
        sys.exit(0)
    payload = validate_stdin_payload(raw_stdin)
    if not payload:
        print(json.dumps({}))
        sys.exit(0)

    # Only process Skill tool
    tool_name = payload.get("tool_name", "")
    if tool_name != "Skill":
        print(json.dumps({}))
        sys.exit(0)

    # Check if an RCA skill variant was invoked
    skill_name = extract_skill_name(payload)
    if skill_name not in ("rca", "rca-v2", "rv2"):
        print(json.dumps({}))
        sys.exit(0)

    # Initialize state
    state = initialize_state()
    if state.get("session_id"):
        try:
            record_delegation_event(
                session_id=state["session_id"],
                expected_count=1,
                executed_count=0,
                source="rca_init",
            )
        except Exception:
            # KPI tracking should not block RCA flow.
            pass

    # Report initialization
    if state.get("current_phase", 0) == 0:
        result = {"message": "✅ /rca workflow state initialized. Phase 0: System Context Check."}
    else:
        result = {"message": f"📍 /rca workflow resuming from Phase {state['current_phase']}."}

    print(json.dumps(_normalize_stdout(result)))
    sys.exit(0)


if __name__ == "__main__":
    main()
