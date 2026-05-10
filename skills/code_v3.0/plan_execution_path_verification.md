# Plan: Execution Path Verification for /code PLAN Phase

## Overview

Add mandatory execution path verification to Phase 4 (PLAN) of the `/code` skill to catch structural bugs during planning instead of after implementation. This prevents issues like unreachable code branches and lifecycle gaps that were discovered in GAV Phase 2.

**Why**: Current planning documents data flow but doesn't verify execution paths. Two recent bugs would have been caught earlier:
1. Lifecycle bug: `sys.exit(0)` at line 239 made validation unreachable
2. False positive bug: "blocked" marker appeared in injected context itself

**What**: Add "Step 4.5: Execution Path Verification" to PLAN phase for non-trivial flows

## Architecture

**Single module change** — Update `/code` skill SKILL.md, Phase 4 section

**Location**: Insert between "Pre-mortem step" and "Exit criteria" in Phase 4 (PLAN)

**New step structure**:
```
Step 4.5: Execution Path Verification (MANDATORY for non-linear flows)
├─ Trigger: Non-linear control flow detected
├─ Method: Manual TRACE of main() or equivalent entry point
├─ Checks: 4 verification types
└─ Output: Either PASS (proceed) or FINDINGS (fix plan first)
```

**Scope**:
- Mandatory for: Multi-turn lifecycles, state machines, hooks, handlers
- Optional for: Linear single-path functions (< 20 lines)
- Skipped for: Pure data transformations (no control flow)

## Data Flow

### Before This Change

```
PLAN Phase:
1. Check for existing plan
2. Create plan (7 sections)
3. Run pre-mortem (5 minutes)
4. Exit → TDD phase
   ↓
Implementation happens
   ↓
Testing/TRACE finds bugs
   ↓
Fix and re-test
```

### After This Change

```
PLAN Phase:
1. Check for existing plan
2. Create plan (7 sections)
3. Run pre-mortem (5 minutes)
4. **NEW** Execution Path Verification
   ├─ Detect: Non-linear flow?
   └─ Yes: TRACE main() execution
       ├─ Verify: Each branch reachable?
       ├─ Verify: No early exits skip logic?
       ├─ Verify: State preserved across turns?
       └─ Verify: Markers don't conflict with context?
   ├─ Issues found?
   │   ├─ Yes: Fix plan first → re-verify
   │   └─ No: Exit → TDD phase
   ↓
Implementation happens
   ↓
Testing/TRACE finds fewer bugs (structural issues caught earlier)
```

### Integration Point

**File**: `$CLAUDE_ROOT/skills\code\SKILL.md`
**Section**: Phase 4: PLAN — Design Solution
**Insert location**: After line 351 (after pre-mortem step), before line 357 (Exit criteria)

## Error Handling

**When verification finds issues**:

1. **HALT planning** — Don't proceed to TDD with structural bugs in plan
2. **Document findings** — List each issue with:
   - Issue type (unreachable branch, early exit, lifecycle gap, marker conflict)
   - Location (line numbers, function names)
   - Impact (what breaks)
   - Fix (how to update plan)
3. **Fix plan** — Update plan.md to address findings
4. **Re-verify** — Run execution path verification again
5. **PASS → proceed** — Only after all findings resolved

**Exit criteria**:
- All verification checks pass OR
- Verification not applicable (linear flow) AND
- Plan updated with any fixes

## Test Strategy

### Unit Tests (verification logic)

1. **Happy path** — Linear flow skips verification gracefully
2. **Non-linear flow detected** — Multi-turn lifecycle triggers verification
3. **Unreachable branch detected** — sys.exit() before critical code caught
4. **Early exit detected** — return/exit skips validation logic caught
5. **Lifecycle gap detected** — Missing state persistence caught
6. **Marker conflict detected** — Marker string in injected context caught
7. **Fix and re-verify** — Plan update passes verification on retry

### Integration Tests (workflow)

1. **GAV Phase 2 scenario** — Lifecycle bug caught in planning (regression test)
2. **Hook development** — Multi-turn hook lifecycle verified
3. **State machine** — State transitions verified
4. **Linear function** — Verification skipped, no false positives

### Manual Verification

1. **Create test plan** with intentional bug (unreachable branch)
2. **Run /code** PLAN phase
3. **Verify bug caught** before implementation starts
4. **Fix plan**
5. **Verify re-verification passes**
6. **Proceed to TDD**

## Standards Compliance

**Follows /code skill conventions**:
- **Mandatory verification** — Like TRACE is mandatory for code changes
- **Early detection** — Complements TRACE phase (planning vs implementation)
- **Evidence-based** — Line numbers cited for findings
- **Best-effort error handling** — Verification failures don't crash skill

**Type hints**: Use `dict | None` return types (Python 2025+ standards)

**Documentation**: Markdown with clear sections (Overview, Architecture, Data Flow, etc.)

**No breaking changes** — Adds verification, doesn't remove existing steps

## Ramifications

### Backwards Compatibility

- ✅ **Existing plans still work** — No changes to plan structure
- ✅ **Existing workflow unchanged** — Verification is additive, not replacing
- ✅ **Fast mode respected** — Can skip for trivial linear flows

### Performance Impact

- **Planning phase**: +2-5 minutes for non-linear flows
- **Overall build**: -10-30 minutes (bugs caught earlier = less rework)
- **Net benefit**: Faster due to fewer implementation cycles

### User Experience

**Before**: Implement → test → find bug → fix → re-test
**After**: Plan → verify → fix plan → implement → test (fewer bugs)

**Learning curve**: Low — verification uses existing TRACE methodology users already know

### Migration Path

1. **Update SKILL.md** — Add verification step to Phase 4
2. **Update documentation** — Add examples to reference/
3. **Test with GAV Phase 2** — Verify lifecycle bug would be caught
4. **Roll out gradually** — No flag needed, verification is non-blocking for linear flows

## Pre-mortem Analysis

**Failure Mode #1**: False positives on valid plans
- **Root cause**: Verification too strict, flags benign patterns
- **Prevention**: Verification only mandatory for non-linear flows, optional for simple linear code
- **Test case**: Test #7 (linear function skips verification)

**Failure Mode #2**: Verification crashes /code skill
- **Root cause**: Unhandled exception during TRACE
- **Prevention**: Wrap verification in try/except, treat failures as "skip with warning"
- **Test case**: Test #8 (malformed plan handled gracefully)

**Failure Mode #3**: Performance regression on every plan
- **Root cause**: Verification runs on all plans including trivial ones
- **Prevention**: Early exit for linear flows (< 20 lines, single path)
- **Observability**: Monitor PLAN phase duration, should add < 5 minutes for non-trivial plans

**Failure Mode #4**: Teams bypass verification
- **Root cause**: Perceived as overhead without value
- **Prevention**: Document real bugs caught (GAV Phase 2 case study), integrate with TRACE methodology
- **Test case**: None (cultural adoption, not technical)

## Tasks

1. **Update SKILL.md** — Add "Step 4.5: Execution Path Verification" section to Phase 4
2. **Create reference example** — Add `references/execution_path_verification_example.md` showing GAV Phase 2 bug caught
3. **Test with GAV Phase 2** — Verify lifecycle bug would be caught during planning
4. **Document integration** — Update `flows/feature.md` with verification step
5. **Run ruff** — Code quality check on updated SKILL.md
6. **Update version** — Bump to v2.19.0 in SKILL.md header

## Success Criteria

- [ ] SKILL.md updated with verification step
- [ ] Reference example shows GAV Phase 2 lifecycle bug caught
- [ ] Test cases pass (unit + integration)
- [ ] Ruff checks pass
- [ ] Version bumped to v2.19.0
- [ ] Documentation updated (flows/feature.md)
- [ ] GAV Phase 2 regression test passes

## Risk Assessment

**Low risk** change:
- Additive only (no removal)
- Skips gracefully for simple flows
- Uses proven TRACE methodology
- Complements existing phases (doesn't replace)

**Mitigations**:
- Early exit for linear flows (performance)
- Best-effort error handling (no crashes)
- Clear documentation (when to run, how to interpret findings)

## Timeline

**Planning**: 30 minutes (this document)
**Implementation**: 1-2 hours (update SKILL.md, create examples)
**Testing**: 1 hour (unit + integration tests)
**Documentation**: 30 minutes (flows/feature.md updates)
**Total**: 3-4 hours

## References

- **GAV Phase 2 bugs**: `$CLAUDE_ROOT/hooks\plan_gav_phase2_drift_detection.md`
- **TRACE methodology**: `$CLAUDE_ROOT/skills\trace\templates\TRACE_METHODOLOGY.md`
- **Current /code skill**: `$CLAUDE_ROOT/skills\code\SKILL.md`
- **Feature flow**: `$CLAUDE_ROOT/skills\code\flows\feature.md`
