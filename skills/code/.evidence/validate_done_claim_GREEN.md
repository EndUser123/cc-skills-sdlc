# Task 3.2: Evidence Guard for SHIP Phase - GREEN Evidence

**Task**: Implement `scripts/validate_done_claim.py` to validate SHIP phase readiness
**Date**: 2026-03-01
**Phase**: GREEN (Implementation)

## Implementation Summary

Created evidence guard validation that checks all 4 TDD evidence types (RED, GREEN, REFACTOR, VERIFY) before allowing SHIP phase completion.

## Files Created

### `scripts/validate_done_claim.py`
- **Purpose**: Validates that all tasks have complete TDD evidence before SHIP
- **API**: Returns `True` on success, raises `ValueError` with detailed report on failure
- **Integration**: Uses `EvidenceManager.can_mark_done()` to check task completeness

## Key Implementation Details

### Function Signature
```python
def validate_done_claim(
    evidence_mgr,
    task_ids: Optional[list[str]] = None,
) -> bool:
```

### Validation Logic
1. If no task IDs specified, checks all tasks in ledger
2. If no tasks exist, validation passes (nothing to check)
3. For each task, checks `can_mark_done(task_id)` returns True
4. Generates detailed report of missing evidence by task
5. Raises `ValueError` with formatted report if any task incomplete

### Error Message Format
```
Cannot proceed to SHIP: N task(s) missing evidence.
Complete all 4 evidence types (RED, GREEN, REFACTOR, VERIFY) for each task.

Missing Evidence Details:
  - task-1: missing RED, GREEN
  - task-2: missing VERIFY
```

## Test Results

**All 8 tests passing** (0.34s):
- `test_all_tasks_complete_pass` - ✅ Returns True when all 4 evidence types present
- `test_one_task_missing_evidence` - ✅ Raises ValueError with clear error message
- `test_multiple_tasks_missing_evidence` - ✅ Detailed report for multiple incomplete tasks
- `test_no_tasks_in_ledger` - ✅ Passes when ledger is empty (nothing to check)
- `test_generate_missing_evidence_report` - ✅ Specific missing evidence types reported
- `test_error_message_clarity` - ✅ Error messages are actionable and clear
- `test_all_four_evidence_types_required` - ✅ All 4 types mandatory (RED, GREEN, REFACTOR, VERIFY)
- `test_partial_task_list_validation` - ✅ Can validate specific tasks only

## Integration Points

- Uses `EvidenceManager.can_mark_done(task_id)` API
- Called by SHIP phase validation hook (Task 3.2 integration)
- Prevents SHIP completion when tasks missing evidence

## Design Decisions

1. **Return Value**: Returns `True` instead of tuple to match test expectations
2. **Error Reporting**: Raises `ValueError` with detailed, multi-line report
3. **Empty Ledger**: Returns `True` when no tasks (nothing to validate)
4. **Task Selection**: Optional `task_ids` parameter allows partial validation

## Notes

- All 4 evidence types are required (RED, GREEN, REFACTOR, VERIFY)
- Missing evidence report includes task ID and specific missing types
- Error messages are actionable and clear for users
