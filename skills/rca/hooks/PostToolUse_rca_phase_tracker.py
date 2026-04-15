#!/usr/bin/env python3
"""
PostToolUse: Phase tracker for /rca workflow.
Updates phase based on tool usage patterns during RCA.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
STATE_FILE = STATE_DIR / "rca_workflow.json"

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

# Import metrics_tracker and auto_research (optional - from rca package)
record_delegation_event = None
should_trigger_research = None
try:
    # Add package src to path for import
    _hook_dir = Path(__file__).parent.parent.parent.parent / "src"
    if str(_hook_dir) not in sys.path:
        sys.path.insert(0, str(_hook_dir))
    from rca.auto_research import should_trigger_research
    from rca.metrics_tracker import record_delegation_event
except ImportError:
    # Fallback: try CSF path for development environments
    CSF_SRC = os.environ.get("CSF_SRC", "P:/__csf/src")
    if os.path.exists(CSF_SRC):
        sys.path.insert(0, CSF_SRC)
        try:
            from rca.auto_research import should_trigger_research
            from rca.metrics_tracker import record_delegation_event
        except ImportError:
            record_delegation_event = None
            should_trigger_research = None
    else:
        record_delegation_event = None
        should_trigger_research = None


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


# RCA engine execution patterns
EXECUTION_PATTERN = r"src\.rca|from rca\.|SimpleRCAEngine|RCAEngine|EnhancementRouter|daemon_client|RCA HANDOFF BUNDLE"
DELEGATION_PATTERN = r"rca-specialist"

# Hook error detection pattern
HOOK_ERROR_PATTERN = r"hook error|hook_error|PostToolUse:.*error|PreToolUse:.*error"
DIAGNOSTIC_SWEEP_PATTERN = (
    r"stage 2c|diagnostic sweep|cc_errors\.jsonl|timeout pattern|signal-source"
)

# RCA phases with detection patterns
# Note: tool_patterns match against tool_name and serialized tool_input
#       patterns match against tool_output content (case-insensitive)
RCA_PHASES = {
    -1: {
        "name": "history_check",
        "patterns": [
            # CKS/CHS search in output
            r"search.*cks",
            r"search.*history",
            r"similar.*past",
            r"regression.*check",
            r"progressive.?search",
            # Knowledge retrieval indicators
            r"found \d+ similar",
            r"past.*session",
            r"cks.*result",
            r"chs.*result",
            # Skill names in output
            r"/search",
            r"progressive-search",
            r"context7",
        ],
        "tool_patterns": [
            # Direct function calls (stable)
            r"search_cks_history",
            # CKS/CHS search via various paths (match file names, not any "search")
            r"Bash.*search\.py",
            r"Bash.*search_cli",
            r"Bash.*-m.*csf.*search",
            r"Bash.*/search",
            r"Bash.*csf/cli",
            r"Bash.*cks|chs",  # CKS/CHS in command
            # Skill invocations (by skill name)
            r"Skill.*skill.*search",
            r"Skill.*skill.*progressive",
            r"skill_name.*search",
            # Web research (for library docs lookup)
            r"WebSearch",
            r"WebFetch",
            r"mcp__web",
            # Context7 (library docs)
            r"context7.*resolve",
            r"context7.*query",
            r"mcp__plugin_context7",
            # CKS memory/search
            r"mcp__plugin_claude-mem",
            r"claude-mem.*search",
        ],
    },
    0: {
        "name": "system_context_check",
        "patterns": [r"system.?check", r"context.?check", r"dependencies.?running"],
        "tool_patterns": [
            r"Bash.*systemctl",
            r"Bash.*service.*status",
            r"Bash.*ps.*aux",
            r"Bash.*pgrep",
        ],
    },
    1: {
        "name": "data_flow_trace",
        "patterns": [r"tracing.?data.?flow", r"data.?flow", r"entry.?point", r"failure.?point"],
        "tool_patterns": [
            r"Read.*config",
            r"Read.*routing",
            r"Grep.*def ",
            r"Grep.*import ",
            r"Grep.*class ",
            r"Read.*__init__",
            # Serena MCP symbolic tools (code navigation = data flow tracing)
            r"mcp__plugin_serena.*find_symbol",
            r"mcp__plugin_serena.*find_referencing",
            r"mcp__plugin_serena.*get_symbols_overview",
            r"mcp__plugin_serena.*type.*hierarchy",
            r"mcp__plugin_serena.*jet_brains",
        ],
    },
    2: {
        "name": "hypothesis_ledger",
        "patterns": [r"hypothesis.?ledger", r"hypotheses?", r"confidence.*scoring"],
        "tool_patterns": [],
    },
    3: {
        "name": "five_whys",
        "patterns": [r"five.?whys", r"why.*did", r"root.?cause"],
        "tool_patterns": [],
    },
    4: {
        "name": "invariant_check",
        "patterns": [r"invariant", r"violated", r"assertion"],
        "tool_patterns": [],
    },
    5: {
        "name": "counterfactual_test",
        "patterns": [r"counterfactual", r"with.*bug", r"without.*bug"],
        "tool_patterns": [
            r"Bash.*pytest",
            r"Bash.*python.*-m.*test",
            r"Bash.*uv run.*test",
            r"Bash.*python.*test",
        ],
    },
    6: {
        "name": "timeboxing_escalation",
        "patterns": [r"time.?box", r"escalat", r"--debate", r"--challenge"],
        "tool_patterns": [],
    },
}


def detect_phase_from_output(output: str) -> int:
    """Detect RCA phase from tool output content."""
    if not output:
        return None

    output_lower = output.lower()

    # Return highest matching phase so we don't regress
    best_phase = None
    for phase_num, phase_data in RCA_PHASES.items():
        # Check for phase name in output
        if phase_data["name"] in output_lower:
            if best_phase is None or phase_num > best_phase:
                best_phase = phase_num
            continue

        # Check for patterns
        for pattern in phase_data["patterns"]:
            if re.search(pattern, output_lower):
                if best_phase is None or phase_num > best_phase:
                    best_phase = phase_num
                break

    return best_phase


def detect_phase_from_tool(tool_name: str, tool_input: dict) -> int:
    """Detect RCA phase from tool usage.

    Checks multiple sources for robustness:
    1. Tool name (e.g., "Skill", "Bash")
    2. skill_name in tool_input (e.g., "search", "progressive-search")
    3. Serialized tool_input string
    """
    # Extract skill_name if present (most reliable for Skill invocations)
    skill_name = None
    if isinstance(tool_input, dict):
        skill_name = tool_input.get("skill_name") or tool_input.get("skill")

    # Build search string from multiple sources
    search_parts = [tool_name]
    if skill_name:
        search_parts.append(skill_name)
    search_parts.append(str(tool_input))
    tool_str = " ".join(search_parts)

    for phase_num, phase_data in RCA_PHASES.items():
        for pattern in phase_data.get("tool_patterns", []):
            if re.search(pattern, tool_str, re.IGNORECASE):
                return phase_num
    return None


def detect_execution(tool_name: str, tool_input: dict, tool_output: str) -> bool:
    """Detect if RCA engine was executed."""
    # Check tool commands for execution pattern
    if tool_name == "Bash":
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
        if re.search(EXECUTION_PATTERN, command, re.IGNORECASE):
            return True

    # Check tool output for execution pattern
    if tool_output and re.search(EXECUTION_PATTERN, tool_output, re.IGNORECASE):
        return True

    return False


def detect_successful_tool_execution(payload: dict) -> bool:
    """Detect whether tool execution completed successfully."""
    # Common PostToolUse payload variants across hook routers.
    for key in ("tool_result", "tool_response", "response"):
        block = payload.get(key)
        if not isinstance(block, dict):
            continue
        for exit_key in ("exitCode", "exit_code", "error_code", "returncode"):
            exit_value = block.get(exit_key)
            if exit_value is None:
                continue
            try:
                return int(exit_value) == 0
            except (TypeError, ValueError):
                continue
        if block.get("is_error") is True:
            return False
        if block.get("error"):
            return False
    # No explicit status available; treat as unknown success and allow legacy behavior.
    return True


def detect_delegation(tool_name: str, tool_input: dict, tool_output: str) -> bool:
    """Detect if RCA specialist delegation was executed."""
    if tool_name != "Task":
        return False
    payload_text = f"{tool_input} {tool_output}"
    return bool(re.search(DELEGATION_PATTERN, payload_text, re.IGNORECASE))


def detect_problem_type(tool_output: str) -> str | None:
    """Detect if this RCA is investigating a hook error problem.

    Args:
        tool_output: The tool output to analyze

    Returns:
        "hook_error" if hook error patterns detected, None otherwise
    """
    if not tool_output:
        return None

    if re.search(HOOK_ERROR_PATTERN, tool_output, re.IGNORECASE):
        return "hook_error"

    return None


def check_auto_research_trigger(tool_output: str) -> dict | None:
    """Check if auto-research should be triggered based on tool output.

    Analyzes tool output for signs that external library research is needed:
    - External library names (fastapi, django, yt-dlp, etc.)
    - Staleness keywords (deprecated, removed in, changed in)
    - Import errors, AttributeError, ModuleNotFoundError

    Args:
        tool_output: The tool output to analyze

    Returns:
        Dict with research trigger info if triggered, None otherwise:
        {
            "should_research": bool,
            "query": str (built search query),
            "libraries": list[str],
            "confidence": float,
            "reason": str
        }
    """
    if not tool_output or not should_trigger_research:
        return None

    try:
        trigger = should_trigger_research(tool_output)
        if trigger.should_research:
            return {
                "should_research": True,
                "query": f"{trigger.libraries[0] if trigger.libraries else ''} {tool_output[:50]}",
                "libraries": trigger.libraries,
                "confidence": trigger.confidence,
                "reason": trigger.reason,
            }
    except Exception:
        pass

    return None


def detect_diagnostic_sweep(tool_output: str) -> bool:
    """Detect evidence that diagnostic sweep/source verification was executed."""
    if not tool_output:
        return False
    return bool(re.search(DIAGNOSTIC_SWEEP_PATTERN, tool_output, re.IGNORECASE))


@hook_main
def main():
    """Entry point - update RCA phase based on tool usage."""
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({}))
        sys.exit(0)

    # Check if RCA workflow is active
    if not STATE_FILE.exists():
        print(json.dumps({}))
        sys.exit(0)

    try:
        with FileLock(STATE_FILE.parent / ".lock"):
            state = json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        print(json.dumps({}))
        sys.exit(0)

    # Skip if RCA already complete
    if state.get("complete", False):
        print(json.dumps({}))
        sys.exit(0)

    # Detect phase from tool usage or output
    tool_name = payload.get("tool_name", "")
    tool_output = payload.get("tool_output", "")
    tool_input = payload.get("tool_input", {})

    detected_phase = detect_phase_from_tool(tool_name, tool_input) or detect_phase_from_output(
        tool_output
    )

    # Detect RCA engine execution
    engine_executed = detect_execution(tool_name, tool_input, tool_output)
    execution_success = detect_successful_tool_execution(payload)
    delegation_executed = detect_delegation(tool_name, tool_input, tool_output)

    # Update state if phase or execution detected
    state_modified = False

    if engine_executed and execution_success and not state.get("execution_satisfied", False):
        state["execution_satisfied"] = True
        state["execution_tool"] = tool_name
        state["execution_time"] = datetime.now().isoformat()
        state_modified = True

    if delegation_executed and not state.get("delegation_satisfied", False):
        state["delegation_satisfied"] = True
        state["delegation_tool"] = tool_name
        state["delegation_time"] = datetime.now().isoformat()
        if state.get("session_id"):
            try:
                record_delegation_event(
                    session_id=state["session_id"],
                    expected_count=1,
                    executed_count=1,
                    source="rca_task",
                )
            except Exception:
                pass
        state_modified = True

    if detected_phase is not None and detected_phase >= state.get("current_phase", -2):
        # Record current phase as completed, then advance
        # Default -2 so Phase -1 (history_check) can be detected on first tool use
        current = state.get("current_phase", -2)
        state["phases_completed"] = state.get("phases_completed", [])
        if current not in state["phases_completed"]:
            state["phases_completed"].append(current)
        if detected_phase > current:
            state["current_phase"] = detected_phase
        if detected_phase not in state["phases_completed"]:
            state["phases_completed"].append(detected_phase)
        state["updated_at"] = datetime.now().isoformat()
        state_modified = True

    # Detect problem type (e.g., hook_error)
    problem_type = detect_problem_type(tool_output)
    if problem_type and state.get("problem_type") != problem_type:
        state["problem_type"] = problem_type
        state["problem_type_detected"] = True
        state_modified = True

    if detect_diagnostic_sweep(tool_output):
        # Track that RCA touched cross-source diagnostics before claims.
        state["diagnostic_sweep_observed"] = True
        state_modified = True

    # Check auto-research trigger (notify but don't block)
    research_trigger = check_auto_research_trigger(tool_output)
    if research_trigger and research_trigger.get("should_research"):
        # Store research trigger in state for later use
        state["research_trigger"] = {
            "query": research_trigger.get("query", ""),
            "libraries": research_trigger.get("libraries", []),
            "confidence": research_trigger.get("confidence", 0),
            "reason": research_trigger.get("reason", ""),
            "triggered_at": datetime.now().isoformat(),
        }
        state_modified = True

    if state_modified:
        with FileLock(STATE_FILE.parent / ".lock"):
            STATE_FILE.write_text(json.dumps(state, indent=2))

        if detected_phase is not None:
            result = {
                "message": f"📍 RCA Phase {detected_phase}: {RCA_PHASES[detected_phase]['name']}"
            }
            print(json.dumps(result))
        elif delegation_executed:
            result = {"message": "✅ RCA specialist delegation detected"}
            print(json.dumps(result))
        elif engine_executed:
            result = {"message": "✅ RCA engine execution detected"}
            print(json.dumps(result))
        elif research_trigger and research_trigger.get("should_research"):
            # Notify about research trigger
            libs = research_trigger.get("libraries", [])
            libs_str = ", ".join(libs[:3]) if libs else "external library"
            result = {
                "message": f"🔍 Auto-research triggered: {libs_str} - Consider WebSearch for current docs"
            }
            print(json.dumps(result))
        else:
            print(json.dumps({}))
    else:
        print(json.dumps({}))

    sys.exit(0)


if __name__ == "__main__":
    main()
