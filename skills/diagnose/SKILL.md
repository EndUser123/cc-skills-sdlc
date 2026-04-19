---
name: diagnose
description: Structured diagnostic protocol enforcing systematic hypothesis testing when investigating issues.
version: "1.0.0"
status: "stable"
category: analysis
---

# Structured Diagnostic Protocol

## AID Integration (v1.1.0)

**Bug hunting assistance via AI Distiller (AID):**

```bash
# Systematically search for bugs
aid <path> --ai-action prompt-for-bug-hunting
```

**AID `prompt-for-bug-hunting` provides:**
- **Quality Analysis**: Code quality issues that may indicate bugs
- **Edge Case Detection**: Boundary conditions, null handling, error paths
- **Logical Inconsistencies**: Contradictory logic, unreachable code
- **Resource Management**: Memory leaks, file handle leaks, connection leaks
- **Concurrency Issues**: Race conditions, deadlocks, thread safety

**When to use AID for diagnosis:**
- Pre-mortem analysis (investigate before incident)
- Legacy code bug discovery (systematic pattern search)
- Test gap analysis (find missing test scenarios)
- Quality gate for code changes (bug regression check)

**Integration**: Run AID bug hunting before hypothesis generation to inform H1-H3 list.

---

**When to use**:
- Investigating bugs, errors, or unexpected behavior
- Debugging test failures or performance issues
- Analyzing system failures or race conditions

**When NOT to use**:
- Simple fixes (obvious typo, missing import)
- Feature implementation (use /plan-workflow instead)
- Code exploration without investigation intent

---

## How It Works

`/diagnose` enforces the Structured Diagnostic Protocol from MEMORY.md:

1. **List all hypotheses upfront** (minimum 3)
2. **For EACH hypothesis**: design disconfirming test → run test → mark RULED OUT/CONFIRMED
3. **Only proceed** when all but one ruled out OR one confirmed
4. **Document** the diagnostic path

---

## Template

```markdown
## Diagnostic Investigation

**Issue**: [brief problem description]

**Hypotheses**:
H1: [description]
H2: [description]
H3: [description]

**Test Results**:
H1: Test `[command]` → Result `[output]` → RULED OUT/CONFIRMED
H2: Test `[command]` → Result `[output]` → RULED OUT/CONFIRMED
H3: Test `[command]` → Result `[output]` → RULED OUT/CONFIRMED

**Conclusion**: H[confirmed] is the root cause
**Next Step**: [proposed fix]
```

---

## Examples

### Example 1: Pytest Hanging

```markdown
## Diagnostic Investigation

**Issue**: pytest hangs indefinitely when running test suite

**Hypotheses**:
H1: pytest-testmon plugin interference with test collection
H2: Missing tot_tracer module causing import hang
H3: Hook interference during test collection
H4: Recursive test imports causing circular dependency

**Test Results**:
H1: Test `pytest tests/ -v -p no:testmon` → Tests complete in 0.15s → RULED OUT
H2: Test `grep -r "tot_tracer" tests/` → No matches → RULED OUT
H3: Test `mv .claude/hooks .claude/hooks.bak && pytest tests/` → Still hangs → RULED OUT
H4: Test `pytest --collect-only` → Hangs at same point → CONFIRMED

**Conclusion**: H4 is the root cause - test collection has circular import
**Next Step**: Analyze test import graph with `pytest --collect-only --verbose`
```

### Example 2: Async Function Race Condition

```markdown
## Diagnostic Investigation

**Issue**: Intermittent KeyError in async handler

**Hypotheses**:
H1: Multiple tasks accessing shared dict without lock
H2: Event loop order causing premature deletion
H3: Exception handler swallowing race condition error
H4: Task cancellation during dict access

**Test Results**:
H1: Test `add locks to dict access` → Still fails → RULED OUT
H2: Test `add logging before deletion` → KeyError happens before delete → RULED OUT
H3: Test `remove try/except wrapper` → RuntimeError appears → CONFIRMED
H4: N/A (H3 confirmed)

**Conclusion**: H3 - Exception wrapper was hiding RuntimeError, manifesting as KeyError
**Next Step**: Remove exception wrapper, let RuntimeError propagate for proper stack trace
```

---

## Protocol Enforcement

This skill REQUIRES:

- [ ] **3+ hypotheses listed** before any testing begins
- [ ] **Each hypothesis has test command** with exact syntax
- [ ] **Each hypothesis has result** with actual output (not "should work")
- [ ] **Each hypothesis marked** RULED OUT or CONFIRMED
- [ ] **Conclusion explicitly states** which hypothesis won
- [ ] **Next step proposed** ONLY after conclusion reached

---

## Integration with MEMORY.md Protocols

This skill enforces these protocols from MEMORY.md:

### Verification First Protocol
- Claim → Test → Document (no claims without testing)

### Solution Proposal Gate
- Root cause identified? ✓ (hypothesis testing)
- Alternative hypotheses ruled out? ✓ (diagnostic structure)
- Proposed fix tested? ✓ (next step test)

### Structured Diagnostic Protocol
- 3+ hypotheses upfront ✓
- Systematic testing for each ✓
- Document path ✓

---

## Output Format

Required sections (in order):

1. **Diagnostic Investigation** (heading)
2. **Issue** (brief problem statement)
3. **Hypotheses** (H1, H2, H3... with descriptions)
4. **Test Results** (each with command, output, conclusion)
5. **Conclusion** (which hypothesis confirmed)
6. **Next Step** (proposed fix or next test)

---

## Prohibited Behaviors

DO NOT:
- Jump to solution before listing all hypotheses
- Test only one hypothesis (need 3+)
- Claim "probably" or "likely" without test output
- Skip documenting the diagnostic path
- Accept first plausible explanation

---

## Quick Reference

| Violation | Detection | Correction |
|-----------|-----------|------------|
| Single hypothesis | Only H1 listed | Add H2, H3 upfront |
| Untested claim | "Probably caused by X" | Show test output |
| Missing conclusion | Tests but no winner | State which hypothesis confirmed |
| Premature fix | "Let's try X" before tests | Complete protocol first |

---

**Version**: 1.0.0
**Enforcement**: Stop hook checks for violations
