# PARALLEL Delegation Patterns

## PARALLEL FIRST Rule

**If tasks are independent, launch ALL subagents in parallel.**

| Step | Decompose When | Example |
|------|----------------|---------|
| **DISCOVER** | Multiple modules/directories to search | 1 agent per top-level module |
| **RED** | Multiple test cases | 1 agent per test case |
| **GREEN** | Implementation spans multiple files | 1 agent per file |
| **REFACTOR** | Multiple independent cleanups | 1 agent per cleanup task |

**Decision tree:**
```
Can the task be split into independent pieces?
  YES -> How many pieces? -> Launch that many agents in parallel
  NO  -> Single agent for this step
```

**No upper limit** on parallel agents. If tasks are independent, launch all of them.

---

## RED Phase: Write Failing Test (PARALLEL)

**Current action:** Launching PARALLEL `tdd-test-writer` subagents...

**PARALLEL TEST WRITING STRATEGY:**
1. **Parse feature into N test cases** - Break down requirements into individual testable scenarios
2. **Launch N parallel subagents** - ONE `Task(subagent_type="tdd-test-writer")` call PER test case
3. **Each subagent:**
   - Writes ONE test function/case
   - Runs pytest to verify it FAILS
   - Returns test path and failure output
4. **Collect results** - Aggregate all test files and failures

**Example - Launching parallel test writers:**
```python
# IN ONE MESSAGE, SEND MULTIPLE PARALLEL Task CALLS:
Task(description="Write test 1", subagent_type="tdd-test-writer", prompt="Write test for feature X case 1...")
Task(description="Write test 2", subagent_type="tdd-test-writer", prompt="Write test for feature X case 2...")
Task(description="Write test 3", subagent_type="tdd-test-writer", prompt="Write test for feature X case 3...")
```

**You MUST:**
- Describe the feature requirement clearly
- Break down into individual test cases
- Launch ONE Task call PER test case
- Let each test writer write ONLY their test

**Do NOT proceed to GREEN until:**
- All test files exist
- All tests have been run
- All tests FAIL (this confirms we're testing the right things)

---

## GREEN Phase: Make It Pass (PARALLEL)

**Current action:** Launching PARALLEL `tdd-implementer` subagents...

**PARALLEL IMPLEMENTATION STRATEGY:**
1. **Parse failing tests into N implementation tasks** - Break down by file, method, or feature
2. **Launch N parallel subagents** - ONE `Task(subagent_type="tdd-implementer")` call PER task
3. **Each subagent:**
   - Reads their assigned failing test(s)
   - Writes minimal code to make them pass
   - Runs pytest to verify the test PASSES
   - Returns implementation summary
4. **Collect results** - Aggregate all implementations

**Example - Launching parallel implementers:**
```python
# IN ONE MESSAGE, SEND MULTIPLE PARALLEL Task CALLS:
Task(description="Implement cache class", subagent_type="tdd-implementer", prompt="Implement _failed_providers cache...")
Task(description="Implement mark failed", subagent_type="tdd-implementer", prompt="Implement _mark_provider_as_failed...")
Task(description="Implement check TTL", subagent_type="tdd-implementer", prompt="Implement _is_provider_expired...")
Task(description="Integrate failover", subagent_type="tdd-implementer", prompt="Wire up failover in execute_research...")
```

**You MUST:**
- Parse failing tests into independent implementation tasks
- Launch ONE Task call PER implementation task
- Write ONLY what each test requires
- No extra features
- No refactoring yet

**Do NOT proceed to REFACTOR until:**
- All implementations exist
- All tests have been run
- All tests PASS

---

## REFACTOR Phase: Improve (PARALLEL)

**Current action:** Launching PARALLEL `tdd-refactorer` subagents...

**PARALLEL REFACTORING STRATEGY:**
1. **Parse code into N refactoring tasks** - Break down by file, complexity, or cleanup category
2. **Launch N parallel subagents** - ONE `Task(subagent_type="tdd-refactorer")` call PER task
3. **Each subagent:**
   - Evaluates their assigned code section
   - Applies improvements if beneficial (type hints, docstrings, simplification)
   - Runs pytest to verify tests still pass
   - Returns summary or "no refactoring needed"
4. **Collect results** - Aggregate all improvements

**Example - Launching parallel refactorers:**
```python
# IN ONE MESSAGE, SEND MULTIPLE PARALLEL Task CALLS:
Task(description="Add type hints", subagent_type="tdd-refactorer", prompt="Add type hints to cache.py...")
Task(description="Add docstrings", subagent_type="tdd-refactorer", prompt="Add docstrings to failover methods...")
Task(description="Simplify logic", subagent_type="tdd-refactorer", prompt="Simplify TTL expiration logic...")
Task(description="Extract helpers", subagent_type="tdd-refactorer", prompt="Extract duplicate code to helpers...")
```

**You MUST:**
- Parse code into independent refactoring tasks
- Launch ONE Task call PER refactoring task
- Keep tests passing
- Only change code structure, not behavior
- Run tests after each change

**Do NOT mark complete until:**
- All code sections have been evaluated
- All tests still pass
- Summary provided for each section

---

## End-to-End Example

```bash
# New feature
User: "implement search by channel name"

# Skill responds:
# RED PHASE: Launching PARALLEL tdd-test-writer subagents...
Task(subagent_type="tdd-test-writer", prompt="Write test for search by channel name - happy path", description="Happy path test")
Task(subagent_type="tdd-test-writer", prompt="Write test for search by channel name - channel not found", description="Not found test")
Task(subagent_type="tdd-test-writer", prompt="Write test for search by channel name - empty query", description="Empty query test")

# After tests fail:
# GREEN PHASE: Launching PARALLEL tdd-implementer subagents...
Task(subagent_type="tdd-implementer", prompt="Implement search_by_channel_name to pass tests", description="Implement search")

# After tests pass:
# REFACTOR PHASE: Launching PARALLEL tdd-refactorer subagents...
Task(subagent_type="tdd-refactorer", prompt="Add type hints to search module", description="Add type hints")
Task(subagent_type="tdd-refactorer", prompt="Add docstrings to search functions", description="Add docstrings")
```
