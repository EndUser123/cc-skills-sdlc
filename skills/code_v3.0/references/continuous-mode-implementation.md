# Continuous Execution Mode Implementation Details

## Implementation

### Step 1: Detect continuous mode at workflow start
```bash
# Run detection hook at Phase 0 (analyze_query_intent)
python .claude/skills/code/hooks/detect_continuous_mode.py "$USER_QUERY"

# Hook creates:
# - Environment variable: CODE_CONTINUOUS_MODE=1
# - State file: .claude/state/code_continuous_mode.flag
```

### Step 2: Check continuous mode at each phase boundary
```bash
# Before ANY phase completion summary or "Next Steps" menu:
check_continuous_mode() {
  # Check state file first (persists across subprocess boundaries)
  if [ -f ".claude/state/code_continuous_mode.flag" ]; then
    return 0  # Continuous mode active
  fi

  # Fallback: check environment variable
  if [ "${CODE_CONTINUOUS_MODE:-0}" = "1" ]; then
    return 0  # Continuous mode active
  fi

  return 1  # Continuous mode NOT active
}

# At each phase boundary:
if check_continuous_mode; then
  # SUPPRESS all summaries and menus
  echo "Phase ${N} complete, continuing to Phase ${N+1}..."
  # DO NOT STOP, DO NOT SHOW OPTIONS
  continue  # Immediately proceed to next phase
else
  # Default behavior: show summary and options
  show_phase_summary
  present_next_steps_menu
fi
```

### Step 3: Phase boundary enforcement rules

When `continuous_mode` is active:
- **NEVER stop** after completing a phase (Phase boundaries are NOT stopping points)
- **NEVER stop** after completing a subset of tasks
- **NEVER summarize** progress and wait for user to say "continue"
- **ONLY stop** for genuine blockers:
  - Ambiguous requirements (cannot proceed without clarification)
  - Conflicting constraints (impossible to satisfy both)
  - Actual errors/failures (tests fail, crashes, exceptions)
  - Missing critical information (no API to call, dependency doesn't exist)

When `continuous_mode` is **NOT** active:
- Show phase-completion summaries
- Present "Next Steps" menu after ALL phases complete
- User must explicitly choose next action

### Step 4: Cleanup after workflow completes
```bash
# Remove state file after all phases complete
rm -f .claude/state/code_continuous_mode.flag
unset CODE_CONTINUOUS_MODE
```

## Difference from Single-Task Mode

- **Loop mode** (default): `/code plan.md` -> Multi-task plan, autonomous iteration
- **Single-task** (`--no-loop`): `/code <task description>` -> One feature, DONE

## Configuration

- Expects `.claude/loop/config.yaml` for exit policy settings
- Uses loop-core infrastructure (`loop_policy`, `state_manager`, etc.)
- Per-terminal state isolation (each terminal gets own state directory)
- Practical verification: checks plan requirements against completed tasks
- Chat concern extraction: detects blockers/issues in conversation history
