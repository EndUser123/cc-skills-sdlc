# Task 4.3: /code --fix-paths Command - GREEN Evidence

**Task**: Implement `scripts/fix_state_paths.py` for /code --fix-paths command
**Date**: 2026-03-01
**Phase**: GREEN (Implementation)

## Implementation Summary

Created fix_state_paths script that scans state JSON files for Git Bash paths (/p/...), batch normalizes them to Windows native format (P:\\...), creates backups before modification, and supports dry-run mode for safe preview.

## Files Created

### `scripts/fix_state_paths.py`
- **Purpose**: Fix Git Bash paths in state JSON files after git operations
- **API**: Multiple functions for detection, normalization, and batch processing
- **Safety**: Backup before modification, dry-run mode, rollback on error

## Key Implementation Details

### Core Functions

#### `detect_git_bash_paths(data: Any) -> list[str]`
Recursively scans JSON data for Git Bash path strings.

```python
def detect_git_bash_paths(data: Any) -> list[str]:
    """Recursively detect Git Bash paths in JSON data.

    Args:
        data: JSON data (dict, list, or primitive)

    Returns:
        List of Git Bash paths found

    Example:
        >>> detect_git_bash_paths({"path": "/p/src/test.py"})
        ['/p/src/test.py']
    """
```

**Logic**:
1. Pattern matches `/[a-z]/[\w/\-.]+` (e.g., `/p/.claude/skills/code`)
2. Recursively scans dicts, lists, and primitive values
3. Returns list of detected Git Bash paths
4. Ignores Windows paths (`P:\...`) and relative paths

#### `normalize_git_bash_path(path: str) -> str`
Converts Git Bash path to Windows native format.

```python
def normalize_git_bash_path(path: str) -> str:
    """Normalize a Git Bash path to Windows native format.

    Args:
        path: Git Bash path (e.g., /p/src/test.py)

    Returns:
        Windows native path (e.g., P:\\\\src\\\\test.py)

    Example:
        >>> normalize_git_bash_path("/p/.claude/skills/code")
        'P:\\\\.claude\\\\skills\\\\code'
    """
```

**Logic**:
1. Uses existing `utils.normalize_paths.normalize_path()` for conversion
2. Only processes Git Bash paths, preserves all others unchanged
3. Returns normalized path with double backslashes for JSON

#### `fix_paths_in_data(data: Any) -> tuple[Any, int]`
Recursively normalizes all Git Bash paths in JSON structures.

**Returns**: (modified_data, count_of_paths_normalized)

**Logic**:
- Recursively walks dicts, lists, and primitives
- Normalizes Git Bash paths in place
- Preserves non-path content unchanged
- Tracks count of paths normalized

#### `fix_paths_in_file(file_path: str | Path, backup: bool = True) -> int`
Loads JSON file, normalizes paths, creates backup, writes back.

**Parameters**:
- `backup`: If True, creates `.backup` file before modification (default: True)

**Returns**: Count of paths normalized

**Error Handling**:
- JSON decode errors logged, returns 0
- Backup failures handled gracefully
- Write failures don't corrupt original file

#### `find_state_files(state_dir: str | Path) -> list[Path]`
Recursively scans directory for `.json` files.

**Returns**: List of Path objects

**Filtering**:
- Only `.json` files
- Excludes backup files (`.json.backup`)
- Recursive directory scan

#### `fix_paths_in_directory(state_dir: str | Path, backup: bool = True, dry_run: bool = False) -> dict`
High-level API for batch processing all JSON files.

**Parameters**:
- `backup`: Create backups before modification (default: True)
- `dry_run`: Preview mode without modification (default: False)

**Returns**: Summary dict with:
```python
{
    'files_processed': list[str],  # File paths processed
    'total_paths_fixed': int,  # Total paths normalized across all files
    'results': dict[str, int],  # Per-file path counts
}
```

#### `fix_paths_main(state_dir: str | Path, backup: bool = True, dry_run: bool = False) -> dict`
Main entry point with logging and summary output.

**Behavior**:
- Prints scan results
- Processes each file with detailed logging
- Prints summary of changes
- Returns results dict

#### `main() -> int`
CLI entry point with argparse.

**Arguments**:
- `--state-dir`: Path to state directory (default: current directory)
- `--no-backup`: Skip backup creation (not recommended)
- `--dry-run`: Preview mode without modification

**Exit codes**:
- 0: Success
- 1: Error

## Test Results

**All 29 tests passing** (0.31s):

### Test Class Breakdown
1. **TestPathDetection** (4 tests)
   - ✅ Detects Git Bash paths
   - ✅ Detects multiple drives
   - ✅ Ignores Windows paths
   - ✅ Ignores relative paths

2. **TestPathNormalization** (5 tests)
   - ✅ Normalizes to Windows format
   - ✅ Multiple drives
   - ✅ Preserves non-Git-Bash paths
   - ✅ Handles special characters
   - ✅ Empty and null values

3. **TestJSONModification** (5 tests)
   - ✅ Updates JSON files
   - ✅ Preserves non-path content
   - ✅ Nested paths
   - ✅ Valid JSON output
   - ✅ Empty JSON file

4. **TestBackupBehavior** (3 tests)
   - ✅ Creates backup
   - ✅ Backup format
   - ✅ Restores on error

5. **TestScanningAndBatchOperations** (5 tests)
   - ✅ Scans all state files
   - ✅ Recursive directory scan
   - ✅ Filters by pattern
   - ✅ Handles multiple files
   - ✅ Reports changes

6. **TestEdgeCases** (3 tests)
   - ✅ No paths found
   - ✅ Mixed path formats
   - ✅ Special characters

7. **TestIntegrationTests** (4 tests)
   - ✅ Full integration
   - ✅ CLI invocation
   - ✅ Dry-run mode
   - ✅ Preserves JSON structure

## Integration Points

- Uses `utils.normalize_paths.normalize_path()` for conversion
- Uses `pathlib.Path` for cross-platform path handling
- Uses `json` for JSON serialization
- Uses `logging` module for operation logging
- Uses `argparse` for CLI argument parsing

## Design Decisions

1. **Safety First**: Backup before modification by default
2. **Dry-Run Mode**: Preview changes before executing
3. **Recursive Scanning**: Finds JSON files in subdirectories
4. **Preserve Structure**: Only modifies path strings, preserves all other content
5. **Batch Processing**: Processes all files in one operation
6. **Comprehensive Logging**: Every operation logged for debugging
7. **Graceful Degradation**: Handles errors without corrupting data

## Usage Examples

### Python API
```python
from scripts.fix_state_paths import fix_paths_in_directory
from pathlib import Path

# Fix all paths in state directory (with backups)
result = fix_paths_in_directory(Path("./state"), backup=True)
print(f"Fixed {result['total_paths_fixed']} paths in {len(result['files_processed'])} files")

# Dry-run preview
result = fix_paths_in_directory(Path("./state"), dry_run=True)
for file, count in result['results'].items():
    print(f"{file}: {count} paths")
```

### CLI
```bash
# Default operation with backups
python scripts/fix_state_paths.py

# Custom state directory
python scripts/fix_state_paths.py --state-dir /path/to/state

# No backups (not recommended)
python scripts/fix_state_paths.py --no-backup

# Dry-run preview
python scripts/fix_state_paths.py --dry-run
```

## Example Output

```
Fixing Git Bash paths in state files...

Scanned: 3 JSON file(s)
Found: 5 Git Bash path(s) to normalize

Fixing: state1.json
  Fixed 2 path(s) in state1.json
  Backup: state1.json.backup

Fixing: subdir/state2.json
  Fixed 3 path(s) in subdir/state2.json
  Backup: subdir/state2.json.backup

Summary: 5 path(s) normalized in 3 file(s)
```

## Path Detection Pattern

**Git Bash Pattern**: `/[a-z]/[\w/\-.]+`
- Matches: `/p/.claude/skills/code`, `/c/Users/test`, `/d/src/test.py`
- Ignores: `P:\.claude\skills\code`, `src/test.py`, `./tests/test.py`

**Conversion Examples**:
- `/p/.claude/skills/code` → `P:\\\\.claude\\\\skills\\\\code`
- `/c/Users/test` → `C:\\\\Users\\\\test`
- `/d/src/test.py` → `D:\\\\src\\\\test.py`

## Error Handling

### Graceful Degradation
- **JSON decode errors**: Logged and skipped, returns 0 paths fixed
- **Backup failures**: Error logged, operation aborted
- **Write failures**: Original file preserved, error logged

### Defensive Programming
- All functions check for None and empty strings
- Proper error logging for all failure modes
- User-friendly error messages
- Backup/rollback support on error

## Notes

- Auto-formatted with ruff (raw string for docstring)
- Comprehensive logging for debugging
- Safe by default (backup enabled)
- Dry-run mode for safe preview
- CLI integration with argparse
- Handles nested JSON structures recursively
- Preserves non-path content unchanged
