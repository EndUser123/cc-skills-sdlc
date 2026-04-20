# Bug-Fixing Workflow

When intent = "bug fix" (detected from "fix", "bug", "broken", "error", "crash"):

## Bug-Fixing Constraints

- **YAGNI**: Fix the actual bug, don't add "defensive" code for hypothetical scenarios
- **Data vs Logic**: If the bug is environmental (missing file, auth), recommend operational fix, not code workaround

## Workflow Adaptations

| Phase | Bug Fix Adaptation |
|-------|-------------------|
| DISCOVER | If error provided, grep for error location; if regression, suggest git bisect |
| RED | If test exists: verify test fails, proceed to GREEN; if no test: write regression test |
| GREEN | Fix ONLY the reported bug (YAGNI constraint) |
| VERIFY | Run actual command with bug reproduction |
| REGRESSION | Run related tests |
| CLOSURE | Search/Grep to ensure NO other instances remain |

## Closure Protocol

After GREEN phase for bug fixes:
```bash
# Search for similar patterns that might have the same bug
grep -r "PATTERN" --include="*.py" | grep -v "test_"
```

Report findings to ensure complete fix.

---

# Completion Format

**When completing TDD work, provide a structured summary with:**

1. **Status Summary** - What was completed (fixes, tests, refactoring)
2. **Test Results** - Actual pytest output showing pass/fail counts
3. **Next Steps** - Alphanumeric list of remaining work items

**Example completion format:**

```markdown
## TDD COMPLETE - Summary

**Findings Fixed:** X/Y (Z%)

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| QUAL-XXX | HIGH | Description | FIXED |
| PERF-XXX | CRITICAL | Description | FIXED |

**Tests Created:** N new tests

| Test File | Tests | Coverage |
|-----------|-------|----------|
| test_module.py | N | Description |

## Next Steps

1 - Fix QUAL-XXX: [specific action required]
2 - Address PERF-XXX: [specific action required]
3 - Run full regression: pytest tests/ -v
4 - Or: Proceed with deployment/usage

**Note:** This pattern provides clear next actions and completion status.
```

**Key elements:**
- **Status first** - What was accomplished
- **Evidence** - Actual test results (not "should work")
- **Next Steps** - Numbered list of specific actions
- **Or option** - Alternative paths when relevant
