# Task 4.2: /code --repair-markers Command - GREEN Evidence

**Task**: Implement `scripts/repair_markers.py` for /code --repair-markers command
**Date**: 2026-03-01
**Phase**: GREEN (Implementation)

## Implementation Summary

Created repair_markers script that detects and invalidates stale phase markers (phase completion markers with old commit hash that doesn't match current git HEAD). Supports interactive confirmation, dry-run mode, and CLI invocation.

## Files Created

### `scripts/repair_markers.py`
- **Purpose**: Detect and repair stale phase markers after git rollback
- **API**: Multiple functions for detection, invalidation, and CLI entry point
- **Safety**: Confirmation prompt by default, dry-run mode for preview

## Key Implementation Details

### Core Functions

#### `detect_stale_markers(phase_mgr) -> list[str]`
Detects phase markers with stale commit hashes.

```python
def detect_stale_markers(phase_mgr) -> list[str]:
    """Detect phase markers with stale commit hashes.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        List of phase names with stale markers

    Example:
        >>> detect_stale_markers(phase_mgr)
        ['BUILD', 'TRACE']
    """
```

**Logic**:
1. Gets all phases from phase state
2. Checks each phase's validity using `phase_mgr.is_phase_valid(phase)`
3. Returns list of invalid phase names
4. Handles corrupted state files gracefully

#### `invalidate_stale_markers(phase_mgr) -> int`
Invalidates all detected stale markers.

```python
def invalidate_stale_markers(phase_mgr) -> int:
    """Invalidate all stale phase markers.

    Args:
        phase_mgr: PhaseStateManager instance

    Returns:
        Number of markers invalidated
    """
```

**Logic**:
1. Detects stale markers
2. For each stale marker: calls `phase_mgr.invalidate_phase(phase_name)`
3. Logs each invalidation
4. Returns count of invalidated markers

#### `repair_markers_dry_run(phase_mgr) -> str`
Generates preview report without modifying state.

**Returns**: Formatted string showing:
- Current git HEAD commit
- Stale markers with recorded commit hash
- Recommendation for repair

#### `repair_markers_interactive(phase_mgr, confirm: bool = True) -> dict`
Repairs markers with optional confirmation prompt.

**Parameters**:
- `confirm`: If True, asks user before repairing (default: True)
- Returns dict with: `invalidated_markers` (list), `invalidated_count` (int), `skipped` (bool)

**Flow**:
1. Detects stale markers
2. If none found: returns empty result
3. Shows what will be repaired
4. If confirm=True: prompts user
5. If user declines: returns with skipped=True
6. If user confirms or confirm=False: invalidates markers
7. Returns result dict

#### `repair_stale_markers(phase_mgr, stale_markers: list[str] | None = None, confirm: bool = True, dry_run: bool = False) -> dict`
High-level API coordinating all repair operations.

**Parameters**:
- `stale_markers`: Optional list of specific markers to repair (default: detect all)
- `confirm`: Require confirmation before repair (default: True)
- `dry_run`: Preview mode without modification (default: False)

**Returns**: Dict with:
```python
{
    'detected_markers': list[str],  # All stale markers found
    'invalidated_markers': list[str],  # Markers actually invalidated
    'invalidated_count': int,  # Count of invalidated markers
    'skipped': bool,  # True if user declined confirmation
    'dry_run': bool,  # True if dry-run mode
    'report': str,  # Human-readable report
}
```

#### `main() -> int`
CLI entry point with argument parsing.

**Arguments**:
- `--yes`: Auto-confirm repair (skip prompt)
- `--dry-run`: Preview mode without modification

**Exit codes**:
- 0: Success
- 1: Error

## Test Results

**All 18 tests passing** (0.41s):

### Test Class Breakdown
1. **TestRepairMarkersCoreFunctionality** (3 tests)
   - ✅ Detects stale markers
   - ✅ Valid markers unchanged
   - ✅ Invalidates stale markers

2. **TestRepairMarkersCommitHashValidation** (3 tests)
   - ✅ Compares to git HEAD
   - ✅ Handles missing git
   - ✅ Handles detached HEAD

3. **TestRepairMarkersConfirmation** (3 tests)
   - ✅ Confirms before deletion
   - ✅ Auto-confirm flag (--yes)
   - ✅ Dry-run mode (--dry-run)

4. **TestRepairMarkersEdgeCases** (3 tests)
   - ✅ Empty state file
   - ✅ No markers present
   - ✅ Corrupted state file

5. **TestRepairMarkersIntegration** (3 tests)
   - ✅ Full integration test
   - ✅ CLI invocation
   - ✅ With PhaseStateManager

6. **TestRepairMarkersBatchOperations** (3 tests)
   - ✅ Multiple stale markers
   - ✅ Preserves valid markers
   - ✅ Reports changes

## Integration Points

- Uses `PhaseStateManager` from `utils.phase_state`
- Uses `get_git_head_hash()` from `utils.phase_state`
- Uses `is_phase_valid()` for commit comparison
- Uses `invalidate_phase()` for marker invalidation
- Uses `logging` module for operation logging

## Design Decisions

1. **Safety First**: Confirmation prompt by default prevents accidental data loss
2. **Dry-Run Mode**: Preview what will be repaired without executing
3. **Selective Repair**: Can repair specific markers or detect all stale markers
4. **Graceful Degradation**: Handles missing git, corrupted state, empty files
5. **Comprehensive Logging**: Every operation logged for debugging
6. **CLI-Friendly**: Proper exit codes and argument parsing

## Usage Examples

### Python API
```python
from scripts.repair_markers import repair_stale_markers
from utils.phase_state import PhaseStateManager

terminal_id = "default"
phase_mgr = PhaseStateManager(terminal_id)

# Interactive repair with confirmation
result = repair_stale_markers(phase_mgr, confirm=True)
print(f"Repaired {result['invalidated_count']} markers")

# Auto-confirm repair
result = repair_stale_markers(phase_mgr, confirm=False)

# Dry-run preview
result = repair_stale_markers(phase_mgr, dry_run=True)
print(result['report'])
```

### CLI
```bash
# Interactive repair (with confirmation)
python scripts/repair_markers.py

# Auto-confirm repair
python scripts/repair_markers.py --yes

# Dry-run preview
python scripts/repair_markers.py --dry-run
```

## Example Output

```
Repairing stale phase markers...

Stale markers detected:
  BUILD: abc123def456 (current: def789abc123)
  TRACE: abc123def456 (current: def789abc123)

Repair 2 markers? [y/N]: y

Repaired:
  BUILD: invalidated (commit mismatch)
  TRACE: invalidated (commit mismatch)

Summary: 2 markers repaired
```

## Error Handling

### Graceful Degradation
- **Missing git**: Returns None from `get_git_head_hash()`, treats all markers as valid
- **Corrupted state**: Catches JSONDecodeError, returns empty list
- **Empty state**: Returns empty list (no markers to check)
- **Detached HEAD**: Works normally (compares commit hashes)

### Defensive Programming
- All functions check for None returns
- Proper error logging for all failure modes
- User-friendly error messages

## Notes

- Auto-formatted with ruff (raw string for docstring)
- Comprehensive logging for debugging
- Safe by default (confirmation required)
- Dry-run mode for safe preview
- CLI integration with argparse
