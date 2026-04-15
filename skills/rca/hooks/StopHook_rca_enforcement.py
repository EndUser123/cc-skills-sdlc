#!/usr/bin/env python3
"""
Stop hook: Enforce RCA engine execution before completion.
Blocks if /rca was invoked but engine never ran.

Multi-terminal safe: only enforces RCA state that belongs to the current terminal.
Uses CLAUDE_TERMINAL_ID which persists across compaction (unlike CLAUDE_SESSION_ID).

FIXED (2026-03-02): Added staleness check to reject old state files from previous sessions,
preventing misclassification where /arch commands are blocked by stale /rca state.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
STATE_FILE = STATE_DIR / "rca_workflow.json"
HOOK_ERROR_STATE_FILE = STATE_DIR / "hook_error_investigation.json"

# Stale state threshold (10 minutes)
STATE_STALE_SECONDS = 600

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


def get_current_terminal_id() -> str:
    """Get the current Claude Code terminal ID from environment.

    Multi-terminal safety: each terminal has a unique CLAUDE_TERMINAL_ID.
    Terminal ID persists across compaction, unlike CLAUDE_SESSION_ID which changes.
    This ensures Terminal A doesn't get blocked by Terminal B's RCA state,
    and Terminal A's RCA state is recognized even after compaction.
    """
    return os.environ.get("CLAUDE_TERMINAL_ID", "").strip()


def load_hook_error_gate():
    """Load no_handwave_gate from hook_error_rca.py (package local)."""
    hooks_dir = Path(__file__).parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    try:
        from hook_error_rca import no_handwave_gate

        return no_handwave_gate
    except ImportError:
        return None


def is_state_stale(state: dict) -> bool:
    """Check if RCA workflow state is stale (old session).

    State is considered stale if:
    - Updated more than STATE_STALE_SECONDS ago (default: 10 minutes)
    - Missing 'updated_at' timestamp field (legacy state file)

    This prevents old /rca sessions from blocking new /arch commands.
    """
    updated_at_str = state.get("updated_at")
    if not updated_at_str:
        # Missing timestamp means legacy state file - consider stale
        return True

    try:
        updated_at = datetime.fromisoformat(updated_at_str)
        age_seconds = (datetime.now(UTC) - updated_at).total_seconds()
        return age_seconds > STATE_STALE_SECONDS
    except (ValueError, TypeError):
        # Invalid timestamp format - consider stale
        return True


@hook_main
def main():
    """Entry point - enforce RCA engine execution.

    Multi-terminal safety: Only enforces RCA state that belongs to the current
    terminal (identified by CLAUDE_TERMINAL_ID). Terminal ID persists across
    compaction, unlike CLAUDE_SESSION_ID which changes.

    FIXED: Added staleness check to reject old state files, preventing
    misclassification where /arch commands are blocked by stale /rca state.
    """
    # Only block if RCA workflow is active
    if not STATE_FILE.exists():
        print(json.dumps({}))
        sys.exit(0)

    try:
        state = json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        print(json.dumps({}))
        sys.exit(0)

    # NEW: Check if state is stale (old session)
    # This prevents /arch commands from being blocked by old /rca state
    if is_state_stale(state):
        # Auto-cleanup stale state to prevent future false positives
        try:
            STATE_FILE.unlink(missing_ok=True)
        except OSError:
            pass  # Cleanup failed, but don't block on it
        print(json.dumps({}))
        sys.exit(0)

    # Multi-terminal safety: Check if this RCA state belongs to the current terminal
    current_terminal_id = get_current_terminal_id()
    rca_terminal_id = state.get("claude_terminal_id")

    # If state has a terminal_id and it doesn't match ours, ignore it
    # (it belongs to a different terminal)
    if rca_terminal_id and current_terminal_id:
        if rca_terminal_id != current_terminal_id:
            # State belongs to a different terminal - don't enforce
            print(json.dumps({}))
            sys.exit(0)

    # Check if RCA was actually invoked (support /rca aliases too)
    if state.get("skill") not in ("rca", "r", "rca-v2", "rv2"):
        print(json.dumps({}))
        sys.exit(0)

    # Check mechanical requirements
    execution_ok = state.get("execution_satisfied", False)
    delegation_ok = state.get("delegation_satisfied", False)

    # Check methodology requirements (warn, don't hard-block)
    phases_completed = state.get("phases_completed", [])
    has_root_cause = bool(state.get("root_cause"))
    has_hypotheses = bool(state.get("hypotheses"))
    # Key methodology phases: data_flow_trace(1), hypothesis_ledger(2), five_whys(3)
    methodology_phases = {1, 2, 3}
    completed_methodology = methodology_phases.intersection(set(phases_completed))

    # Hard block: engine execution and delegation are mandatory
    if execution_ok and delegation_ok:
        # ===== HOOK-ERROR SPECIFIC ENFORCEMENT =====
        # If problem_type is "hook_error", apply additional gates
        problem_type = state.get("problem_type")
        if problem_type == "hook_error":
            # Load no_handwave_gate
            no_handwave_gate = load_hook_error_gate()

            if not HOOK_ERROR_STATE_FILE.exists():
                block_message = {
                    "decision": "block",
                    "reason": f"""⚠️ HOOK-ERROR RCA INCOMPLETE

Problem type detected as 'hook_error' but Stage 1 never ran.

Required action:
  python $CLAUDE_HOME/hooks/hook_error_rca.py full <event_type> --tool <tool_name>
  (or: python {{CLAUDE_HOME}}/hooks/hook_error_rca.py full <event_type> --tool <tool_name>)

This will:
  1. Enumerate all matching hook registrations
  2. Test each hook in isolation
  3. Classify root cause with evidence

Evidence saved to: {HOOK_ERROR_STATE_FILE}""",
                }
                print(json.dumps(block_message))
                sys.exit(2)

            # Load investigation state
            try:
                investigation = json.loads(HOOK_ERROR_STATE_FILE.read_text())
            except (OSError, json.JSONDecodeError):
                investigation = {}

            test_results = investigation.get("test_results", [])
            if not test_results:
                block_message = {
                    "decision": "block",
                    "reason": """⚠️ HOOK-ERROR RCA INCOMPLETE

Problem type detected as 'hook_error' but Stage 2 never ran.

Hooks were not tested in isolation. Run:
  python $CLAUDE_HOME/hooks/hook_error_rca.py full <event_type> --tool <tool_name>""",
                }
                print(json.dumps(block_message))
                sys.exit(2)

            # Mandatory: diagnostic sweep across cc_errors.jsonl must complete
            if not investigation.get("diagnostic_sweep_completed", False):
                block_message = {
                    "decision": "block",
                    "reason": f"""⚠️ HOOK-ERROR RCA INCOMPLETE

Diagnostic sweep missing (cross-source analysis not completed).

Required evidence before claiming root cause:
  1. cc_errors.jsonl aggregate sweep
  2. Timeout pattern scan (e.g., timeout_imminent clusters)
  3. Cross-reference with isolated hook tests

Re-run:
  python $CLAUDE_HOME/hooks/hook_error_rca.py full <event_type> --tool <tool_name>

Evidence path: {HOOK_ERROR_STATE_FILE}""",
                }
                print(json.dumps(block_message))
                sys.exit(2)

            # Mandatory: timeout pattern scan status must be explicit
            if not investigation.get("timeout_pattern_scan_completed", False):
                block_message = {
                    "decision": "block",
                    "reason": """⚠️ HOOK-ERROR RCA INCOMPLETE

Timeout pattern analysis missing.

You must explicitly inspect cc_errors.jsonl for recurring timeout signals
before finalizing hook-error RCA.""",
                }
                print(json.dumps(block_message))
                sys.exit(2)

            # Mandatory: verify whether "hook error" is functional failure vs display labeling artifact
            if not investigation.get("signal_source_verified", False):
                block_message = {
                    "decision": "block",
                    "reason": f"""⚠️ HOOK-ERROR RCA INCOMPLETE

Signal-source verification missing.

You must verify whether the observed "hook error" is:
  - a real hook failure (non-zero exit / timeout), or
  - stderr-on-exit-0 labeling behavior.

Evidence path: {HOOK_ERROR_STATE_FILE}""",
                }
                print(json.dumps(block_message))
                sys.exit(2)

            # Run no-handwave gate on root cause statement
            if no_handwave_gate:
                root_cause_statement = state.get("root_cause", "")
                gate_passed, gate_reason = no_handwave_gate(test_results, root_cause_statement)

                if not gate_passed:
                    block_message = {
                        "decision": "block",
                        "reason": f"""⚠️ HOOK-ERROR RCA GATE FAILED

{gate_reason}

Root cause must reference specific evidence:
  - File names (e.g., bad_hook.py)
  - Exit codes (e.g., "exit code 1")
  - Error types (e.g., ImportError, SyntaxError)
  - stderr content

Review investigation evidence at: {HOOK_ERROR_STATE_FILE}""",
                    }
                    print(json.dumps(block_message))
                    sys.exit(2)

        # Soft warn: methodology gaps (non-hook-error path)
        warnings = []
        if not has_root_cause:
            warnings.append("no root_cause recorded in workflow state")
        if not has_hypotheses:
            warnings.append("no hypotheses tracked in workflow state")
        missing_phases = methodology_phases - set(phases_completed)
        if missing_phases:
            phase_names = {1: "data_flow_trace", 2: "hypothesis_ledger", 3: "five_whys"}
            warnings.append(
                "phases not detected: " + ", ".join(phase_names[p] for p in sorted(missing_phases))
            )

        # Check if findings were recorded via rca record
        outcome_recorded = state.get("outcome_recorded", False)
        if not outcome_recorded:
            warnings.append(
                "findings not recorded - run: rca record "
                '--outcome <resolved|failed> --problem "..." --root-cause "..." --fix "..."'
            )

        if warnings:
            result = {"message": "RCA methodology gaps (non-blocking): " + "; ".join(warnings)}
            print(json.dumps(result))
        else:
            print(json.dumps({}))
        sys.exit(0)

    # Block completion - RCA workflow incomplete
    missing = []
    if not execution_ok:
        missing.append("engine execution")
    if not delegation_ok:
        missing.append("specialist delegation")
    missing_str = ", ".join(missing)

    # FIXED: More accurate error message
    # Use Skill tool instead of non-existent rca-specialist agent
    block_message = {
        "decision": "block",
        "reason": f"""⚠️ RCA WORKFLOW INCOMPLETE

Previous /rca invocation incomplete: {missing_str}.

Required actions before completion:

1. Run the RCA execution directive (preflight + handoff bundle).
2. Execute specialist delegation using Skill tool:
   Skill("adversarial-rca", args="<prompt>")

   Or use general-purpose agent:
   Task(subagent_type="general-purpose", description="RCA investigation", prompt=<prompt>)

Investigation commands (grep, ls, Read, Bash) are allowed during investigation,
but you must execute both engine preflight and specialist delegation before completing the session.

If you're not currently working on /rca, run: rm {STATE_FILE}""",
    }

    print(json.dumps(block_message))
    sys.exit(2)


if __name__ == "__main__":
    main()
