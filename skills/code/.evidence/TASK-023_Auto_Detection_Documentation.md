# TASK-023 Auto-Detection Logic Documentation Evidence

**Task**: Clarify auto-detection logic (manual vs auto)
**Date**: 2026-03-16
**Status**: ✅ COMPLETE

---

## Acceptance Criteria (from plan.md)

From TASK-023:
- Document manual trigger conditions (user flags)
- Document auto-detection triggers (keywords, patterns)
- Explain override behavior (--ralph-enable/--ralph-disable)
- Ensure clear distinction between manual and auto modes
- File: `P:/.claude/skills/code/SKILL.md`
- Points: 2 (Simple)

---

## Problem Statement

**Gap Identified**: The Ralph Loop auto-detection feature (v2.24.0) had basic documentation, but lacked clear guidance on:
1. When to use manual vs automatic mode
2. How override flags interact with auto-detection
3. Decision-making criteria for choosing manual override
4. Best practices for optimal usage

**Questions to Answer**:
1. What triggers automatic detection?
2. When should I manually override?
3. What are the keyword patterns?
4. How do flags affect auto-detection?

---

## Solution: Comprehensive Documentation

### Changes Made

**File**: `P:\.claude\skills\code\SKILL.md`

**Added Section**: "Manual vs Automatic Detection: When to Use Each"

**Location**: After line 105 (after auto-detection examples), before "Implementation:" section

**Content Added**:

#### 1. Automatic Detection Mode (Default)

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
- Runs automatically when `--loop` is passed (no additional flags needed)
- Logs detection result to `.evidence/ralph_auto_detection.md`
- Provides confidence score (0.0-1.0) and reasoning
- Falls back to sensible defaults when keywords are ambiguous

**Examples of auto-detection in action:**
```bash
# Auto-detects as implementation → enables Ralph Loop
/code "implement user authentication" --loop

# Auto-detects as research → disables Ralph Loop
/code "research authentication patterns" --loop

# Ambiguous query → uses keyword frequency and context
/code "fix authentication" --loop
# → "fix" is implementation keyword → enables Ralph Loop
```

#### 2. Manual Override Mode

**When to use manual override:**

1. **Force enable Ralph Loop** (`--ralph-enable`):
   - You're doing research but want autonomous iteration anyway
   - Query contains research keywords but is actually implementation-heavy
   - You know the task is repetitive and suitable for Ralph Loop

   Example:
   ```bash
   # "analyze" is research keyword, but this is actually implementation
   /code "analyze existing code and add tests" --loop --ralph-enable
   ```

2. **Force disable Ralph Loop** (`--ralph-disable`):
   - You're implementing but need close supervision
   - Debugging critical bugs where human oversight is essential
   - Feature is experimental or high-risk

   Example:
   ```bash
   # "implement" is implementation keyword, but this needs supervision
   /code "implement critical security fix" --loop --ralph-disable
   ```

3. **Override precedence**:
   - Manual flags (`--ralph-enable`/`--ralph-disable`) ALWAYS override auto-detection
   - No need to remove keywords from your query
   - Flags are the final decision, regardless of detection confidence

#### 3. Decision Tree: Manual or Auto?

```
Start: You want to use --loop mode
  │
  ├─→ Are you unsure which mode fits best?
  │    └─→ Use AUTO (default, no flags needed)
  │
  ├─→ Does your query clearly indicate the task type?
  │    ├─→ Yes → Use AUTO (let system detect)
  │    └─→ No → Use AUTO (system handles ambiguity)
  │
  ├─→ Do you disagree with auto-detection?
  │    ├─→ Yes → Use MANUAL OVERRIDE (--ralph-enable or --ralph-disable)
  │    └─→ No → Use AUTO (trust the detection)
  │
  └─→ Is this a critical/sensitive task?
       ├─→ Yes → Use MANUAL (--ralph-disable for supervision)
       └─→ No → Use AUTO (default behavior)
```

#### 4. Best Practices

1. **Default to auto-detection**: It's optimized for most cases
2. **Use manual flags sparingly**: Only when you have specific reasons
3. **Trust but verify**: Check `.evidence/ralph_auto_detection.md` to see why a decision was made
4. **Provide clear queries**: More specific keywords = better auto-detection
5. **For research that's actually implementation**: Use `--ralph-enable` with implementation keywords in your query

---

## Verification

**Verification Method**: Documentation review

**Verification Results**:
- ✅ Manual trigger conditions documented (--ralph-enable, --ralph-disable flags)
- ✅ Auto-detection triggers documented (7 implementation keywords, 7 research keywords)
- ✅ Override behavior explained (flags ALWAYS override auto-detection)
- ✅ Clear distinction between manual and auto modes (decision tree + best practices)
- ✅ When-to-use guidance for each mode (use cases + examples)
- ✅ Decision tree for choosing manual vs auto
- ✅ Best practices for optimal usage

---

## Benefits

1. **Clarity**: Users now understand when to use manual vs automatic mode
2. **Confidence**: Decision tree provides clear guidance for edge cases
3. **Best practices**: Documented patterns for common scenarios
4. **Examples**: Concrete examples for each mode and override scenario
5. **Troubleshooting**: How to verify auto-detection decisions (check evidence log)

---

## Testing Notes

**Test Required**: Verify documentation is clear and comprehensive
**Test Command**: Manual review (no automated test needed for documentation)

**Expected Result**: Users understand:
- When to use automatic detection (default, most cases)
- When to use manual override (specific use cases)
- How override flags work (always override auto-detection)
- How to choose between modes (decision tree)

---

## Completion Checklist

- [x] Read plan.md TASK-023 requirements
- [x] Analyze existing auto-detection documentation (lines 77-115)
- [x] Identify gaps (manual vs auto guidance, override behavior, decision criteria)
- [x] Add comprehensive section "Manual vs Automatic Detection: When to Use Each"
- [x] Document manual trigger conditions (--ralph-enable, --ralph-disable)
- [x] Document auto-detection triggers (keyword patterns)
- [x] Explain override behavior (flags always override)
- [x] Add decision tree for choosing manual vs auto
- [x] Add best practices section
- [x] Create evidence file for TASK-023

---

**Acceptance Criteria Status**:
- ✅ Document manual trigger conditions (user flags) (COMPLETE)
- ✅ Document auto-detection triggers (keywords, patterns) (COMPLETE)
- ✅ Explain override behavior (--ralph-enable/--ralph-disable) (COMPLETE)
- ✅ Ensure clear distinction between manual and auto modes (COMPLETE)
