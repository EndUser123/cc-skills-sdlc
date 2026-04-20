# Ralph Loop Auto-Detection Guide

## Ralph Loop Auto-Detection (v2.24.0)

Automatic task type detection for Ralph Loop optimization.

**Default behavior:** Task type detection runs automatically in loop mode:
- **Implementation tasks** (implement/refactor/fix/add/create/build/develop) -> **Auto-enable Ralph Loop**
- **Research tasks** (research/analyze/document/explore/investigate/study/review) -> **Auto-disable Ralph Loop**
- Detection logged to `.evidence/ralph_auto_detection.md` with timestamp and reasoning

**Override flags:**
- `--ralph-enable`: Force enable Ralph Loop (bypass auto-detection)
- `--ralph-disable`: Force disable Ralph Loop (bypass auto-detection)

**Examples:**
```bash
# Auto-detect (recommended)
/code "implement user authentication"
# -> Auto-enables Ralph Loop (implementation task detected)

/code "research authentication patterns"
# -> Auto-disables Ralph Loop (research task detected)

# Manual override
/code "analyze existing code" --ralph-enable
# -> Force enable despite "analyze" keyword

/code "fix critical bug" --ralph-disable
# -> Force disable for supervised debugging
```

## Manual vs Automatic Detection: When to Use Each

**Summary:**
- **Automatic detection (default)**: Let the system analyze your query and choose the optimal mode
- **Manual override**: Use flags when you know better than the auto-detection

### Automatic Detection Mode (Default)

**When to use:**
- First time working on a feature
- Uncertain about task complexity
- Want system guidance on execution strategy

**How it works:**
The system analyzes your query for task type keywords:

**Implementation task keywords** (auto-enables Ralph Loop):
- `implement`, `refactor`, `fix`, `add`, `create`, `build`, `develop`

**Research task keywords** (auto-disables Ralph Loop):
- `research`, `analyze`, `document`, `explore`, `investigate`, `study`, `review`

**Detection behavior:**
- Runs automatically in loop mode (no additional flags needed)
- Logs detection result to `.evidence/ralph_auto_detection.md`
- Provides confidence score (0.0-1.0) and reasoning
- Falls back to sensible defaults when keywords are ambiguous

**Examples of auto-detection in action:**
```bash
# Auto-detects as implementation -> enables Ralph Loop
/code "implement user authentication"

# Auto-detects as research -> disables Ralph Loop
/code "research authentication patterns"

# Ambiguous query -> uses keyword frequency and context
/code "fix authentication"
# -> "fix" is implementation keyword -> enables Ralph Loop
```

### Manual Override Mode

**When to use manual override:**

1. **Force enable Ralph Loop** (`--ralph-enable`):
   - You're doing research but want autonomous iteration anyway
   - Query contains research keywords but is actually implementation-heavy
   - You know the task is repetitive and suitable for Ralph Loop

   Example:
   ```bash
   # "analyze" is research keyword, but this is actually implementation
   /code "analyze existing code and add tests" --ralph-enable
   ```

2. **Force disable Ralph Loop** (`--ralph-disable`):
   - You're implementing but need close supervision
   - Debugging critical bugs where human oversight is essential
   - Feature is experimental or high-risk

   Example:
   ```bash
   # "implement" is implementation keyword, but this needs supervision
   /code "implement critical security fix" --ralph-disable
   ```

3. **Override precedence**:
   - Manual flags (`--ralph-enable`/`--ralph-disable`) ALWAYS override auto-detection
   - No need to remove keywords from your query
   - Flags are the final decision, regardless of detection confidence

### Decision Tree: Manual or Auto?

```
Start: Loop mode is default (use --no-loop to disable)
  |
  +-> Are you unsure which mode fits best?
  |    +-> Use AUTO (default, no flags needed)
  |
  +-> Does your query clearly indicate the task type?
  |    +-> Yes -> Use AUTO (let system detect)
  |    +-> No -> Use AUTO (system handles ambiguity)
  |
  +-> Do you disagree with auto-detection?
  |    +-> Yes -> Use MANUAL OVERRIDE (--ralph-enable or --ralph-disable)
  |    +-> No -> Use AUTO (trust the detection)
  |
  +-> Is this a critical/sensitive task?
       +-> Yes -> Use MANUAL (--ralph-disable for supervision)
       +-> No -> Use AUTO (default behavior)
```

### Best Practices

1. **Default to auto-detection**: It's optimized for most cases
2. **Use manual flags sparingly**: Only when you have specific reasons
3. **Trust but verify**: Check `.evidence/ralph_auto_detection.md` to see why a decision was made
4. **Provide clear queries**: More specific keywords = better auto-detection
5. **For research that's actually implementation**: Use `--ralph-enable` with implementation keywords in your query

**Implementation:**
- Uses loop-core infrastructure (`loop_policy`, `state_manager`, etc.)
- Per-terminal state isolation (each terminal gets own state directory)
- Practical verification: checks plan requirements against completed tasks
- Chat concern extraction: detects blockers/issues in conversation history

**Configuration:**
- Expects `.claude/loop/config.yaml` for exit policy settings
- See `/loop-code` skill for full configuration options

**Difference from single-task mode:**
- **Loop mode** (default): `/code plan.md` -> Multi-task plan, autonomous iteration
- **Single-task** (`--no-loop`): `/code <task description>` -> One feature, DONE

**Examples:**
```bash
# Multi-task plan with autonomous loop (default)
/code plan.md

# Single task (opt-out with --no-loop)
/code "Add user authentication" --no-loop

# Both achieve same quality, but loop mode handles orchestration
```
