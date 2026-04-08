# Phase 6: TEST - Detailed Instructions

## Test Hierarchy

1. **Unit Tests**: Per-task TDD tests (already written in Phase 5)
   - Verify individual functions and methods work correctly
   - Already passing from TDD phase

2. **Integration Tests**: Component interaction tests
   - Verify modules work together correctly
   - Test data flow between components
   - Validate external integrations (APIs, databases, services)

3. **Regression Tests**: Protect against breaking changes
   - Verify existing functionality still works
   - Catch unintended side effects
   - Run full test suite for affected modules

## Validation Protocol

1. **Run unit tests**: Already passing from TDD phase (quick verification)
2. **Run integration tests**:
   ```bash
   pytest tests/integration/ -v
   # Or project-specific integration test command
   ```
3. **Run regression tests**:
   ```bash
   pytest tests/ -v --cov=<module>
   # Or project-specific full test command
   ```

## Step 6.5: Test Coverage Analysis

After the test suite passes, run test quality analysis:

```
Agent(subagent_type="pr-review-toolkit:pr-test-analyzer", description="Analyze test coverage and quality for <target>")
```

**What this does:**
- Evaluates test coverage completeness
- Identifies untested code paths and edge cases
- Checks test quality (assertions, fixtures, mocking)
- Reports coverage gaps with confidence scores
- Applies 80+ confidence threshold to filter findings

**Integration notes:**
- Run AFTER all tests pass
- Run BEFORE proceeding to TRACE phase
- If critical gaps found, add tests before TRACE
- Complementary to TDD phase verification

## Exit Criteria
- All unit tests pass (from TDD phase)
- All integration tests pass
- All regression tests pass
- No test coverage regressions
- Test quality analysis complete (80+ confidence threshold)

**Parallel execution**: Can run concurrent with AUDIT (Phase 7). Both phases must pass before proceeding to TRACE.
