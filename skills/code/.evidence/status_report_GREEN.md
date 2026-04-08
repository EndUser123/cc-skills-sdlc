# Task 4.1: /code --status Command - GREEN Evidence

**Task**: Implement `scripts/status_report.py` for `/code --status` command
**Date**: 2026-03-01
**Phase**: GREEN (Implementation)

## Implementation Summary

Created comprehensive status reporting script that displays build status including phase completion, task progress, missing evidence, and terminal ownership information.

## Files Created

### `scripts/status_report.py`
- **Purpose**: Generate status report for /code build workflow
- **API**: `generate_status_report(evidence_mgr, phase_mgr) -> str`
- **Sections**: Phase Status, Task Progress, Missing Evidence, Terminal Ownership

## Key Implementation Details

### Function Signature
```python
def generate_status_report(
    evidence_mgr: Optional["EvidenceManager"] = None,
    phase_mgr: Optional["PhaseStateManager"] = None,
) -> str:
    """Generate a comprehensive status report for the /code build workflow.

    Displays:
    - Phase completion status (BUILD/TRACE/SHIP)
    - Task progress summary (complete/pending/blocked)
    - Missing evidence per task
    - Terminal ownership and lease status
    """
```

### Section 1: Phase Status
- Shows all 3 phases (BUILD, TRACE, SHIP) with status indicators
- ✅ Complete (valid: commit hash matches HEAD)
- ✗ Complete (invalid: commit mismatch)
- ⏸ In Progress
- ❌ Not Started
- ✗ Invalid phase (for unknown completed phases)

### Section 2: Task Progress
- Counts tasks by status: complete, pending, blocked
- Complete = all 4 evidence types present (RED, GREEN, REFACTOR, VERIFY)
- Pending = has RED evidence but missing other types
- Blocked = no RED evidence

### Section 3: Missing Evidence
- Lists each incomplete task with missing evidence types
- Empty if all tasks complete

### Section 4: Terminal Ownership
- Shows current terminal owner
- Calculates remaining lease time in minutes
- Shows "Expired" or "No active lease" as appropriate

## Test Results

**All 18 tests passing** (0.58s):

### Test Class Breakdown
1. **TestStatusReportPhaseStatus** (3 tests)
   - ✅ Displays phase status
   - ✅ Shows all phases
   - ✅ Invalid phase detection (commit mismatch)

2. **TestStatusReportTaskProgress** (3 tests)
   - ✅ Shows task progress counts
   - ✅ Handles empty task list
   - ✅ Task IDs visible

3. **TestStatusReportMissingEvidence** (3 tests)
   - ✅ Lists missing evidence
   - ✅ Formats missing evidence clearly
   - ✅ Complete task shows no missing evidence

4. **TestStatusReportTerminalOwnership** (3 tests)
   - ✅ Shows terminal ownership
   - ✅ Shows lease expiration
   - ✅ Handles no ownership

5. **TestStatusReportEmptyLedger** (2 tests)
   - ✅ Empty ledger handling
   - ✅ Returns string

6. **TestStatusCommandIntegration** (4 tests)
   - ✅ Full integration test
   - ✅ None managers handling
   - ✅ Only evidence_mgr
   - ✅ Only phase_mgr

## Integration Points

- Uses `PhaseStateManager.is_phase_valid()` for commit mismatch detection
- Uses `PhaseStateManager._load_build_state()` for terminal ownership
- Uses `EvidenceManager._load_ledger()` for task progress and missing evidence
- Uses Python's `datetime` module for lease expiration calculation

## Design Decisions

1. **Optional Managers**: Both evidence_mgr and phase_mgr are optional - functions gracefully degrade
2. **Commit-Aware Validation**: Uses `is_phase_valid()` to detect stale phase markers
3. **Invalid Phase Detection**: Flags phases not in valid list (BUILD, TRACE, SHIP)
4. **Lease Calculation**: Converts ISO datetime to human-readable "minutes remaining"
5. **Clear Status Indicators**: Uses emoji (✅✗⏸❌) for visual scanning

## Usage Examples

### Python API
```python
from scripts.status_report import generate_status_report
from utils.evidence import EvidenceManager
from utils.phase_state import PhaseStateManager

terminal_id = "default"
evidence_mgr = EvidenceManager(terminal_id)
phase_mgr = PhaseStateManager(terminal_id)

report = generate_status_report(evidence_mgr, phase_mgr)
print(report)
```

### CLI
```python
if __name__ == "__main__":
    from utils.evidence import EvidenceManager
    from utils.phase_state import PhaseStateManager

    terminal_id = "default"
    evidence_mgr = EvidenceManager(terminal_id)
    phase_mgr = PhaseStateManager(terminal_id)

    report = generate_status_report(evidence_mgr, phase_mgr)
    print(report)
```

## Example Output

```
=== /code Build Status ===

Phase Status:
  BUILD: ✅ Complete
  TRACE: ⏸ In Progress
  SHIP: ❌ Not Started

Task Progress:
  3 complete, 2 pending, 1 blocked

Missing Evidence:
  task-2: GREEN, REFACTOR
  task-3: RED, GREEN, REFACTOR, VERIFY

Terminal Ownership:
  Current: terminal-001
  Lease: Expires in 15 minutes
```

## Notes

- All edge cases handled: empty ledger, missing managers, invalid phases
- Auto-formatted with ruff (raw string for docstring)
- Handles expired leases gracefully
- Status indicators chosen for visual scanning
