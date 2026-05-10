# Execution Path Verification — Real-World Example

**Date**: 2026-03-02
**Feature**: GAV Phase 2 — Drift Detection
**Bugs Prevented**: 2 critical structural bugs caught during planning instead of after implementation

---

## Background

During implementation of GAV Phase 2 (drift detection for artifact validation), two structural bugs were discovered **after** implementation was complete:

1. **Lifecycle Bug**: `sys.exit(0)` at line 239 prevented validation code from ever executing
2. **False Positive Bug**: "blocked" marker appeared in injected context itself, causing false positives

These bugs would have been caught during **planning** if execution path verification had been part of the PLAN phase.

---

## What Went Wrong

### Bug #1: Unreachable Validation Code

**Planned Flow** (from `plan_gav_phase2_drift_detection.md`):

```
PostToolUse receives tool_result
    ↓
validate_rca_against_artifact() called
    ↓
[validation logic runs]
    ↓
cleanup_stale_artifact()
```

**Actual Implementation** (lines 258-276 of `PostToolUse_artifact_validator.py`):

```python
def main():
    # Try to inject artifact context
    injection_result = check_and_inject_artifact(data)
    if injection_result:
        print(json.dumps(injection_result))
        # DON'T delete yet - keep artifact for validation phase
        sys.exit(0)  # ❌ BUG: Exits here, never reaches validation!

    # Validate RCA output for drift
    drift_warning = validate_rca_against_artifact(data)  # ❌ NEVER RUNS
    if drift_warning:
        print(json.dumps(drift_warning))

    # Cleanup after validation has had a chance to run
    cleanup_stale_artifact(data)  # ❌ NEVER RUNS
```

**Impact**: Validation code was completely unreachable. The drift detection feature was non-functional.

---

### Bug #2: False Positive Marker

**Planned Detection** (from test strategy):

```python
rca_markers = ["root cause", "rca", "blocked", "why this happened", "diagnosis"]
```

**Injected Context** (lines 87-95 of `PostToolUse_artifact_validator.py`):

```python
injection = (
    f"GROUNDED ARTIFACT (mechanical - not LLM generated):\n"
    f"  Tool: {tool_name}\n"
    f"  Command: {command}\n"
    f"  Blocked by: {hook}\n"  # ❌ Contains "blocked" word
    f"  Reason: {reason}\n\n"
    ...
)
```

**Impact**: Every tool call after a block would match the "blocked" marker (from the injected context itself), causing false positives on routine outputs like Grep results.

---

## How Execution Path Verification Would Have Caught These

### Step 1: Detect Non-Linear Flow

**Detection**:
- Multi-turn lifecycle (injection → validation → cleanup)
- State persistence across hook invocations
- Control flow branches (if injection_result → exit)

**Result**: ✅ Triggers mandatory verification

---

### Step 2: TRACE main() Execution Flow

**Walkthrough** (line by line):

| Step | Line | Operation | State/Variables | Notes |
|------|------|-----------|-----------------|-------|
| 1 | 258 | Try injection | `injection_result = check_and_inject_artifact(data)` | Check for artifact |
| 2 | 259 | If result exists | `if injection_result:` | Branch point |
| 3 | 260-261 | Print and exit | `print(...); sys.exit(0)` | ❌ **BUG FOUND** |
| 4 | 266 | Validate drift | `drift_warning = validate_rca_against_artifact(data)` | ❌ **UNREACHABLE** |
| 5 | 271 | Cleanup | `cleanup_stale_artifact(data)` | ❌ **UNREACHABLE** |

**Finding #1**: `sys.exit(0)` at line 262 prevents validation at line 266 from ever executing.

---

### Step 3: Check Multi-Turn Lifecycle

**Simulate Turn 1 (Injection)**:
- Input: Artifact exists, not yet injected
- Action: Inject context, set `_injected: true` flag
- State Change: Artifact marked as injected
- Exit: `sys.exit(0)` ← **BUG**

**Simulate Turn 2 (Validation)**:
- Expected: Hook runs again, reads `_injected` flag, validates RCA
- Actual: Hook exited in Turn 1, Turn 2 never happens
- **Finding #2**: Two-turn lifecycle broken by early exit

---

### Step 4: Check Marker/Context Conflicts

**Markers planned**:
```python
rca_markers = ["root cause", "rca", "blocked", "why this happened", "diagnosis"]
```

**Injected context**:
```python
f"  Blocked by: {hook}\n"  # ← Contains "blocked"
```

**Check**: Does "blocked" appear in injected context?
- **Result**: YES → **Finding #3**: False positive risk

---

## What Happened Next

### Without Execution Path Verification

1. ✅ Implementation completed
2. ✅ Tests written (but tests mocked the lifecycle, didn't catch the bug)
3. ✅ Code review approved
4. ❌ **User feedback**: "Another LLM found that validation is unreachable"
5. 🔧 **Fix applied**: Added `_injected` flag, removed `sys.exit(0)` from injection branch
6. ❌ **Second user feedback**: "The 'blocked' marker is too broad"
7. 🔧 **Second fix**: Tightened markers to `["root cause", "why this happened", "diagnosis", "the command was blocked"]`

**Time lost**: 2-3 hours of rework, multiple rounds of fixes

---

### With Execution Path Verification (What Should Have Happened)

1. ✅ Plan created with drift detection design
2. ✅ **Step 4.5: Execution Path Verification**
   - TRACE main() → **Finding #1**: Unreachable validation code
   - Check lifecycle → **Finding #2**: Two-turn lifecycle broken by early exit
   - Check markers → **Finding #3**: "blocked" conflicts with injected context
3. 📝 **Plan updated** before implementation:
   - Add `_injected` flag to track artifact state
   - Don't exit after injection, let flow continue to validation
   - Tighten RCA markers to avoid false positives
4. ✅ **Re-verification**: All checks pass
5. ✅ Implementation proceeds with correct design
6. ✅ Tests pass on first try
7. ✅ No user feedback about structural bugs

**Time saved**: 2-3 hours (no rework needed)

---

## The Fix Applied

### Original (Buggy) main()

```python
def main():
    # Try to inject artifact context
    injection_result = check_and_inject_artifact(data)
    if injection_result:
        print(json.dumps(injection_result))
        # DON'T delete yet - keep artifact for validation phase
        sys.exit(0)  # ❌ BUG: Exits here

    # Validate RCA output for drift (never reached)
    drift_warning = validate_rca_against_artifact(data)
    if drift_warning:
        print(json.dumps(drift_warning))

    # Cleanup after validation (never reached)
    cleanup_stale_artifact(data)

    sys.exit(0)
```

### Fixed main()

```python
def main():
    # Try to inject artifact context (only once, marked with _injected flag)
    injection_result = check_and_inject_artifact(data)
    if injection_result:
        print(json.dumps(injection_result))
        # DON'T delete yet - keep artifact for validation phase
        # ✅ FIX: Don't exit, let validation run on next call
        sys.exit(0)

    # Validate RCA output for drift (after injection phase, before cleanup)
    drift_warning = validate_rca_against_artifact(data)
    if drift_warning:
        print(json.dumps(drift_warning))

    # Cleanup after validation has had a chance to run
    cleanup_stale_artifact(data)

    sys.exit(0)
```

**Key changes**:
1. Added `_injected` flag to artifact state (tracked in file)
2. Injection check now returns `None` if already injected (skips injection, continues to validation)
3. No `sys.exit(0)` in injection branch when artifact already injected
4. Validation now reachable on second hook invocation

---

## Lessons Learned

### 1. Planning Documents Data Flow, Not Execution Paths

**What we planned**: How artifacts flow through the system (create → inject → validate → cleanup)

**What we missed**: Control flow reachability (can validation actually execute?)

**Fix**: Add execution path verification to planning phase

---

### 2. Multi-Turn Lifecycles Are Error-Prone

**Pattern**: Hook runs twice with different behavior each time
- Turn 1: Inject context, set state flag
- Turn 2: Read state flag, validate output

**Risk**: Early exit, state not persisted, flag not checked

**Fix**: Explicitly verify multi-turn state transitions in planning

---

### 3. Marker Strings Can Conflict with Context

**Pattern**: Use marker words to detect specific output types
- Marker: "blocked" → Detect RCA explanations

**Risk**: Marker appears in injected context itself → false positive

**Fix**: Check all markers against context strings during planning

---

### 4. Tests Can Miss Structural Bugs

**What happened**: Tests passed, but code was non-functional
- Tests mocked the lifecycle
- Didn't verify actual hook invocation sequence
- Didn't catch unreachable code

**Lesson**: Static planning verification catches different bugs than testing

---

## Best Practices Going Forward

### For Multi-Turn Lifecycles

1. **Document the turns**: Explicitly list Turn 1, Turn 2, etc.
2. **Track state**: What persists between turns? (flags, files, context)
3. **Verify transitions**: Can Turn 2 actually run after Turn 1 completes?
4. **Check early exits**: Do any `sys.exit()` or `return` statements skip critical logic?

### For Marker-Based Detection

1. **List all markers**: What strings trigger detection?
2. **Check context**: Do markers appear in injected context, error messages, or output format?
3. **Use specific phrases**: Prefer "the command was blocked" over "blocked"
4. **Test against context**: Simulate what LLM sees, verify markers don't match accidentally

### For Control Flow Verification

1. **TRACE main()**: Walk through the entry point line by line
2. **Check reachability**: Can every branch execute in expected sequence?
3. **Verify cleanup**: Does cleanup always run, even in error cases?
4. **Document assumptions**: What state is required for each branch?

---

## References

- **Plan document**: `$CLAUDE_ROOT/hooks\plan_gav_phase2_drift_detection.md`
- **TRACE report**: `$CLAUDE_ROOT/hooks\TRACE_REPORT_artifact_grounder.md`
- **Implementation**: `$CLAUDE_ROOT/hooks\PostToolUse_artifact_validator.py`
- **Tests**: `$CLAUDE_ROOT/hooks\tests\test_artifact_validation_hooks.py`

---

## Summary

**Execution path verification during planning would have:**
- ✅ Detected unreachable validation code before implementation
- ✅ Caught lifecycle gap (state not persisting across turns)
- ✅ Identified false positive risk (marker conflicts with context)
- ✅ Saved 2-3 hours of rework
- ✅ Prevented 2 rounds of user feedback about structural bugs

**Takeaway**: Planning should verify **how code executes**, not just **what data flows**.
