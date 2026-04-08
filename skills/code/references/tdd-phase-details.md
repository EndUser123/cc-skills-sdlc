# Phase 5: TDD - Detailed Instructions

## Loop Structure

```
For each task T in plan.md:
  DISCOVER (gap loading, optional)
    1. Load test gaps from /t discovery
    2. If gap file found: display summary
    3. Proceed to RED with gap context if found
              |
  BUILDER (2 dispatches, full TDD evidence)
    1. RED:      Task(test-writer agent)
               -> confirm test FAILS
    2. GREEN+REFACTOR: Task(implementer agent)
               -> pass tests, cleanup, pass again
              |
  VERIFIER
    4. VERIFY:  Task(qa-engineer)
       Stage 1: Spec compliance
       Stage 2: Code quality
       Stage 3: Error handling
              |
         PASS? -> Mark T done
         FAIL? -> Retry from failing phase (max 3 attempts)
         3 failures -> HALT, escalate to user
```

## Dispatch Rules

1. **Test-first is mandatory** -- implementation follows failing test(s).
2. **Use `/tdd` and subagents always** -- parallel RED dispatch via `Task(subagent_type="tdd-test-writer")` is required for ALL TDD tasks.
3. **Sequential discipline** -- RED must complete before GREEN+REFACTOR verification.
4. **Verifier rule by mode** -- full/default mode uses independent verifier; fast+trivial mode allows lightweight lead-session verify with explicit evidence.
5. **Path handling is explicit** -- builder and verifier must use runtime-normalized paths.
6. **Plan compliance check** (after writing tests):
   ```bash
   python .claude/skills/code/scripts/verify_plan_compliance.py plan.md tests/test_<module>.py
   ```
   - Exit codes: 0=pass, 1=mismatch, 2=error

## Parallel RED Delegation

When multiple test cases are needed for a task:

1. **Parse feature into N test cases** -- Break down requirements into individual testable scenarios
2. **Launch N parallel subagents** -- ONE `Task(subagent_type="tdd-test-writer")` call PER test case
3. **Each subagent**: Writes ONE test function/case, runs pytest to verify it FAILS, returns test path and failure output
4. **Collect results** -- Aggregate all test files and failures

**Example:**
```python
Task(description="Write test for feature X case 1", subagent_type="tdd-test-writer", prompt="Write test for...")
Task(description="Write test for feature X case 2", subagent_type="tdd-test-writer", prompt="Write test for...")
Task(description="Write test for feature X case 3", subagent_type="tdd-test-writer", prompt="Write test for...")
```

**Do NOT proceed to GREEN until:**
- All test files exist
- All tests have been run
- All tests FAIL (confirms we're testing the right things)

## Retry Protocol

| Attempt | On Failure |
|---------|------------|
| 1st     | Re-dispatch failing phase with error context |
| 2nd     | Re-dispatch with expanded context (include surrounding code) |
| 3rd     | HALT loop, present failing task + error to user |

## Completion Guard (Anti-False-Done)

For each task, completion requires all four:
1. RED evidence: failing test output exists.
2. GREEN evidence: previously failing tests now pass.
3. REFACTOR evidence: tests still pass after refactor.
4. VERIFY evidence: independent verifier returns PASS.

If any evidence is missing, status is `BLOCKED` (not `DONE`).

## Mid-Build Escalation

| Failure Type | Trigger | Escalation Path |
|--------------|---------|-----------------|
| **Bug** | Test fails, fix is straightforward | Retry within TDD phase |
| **Architectural** | Design flaw, scope mismatch, missing requirement | HALT, return to Phase 4 (PLAN) |
| **Blocker** | External dependency, environment issue | HALT, escalate to user |

## GREEN Phase: AST-Safe Implementation

**Before marking GREEN, verify library API usage** (blocking check):
1. Run `library_checker.check_api_usage()` to extract imports
2. For each external library, use Context7 to fetch current documentation
3. Compare code usage patterns against documented examples
4. Report any deprecated APIs or incorrect usage as blocking issues
5. Only proceed to GREEN phase after fixing or acknowledging findings

**For Python structural changes**, use LibCST helpers:
```python
from packages.refactor.ast_refactor_helpers import (
    safe_transform_file,
    LibCSTTransformer,
)

class MyTransformer(LibCSTTransformer):
    def leave_Attribute(self, original_node, updated_node):
        return updated_node

success, error, count = safe_transform_file(
    "src/module.py",
    MyTransformer
)
```

**For simple changes**, use Write tool (full file replacement)

**Prohibited**:
- NEVER use `.replace()` on partial code blocks
- NEVER use regex for structural changes
- NEVER use sed for Python code

## Coverage Thresholds (VERIFY Stage 2)

- Overall: 80%+ required
- Critical code (models, services): 90%+
- Standard code (views, routes): 80%+
- Helper code (utils, logging): 60%+

## Progress Reporting

After each task completes, report:
```
Task [N/M]: <task description>
  RED: N tests written, all fail
  GREEN+REFACTOR: implemented, pass -> cleanup -> pass
  VERIFY: spec ok quality ok
```
