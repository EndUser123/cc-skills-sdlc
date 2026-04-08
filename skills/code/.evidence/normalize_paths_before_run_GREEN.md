# Task 3.3: Path Normalization Integration - GREEN Evidence

**Task**: Implement `scripts/normalize_paths_before_run.py` to auto-normalize Git Bash paths before TRACE verification
**Date**: 2026-03-01
**Phase**: GREEN (Implementation)

## Implementation Summary

Created path normalization script that converts Git Bash paths (`/p/...`) to Windows native format (`P:\...`) before running pytest/test commands, preventing path mismatch issues in multi-terminal environments.

## Files Created

### `scripts/normalize_paths_before_run.py`
- **Purpose**: Normalize all paths in command strings before execution
- **API**: `normalize_paths_before_run(command: str) -> str`
- **Integration**: Uses existing `utils.normalize_paths.normalize_paths_in_command()`
- **Logging**: Records each path transformation for debugging

## Key Implementation Details

### Function Signature
```python
def normalize_paths_before_run(command: str) -> str:
    """Normalize all paths in a command string before execution.

    This function:
    1. Finds all Git Bash paths (/p/...) in the command
    2. Converts them to Windows native format (P:\...)
    3. Logs each transformation for debugging
    4. Returns the normalized command
    """
```

### Normalization Logic
1. Track original command for comparison
2. Call `normalize_paths_in_command()` from utils
3. If command changed, log all Git Bash paths that were normalized
4. Return normalized command

### Example Transformation
```
Input:  "pytest /p/.claude/skills/code/tests/test_foo.py -v"
Output: "pytest P:\.claude\skills\code\tests\test_foo.py -v"
Log:    "Normalized /p/.claude/skills/code/tests/test_foo.py -> P:\.claude\skills\code\tests\test_foo.py"
```

## Test Results

**All 19 tests passing** (0.19s):

### Test Class Breakdown
1. **TestNormalizeGitBashPathToWindows** (1 test)
   - ✅ Converts `/p/...` to `P:\...`

2. **TestNormalizeAlreadyWindowsPath** (1 test)
   - ✅ Idempotent for Windows paths

3. **TestNormalizeRelativePath** (2 tests)
   - ✅ Preserves `tests/test_foo.py`
   - ✅ Preserves `./tests/test_foo.py`

4. **TestNormalizeCommandWithPaths** (2 tests)
   - ✅ Normalizes paths in `pytest /p/... -v`
   - ✅ Normalizes paths in `python -m pytest /p/...`

5. **TestNormalizeMultiplePathsInCommand** (2 tests)
   - ✅ Normalizes ALL paths: `/p/src/test1.py /p/src/test2.py`
   - ✅ Handles mixed Git Bash + Windows paths

6. **TestPathNormalizationLogging** (2 tests)
   - ✅ Verifies logging records transformations
   - ✅ Checks detailed log format

7. **TestNormalizePathsBeforeRunIntegration** (5 tests)
   - ✅ Full integration test
   - ✅ Empty string edge case
   - ✅ Command without paths unchanged
   - ✅ Multiple drives (`/p/` and `/c/`)

8. **TestEdgeCases** (5 tests)
   - ✅ Paths with spaces
   - ✅ Paths with special chars (dots, dashes, underscores)
   - ✅ Trailing slashes (directories)
   - ✅ Double slashes (`//p/...`)
   - ✅ Lowercase drive letter → uppercase

## Integration Points

- Uses `utils.normalize_paths.normalize_paths_in_command()` for core logic
- Uses `utils.normalize_paths.normalize_path()` for individual path conversion
- Logging via Python's `logging` module
- CLI mode for manual testing

## Design Decisions

1. **Delegation**: Core normalization logic delegated to existing utils (DRY principle)
2. **Logging Only on Changes**: Only logs when command actually changes (reduces noise)
3. **Simple API**: Single function `normalize_paths_before_run(command: str) -> str`
4. **Idempotent**: Safe to call multiple times (Windows paths unchanged)
5. **Preserves Relative Paths**: Does not normalize relative paths (only Git Bash format)

## Usage Examples

### Python API
```python
from scripts.normalize_paths_before_run import normalize_paths_before_run

# Normalize pytest command
cmd = "pytest /p/.claude/skills/code/tests/test_foo.py -v"
normalized = normalize_paths_before_run(cmd)
# Result: "pytest P:\\.claude\\skills\\code\\tests\\test_foo.py -v"
```

### CLI
```bash
python scripts/normalize_paths_before_run.py "pytest /p/src/test.py"
```

## Notes

- Auto-formatted with ruff (raw string for docstring)
- Removes unused imports (`is_git_bash_path`, `is_windows_path`)
- All path formats handled: Git Bash, Windows, relative
- Logging provides audit trail for debugging
