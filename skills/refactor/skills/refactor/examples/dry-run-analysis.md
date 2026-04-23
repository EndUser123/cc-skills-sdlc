# Example: Dry-Run Analysis (No Changes)

Analyze code without making changes. Useful for review before committing to a refactor.

## User Request

```
/refactor src/features/ --dry-run
```

## Workflow Execution

### DISCOVER
1. Scan `src/features/` directory for hotspots
2. Launch 8 agents targeting all files in the directory
3. Each agent writes findings to `{artifacts_dir}/features/refactor/findings-{agent}.json`

### DEDUPLICATE
Merge findings by file+line, assign canonical IDs (COMP-001, DRY-003, etc.)

### CLASSIFY_DEBT
Label each finding: `design_debt`, `code_debt`, `test_debt`, or `documentation_debt`

### PRIORITIZE
Sort by severity: P0 -> P1 -> P2 -> P3

### CONSTITUTIONAL FILTER
Apply SoloDevConstitutionalFilter. Enterprise patterns filtered out.

### PLAN
Create refactoring plan with tiny-commit breakdown.
Run adversarial review on the plan.

**STOP** -- No code changes made. Findings and plan saved to artifacts dir.

## Resuming Later

```
/refactor src/features/ continue
```

The `continue` flag picks up existing findings from `{artifacts_dir}/features/refactor/` and executes RED through DELETION_METRIC for all priority levels.

To force fresh discovery:

```
/refactor src/features/ --rediscover
```
