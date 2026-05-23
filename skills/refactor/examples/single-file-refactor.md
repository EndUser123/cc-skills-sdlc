# Example: Single File Refactor

Refactor a single file with the full 15-step workflow.

## User Request

```
/refactor src/providers/base_provider.py
```

## Workflow Execution

### DISCOVER
1. Scan `base_provider.py` for hotspots via Grep (TODO, FIXME, large functions)
2. Launch 8 agents targeting this single file, staggered 30s apart
3. Each agent writes findings to `{artifacts_dir}/base_provider/refactor/findings-{agent}.json`

### DEDUPLICATE
```bash
python scripts/deduplicate.py P://.claude/.artifacts base_provider
```
Output: `{artifacts_dir}/base_provider/refactor/deduplicated.json`

### CLASSIFY_DEBT
Findings labeled: `code_debt` (duplication), `test_debt` (missing edge cases), etc.

### PRIORITIZE
Findings sorted: P0 bugs first, then P1 error handling, P2 DRY, P3 conventions.

### PLAN
```bash
python scripts/refactor_plan.py deduplicated.json base_provider {session_id}
```
Produces tiny-commit breakdown with explicit "Out of Scope" section.

### RED PHASE
Create `tests/test_base_provider.py` with characterization tests.
Verify tests FAIL before any production code changes.
Git tag: `refactor/red-base_provider-{timestamp}`

### ADVERSARIAL REVIEW
Stress-test characterization tests via `adversarial-review` (8 perspectives).

### REFACTOR (GREEN)
Apply changes using AST-based refactoring (LibCST).
After each file edit, run LSP diagnostics.
Verify characterization tests PASS.
Git tag: `refactor/green-base_provider-{timestamp}`

### REGRESSION
```bash
pytest tests/ -v
```

### DELETION METRIC
```
| Dimension        | Before | After | Delta |
|------------------|--------|-------|-------|
| Naming           | 5      | 8     | +3    |
| Simplicity       | 4      | 7     | +3    |
| Coupling         | 6      | 9     | +3    |
```
Lines removed - lines added = +12 (net simplification)
