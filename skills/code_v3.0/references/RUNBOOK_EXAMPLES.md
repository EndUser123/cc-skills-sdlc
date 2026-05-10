# Runbook Examples - Phase 3-6 Commands

**Last Updated**: 2026-03-01

This document provides practical runbook examples for using the Phase 3-6 UX commands introduced in the /code skill improvement.

## Table of Contents

1. [Using `/code --status` to Debug Stuck Build](#example-1-status-debug)
2. [Using `/code --repair-markers` After Git Rollback](#example-2-repair-markers)
3. [Using `/code --fix-paths` for Path Mismatch Issues](#example-3-fix-paths)
4. [Evidence Guard Blocking SHIP](#example-4-evidence-guard)

---

## Example 1: Using `/code --status` to Debug Stuck Build

### Scenario
You're working on a feature and the build seems stuck. You want to know:
- What phase is active?
- Which tasks are complete/pending/blocked?
- What evidence is missing?
- Who owns the terminal?

### Solution

```bash
/code --status
```

### Expected Output

```
Phase Status:
  BUILD: ✅ Complete (commit: abc123def456)
  TRACE: ✗ Complete (invalid: commit mismatch)
  SHIP: ⏸ Pending

Task Progress:
  Complete: 3/5
  Pending: 2/5
  Blocked: 0/5

Missing Evidence:
  Task 3: Implement auth service
    Missing: GREEN, VERIFY
  Task 4: Add unit tests
    Missing: RED, GREEN, REFACTOR, VERIFY

Terminal: default
Owner: lead
Lease expires: 2026-03-01T14:30:00Z (15 minutes from now)
```

### Analysis

From this output you can see:

1. **Phase issue**: TRACE phase is marked complete but has a commit mismatch - this indicates the code has changed since TRACE verification
2. **Task progress**: You're 60% complete (3/5 tasks done)
3. **Evidence gaps**: Task 3 needs GREEN and VERIFY evidence, Task 4 has no evidence at all
4. **Terminal ownership**: You own the terminal with 15 minutes remaining on the lease

### Next Steps

1. If TRACE has commit mismatch, run `/code --repair-markers` to invalidate stale markers
2. Continue with pending tasks (Task 3 and Task 4)
3. When all tasks complete and evidence is collected, proceed to SHIP

### Advanced Usage

Check status for a specific terminal:

```python
from scripts.status_report import generate_status_report
from utils.evidence_ledger import EvidenceManager
from utils.phase_state import PhaseStateManager

evidence_mgr = EvidenceManager()
phase_mgr = PhaseStateManager(terminal_id="terminal-1")

report = generate_status_report(evidence_mgr, phase_mgr)
print(report)
```

---

## Example 2: Using `/code --repair-markers` After Git Rollback

### Scenario
You just did a `git reset --hard HEAD~2` to rollback 2 commits. Now your phase markers are stale - they reference commits that no longer exist. The /code skill is blocking phase transitions because it thinks phases are complete when they're actually invalid.

### Solution

```bash
/code --repair-markers
```

### Interactive Flow

```
/code --repair-markers

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

### Dry-Run Mode (Preview First)

```bash
/code --repair-markers --dry-run
```

Output:
```
Repairing stale phase markers (dry-run)...

Stale markers detected:
  BUILD: abc123def456 (current: def789abc123)
  TRACE: abc123def456 (current: def789abc123)

No changes made (dry-run mode)
```

### Auto-Confirm Mode (Non-Interactive)

For automation or CI/CD pipelines:

```bash
/code --repair-markers --yes
```

Output:
```
Repairing stale phase markers...

Stale markers detected:
  BUILD: abc123def456 (current: def789abc123)
  TRACE: abc123def456 (current: def789abc123)

Repaired:
  BUILD: invalidated (commit mismatch)
  TRACE: invalidated (commit mismatch)

Summary: 2 markers repaired
```

### What Happens Under the Hood

1. Script calls `detect_stale_markers(phase_mgr)` to find invalid markers
2. For each stale marker, calls `invalidate_phase(phase_name)` which:
   - Renames phase marker file from `<phase>.json` to `<phase>.json.stale`
   - This marks the phase as incomplete in the phase state
3. Next /code invocation will recognize phases as incomplete and allow proper transitions

### Recovery

If you accidentally invalidate the wrong marker:

```bash
# Restore from .stale backup
mv .claude/state/BUILD.json.stale .claude/state/BUILD.json
```

---

## Example 3: Using `/code --fix-paths` for Path Mismatch Issues

### Scenario
After a git operation on Windows with Git Bash, your state files contain Git Bash paths like `/p/.claude/skills/code` but the system is running on Windows where paths should be `$CLAUDE_ROOT/skills\code`. Tests are failing because the path comparison doesn't work.

### Solution

```bash
/code --fix-paths
```

### Expected Output

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

### Dry-Run Mode (Preview First)

```bash
/code --fix-paths --dry-run
```

Output:
```
Fixing Git Bash paths in state files (dry-run)...

Scanned: 3 JSON file(s)
Found: 5 Git Bash path(s) to normalize

Would fix:
  state1.json: 2 paths
    /p/src/test.py → P:\\\\\\\src\\test.py
    /c/Users/config.json → C:\\Users\\config.json
  subdir/state2.json: 3 paths
    /p/.claude/skills/code → P:\\\\\\\.claude\\skills\\code
    /d/data/file.txt → D:\\data\\file.txt

No changes made (dry-run mode)
```

### Path Conversion Examples

| Git Bash Path | Windows Native Path |
|---------------|---------------------|
| `/p/.claude/skills/code` | `$CLAUDE_ROOT/skills\code` |
| `/c/Users/test` | `C:\Users\test` |
| `/d/src/test.py` | `D:\src\test.py` |
| `/tmp/cache` | `/tmp/cache` (unchanged, not a Windows drive) |

### What Gets Fixed

The script scans JSON files recursively and finds:
- Object keys that are Git Bash paths
- String values that are Git Bash paths
- Nested structures (dicts, lists)

It preserves:
- Non-path content (numbers, booleans, null)
- Relative paths
- Windows paths (already correct)
- URLs and other non-filesystem paths

### Recovery

If the fix breaks something:

```bash
# Restore from backup
mv state1.json.backup state1.json
mv subdir/state2.json.backup subdir/state2.json
```

### Advanced Usage

Fix paths in a specific directory:

```bash
/code --fix-paths --state-dir /path/to/state
```

Skip backups (not recommended):

```bash
/code --fix-paths --no-backup
```

---

## Example 4: Evidence Guard Blocking SHIP

### Scenario
You've completed all tasks and try to run `/code --phase=SHIP` to mark the feature done, but it's blocked with an error:

```
Error: Cannot mark done - missing evidence for task 'Task 3'
Required evidence types: RED, GREEN, REFACTOR, VERIFY
Missing: GREEN, VERIFY
```

### Understanding the Evidence Guard

The SHIP phase enforces that all tasks have complete TDD evidence:
- **RED**: Failing test output exists (test written first)
- **GREEN**: Previously failing tests now pass (implementation works)
- **REFACTOR**: Tests still pass after cleanup (code quality maintained)
- **VERIFY**: Independent QA review passed (code verified)

### Solution

Check what evidence is missing:

```bash
/code --status
```

Look for the "Missing Evidence" section:

```
Missing Evidence:
  Task 3: Implement auth service
    Missing: GREEN, VERIFY
```

This means you need to:
1. **GREEN evidence**: Run the tests and show they pass
2. **VERIFY evidence**: Run QA verification and show it passes

### Collecting GREEN Evidence

```bash
# Run tests to demonstrate they pass
pytest tests/test_auth.py -v

# Output should show tests passing
# This is your GREEN evidence
```

### Collecting VERIFY Evidence

```bash
# Run QA verification
/code --verify
```

Or manually review:

```bash
# Use adversarial review
/adversarial-review src/auth.py
```

### Rechecking Done Claim

After collecting evidence, re-run the validation:

```bash
python scripts/validate_done_claim.py --plan plan.md --ledger .claude/resume_ledger.json
```

Expected output:
```
✅ All tasks have complete evidence (RED, GREEN, REFACTOR, VERIFY)
Ready to mark done
```

### Common Issues and Solutions

#### Issue 1: "Evidence file not found"

**Cause**: Evidence files weren't created during task execution

**Solution**: Re-run the task with proper TDD workflow:
```bash
/code Task 3
# Follow TDD: RED (write test) → GREEN (implement) → REFACTOR (clean) → VERIFY (review)
```

#### Issue 2: "VERIFY evidence missing but review was done"

**Cause**: Review wasn't documented or evidence file wasn't created

**Solution**: Create the evidence file manually:
```bash
# Create .evidence/task_3_VERIFY.md
# Include review summary, findings, and PASS/FAIL assessment
```

#### Issue 3: "RED evidence missing but tests exist"

**Cause**: Tests weren't written first (TDD violation)

**Solution**: Document that RED phase was skipped (requires explicit approval):
```bash
# In .evidence/task_3_RED.md
# Document: "RED phase skipped - tests written after implementation (approved by user)"
```

---

## Integration Examples

### Example: Full Workflow After Git Rollback

```bash
# 1. Check current status
/code --status
# Shows: TRACE phase invalid (commit mismatch)

# 2. Repair stale markers
/code --repair-markers --yes
# Output: 2 markers repaired

# 3. Check status again
/code --status
# Shows: All phases pending (correct state)

# 4. Continue work from BUILD phase
/code --phase=BUILD
```

### Example: Recovering from Path Issues

```bash
# 1. Diagnose path mismatch
pytest tests/test_integration.py
# Error: FileNotFoundError: [Errno 2] No such file or directory: '/p/.claude/skills/code/...'

# 2. Fix all state file paths
/code --fix-paths --dry-run
# Preview shows 15 paths will be fixed

# 3. Apply fixes
/code --fix-paths
# Output: 15 paths normalized in 4 files

# 4. Re-run tests
pytest tests/test_integration.py
# Tests now pass
```

### Example: Complete Build with Evidence Collection

```bash
# 1. Start build
/code

# 2. Check status mid-build
/code --status
# Shows: Task 2 complete, Task 3 in progress

# 3. After all tasks complete, check evidence
/code --status
# Look for "Missing Evidence" section

# 4. Collect missing evidence (GREEN, VERIFY)
pytest tests/ -v  # GREEN evidence
/code --verify src/auth.py  # VERIFY evidence

# 5. Validate done claim
python scripts/validate_done_claim.py --plan plan.md --ledger .claude/resume_ledger.json
# Output: ✅ Ready to mark done

# 6. Mark done (SHIP phase)
/code --phase=SHIP
```

---

## Troubleshooting

### Command Not Found

If `/code --status` (or other commands) aren't recognized:

```bash
# Check if script exists
ls scripts/status_report.py
ls scripts/repair_markers.py
ls scripts/fix_state_paths.py

# Scripts should be in $CLAUDE_ROOT/skills\code\scripts\
```

### Permission Denied

If you get permission errors:

```bash
# Windows: No permission issues expected
# Linux/Mac: Ensure scripts are executable
chmod +x scripts/*.py
```

### State File Not Found

If commands complain about missing state files:

```bash
# Check state directory
ls .claude/state/

# Should see: build_state.json, phase_markers.json, etc.
# If missing, initialize with:
/code --phase=BOOTSTRAP
```

### Backup Files Accumulating

If `.backup` files are accumulating:

```bash
# Clean up old backups (after confirming fixes work)
find .claude/state -name "*.backup" -mtime +7 -delete
```

---

## Best Practices

### 1. Always Use Dry-Run First

Before any destructive operation, preview changes:

```bash
/code --repair-markers --dry-run
/code --fix-paths --dry-run
```

### 2. Check Status Before Major Transitions

```bash
/code --status
# Review phase, task, and evidence status before proceeding to SHIP
```

### 3. Use Interactive Mode for Recovery Operations

```bash
/code --repair-markers  # Interactive (safer)
# NOT: /code --repair-markers --yes  # Auto-confirm (risky)
```

### 4. Keep Backups Until Verified

After `/code --fix-paths`, keep `.backup` files until you've verified tests pass:

```bash
/code --fix-paths
pytest tests/  # Verify
# If tests pass, then clean up backups
rm .claude/state/*.backup
```

### 5. Document Explicit Approvals

When bypassing evidence requirements, document in evidence file:

```markdown
# .evidence/task_X_RED.md

## RED Phase - Explicitly Skipped

**Date**: 2026-03-01
**Reason**: Legacy code - tests added after implementation
**Approved By**: User request
**Context**: Task involves refactoring existing working code
```

---

## Summary

The Phase 3-6 UX commands provide:

1. **Visibility** (`--status`): See exactly where you are in the build workflow
2. **Recovery** (`--repair-markers`): Fix stale state after git operations
3. **Path Safety** (`--fix-paths`): Normalize Git Bash to Windows paths automatically
4. **Quality Gates** (Evidence guards): Ensure TDD compliance before SHIP

These commands work together to provide a robust, observable build workflow with recovery mechanisms and quality enforcement.
