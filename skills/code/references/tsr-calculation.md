# TSR Calculation for Post-Hoc Verification

The Task Success Rate (TSR) metric is calculated from the TDD evidence ledger and used by `/verify --post-hoc` to validate implementation completeness.

## What is TSR?

**TSR (Task Success Rate)** measures implementation completion based on TDD evidence:
- TSR = (Completed tasks / Total attempted tasks) x 100
- Threshold: TSR >= 95% required for PASS status
- Tasks must have all 4 TDD evidence types to count as completed

## Evidence Ledger Structure

```json
{
  "version": "1.0",
  "terminal_id": "code_evidence_terminal",
  "tasks": {
    "TASK-001": {
      "description": "Add user authentication",
      "evidence": {
        "RED": {"completed": true, "timestamp": "2026-03-13T10:00:00"},
        "GREEN": {"completed": true, "timestamp": "2026-03-13T10:15:00"},
        "REFACTOR": {"completed": true, "timestamp": "2026-03-13T10:30:00"},
        "VERIFY": {"completed": true, "timestamp": "2026-03-13T10:45:00"}
      },
      "done": true,
      "done_at": "2026-03-13T10:45:00"
    }
  }
}
```

## How TSR is Calculated

**Evidence evaluation logic**:
1. **Completed task**: `done=True` AND all 4 evidence types completed (RED, GREEN, REFACTOR, VERIFY)
2. **Failed task**: `done=False` with partial evidence (some stages complete)
3. **Blocked task**: `done=False` with no evidence (no stages complete)

**Calculation**:
```python
total_attempted = len(tasks)
completed = 0
failed = 0
blocked = 0

for task_id, task_data in tasks.items():
    if task_data.get("done", False):
        evidence = task_data.get("evidence", {})
        required = ["RED", "GREEN", "REFACTOR", "VERIFY"]
        all_present = all(
            evidence.get(stage, {}).get("completed")
            for stage in required
        )
        if all_present:
            completed += 1
        else:
            failed += 1  # Marked done but missing evidence
    else:
        evidence = task_data.get("evidence", {})
        stages_complete = sum(
            1 for e in evidence.values() if e.get("completed")
        )
        if stages_complete == 0:
            blocked += 1
        else:
            failed += 1

tsr = (completed / total_attempted) * 100 if total_attempted > 0 else 0.0
```

## Pass/Fail Criteria

**PASS when**:
- TSR >= 95%
- All tasks have complete TDD evidence
- No blocked tasks

**FAIL when**:
- TSR < 95%
- Tasks marked done but missing evidence types
- Blocked tasks (no evidence at all)

## Example TSR Report

```
### TSR Metric
**Task Success Rate**: 75.0%
**Total Attempted**: 4 tasks
**Completed**: 3 tasks (all 4 evidence types)
**Failed**: 1 task (partial evidence)
**Blocked**: 0 tasks

### Findings
**HIGH**: Task Success Rate is 75.0%, below 95% threshold
**Details**:
  - TASK-004: "Write unit tests" -> Only RED evidence present
  - Missing: GREEN, REFACTOR, VERIFY evidence
```

## Best Practices

1. **Track all TDD phases**: Don't skip RED, GREEN, REFACTOR, or VERIFY
2. **Update ledger continuously**: Record evidence as each phase completes
3. **Don't mark done early**: Only set `done=True` after all 4 evidence types
4. **Verify evidence integrity**: Use evidence ledger validation before DONE claim

## Integration with /verify

```bash
/verify --post-hoc --plan .claude/plans/plan-example.md --evidence-ledger ~/.claude/.state/code/evidence_terminal.json
```

**Verification workflow**:
1. Load evidence ledger from specified path
2. Calculate TSR for all tasks in plan
3. Check TSR against 95% threshold
4. Report failed/blocked tasks with missing evidence
5. Flag tasks marked done without complete evidence
