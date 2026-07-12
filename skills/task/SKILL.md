---
name: task
description: Task orchestration - manage Claude Code task list
workflow_steps: []
---
# /task - Task Orchestration

## Purpose

Orchestrator for Claude Code task list operations. Routes sub-commands to built-in native tools (TaskCreate / TaskUpdate / TaskList / TaskGet).

## Principles

- **Cheap by default**: `/task list` runs only the built-in TaskList tool, no external search. Suggestions and unresolved-history scanning are opt-in.
- **Tool-first**: Wraps built-in tools, not a replacement system.
- **Evidence-based**: Completion verification uses deterministic receipts, not subject matching.
- **Persistence**: `.claude/state/task_tracker/{terminal_id}_tasks.json` via PostToolUse task tracker.
- **Multi-terminal safe**: Tasks survive compaction and sessions.
- **Receipt-based verification**: Completion receipts stored in `P:/.claude/state/task_receipts/{task_id}.json` (approved artifact location, NOT inside the skill dir). Read by `scripts/task_receipt.py`. Verified by `scripts/task_verify.py`.

## Commands

```bash
/task list                           # Default: compact, current terminal (TaskList only, no CHS/CKS)
/task list --all                     # All terminals (slower: reads tracker files)
/task list --status pending          # Filter by status
/task list --suggest                 # Show CHS/CKS/unresolved suggestions (opt-in)

/task scan                           # Explicit unresolved-history scan (opt-in, same as --suggest)

/task add "Fix auth bug"             # TaskCreate
/task add "Dark mode" --priority high # With priority
/task start 123                      # Begin work (TaskUpdate status=in_progress)
/task done 123                       # Complete + write receipt (TaskUpdate + task_receipt.py write)
/task done 123 --verify "pytest -q"  # Complete with verification commands

/task verify [ids...]                # Receipt-based verification (VERIFIED / REVIEW / NO_EVIDENCE / STALE / BLOCKED)
/task verify --json                  # Machine-readable output
/task clean [ids...]                 # Remove only VERIFIED-receipt tasks (dry-run by default)
/task clean [ids...] --apply         # Actually remove

/task search "authentication"        # Search within built-in task list
```

## Output Quick Reference

**Task format (compact):** `#<id> [<status>] <subject> [owner=<owner>]`

**Default /task list output:**
```
Current terminal tasks:
  #1 [pending] Fix auth bug
  #2 [in_progress] Add dark mode        owner=me
Completed: 0  In progress: 1  Pending: 1
```

**With `--all`:**
```
Terminal console_abc tasks:
  #1 [pending] Fix auth bug
Terminal console_def tasks:
  #3 [in_progress] Refactor router     owner=me
```

**With `--suggest`:** appends CHS/CKS suggestions and unresolved items. See [output-format.md](references/output-format.md).

**Status indicators:** `[pending]` / `[in_progress]` / `[completed]`

## /task done — Durable Completion Receipt

**Behavior:** Calls TaskUpdate(status="completed") AND writes a durable completion receipt via `scripts/task_receipt.py write --task-id <id> --verify <commands>`. The receipt is the deterministic evidence that authorizes later cleanup.

Receipt fields:
- task ID, terminal/session, repository/worktree, baseline commit (if available)
- changed files, verification commands/results
- final commit SHA, timestamp, evidence classification (VERIFIED/REVIEW/NO_EVIDENCE)

Receipts are NEVER deleted by /task clean — they outlive the task entry.

## /task verify — Receipt-Based Verification

Replaces the old subject-based `verify_completed.py` (basename / commit-message / pickaxe / grep), which produced false positives across the monorepo.

**Buckets (deterministic):**

| Bucket | Means | Clean-safe? |
|--------|-------|-------------|
| VERIFIED | Receipt exists with evidence_class=VERIFIED, repo matches, SHA reachable | Yes |
| REVIEW | Receipt exists with evidence_class=REVIEW (committed but no passing verification) | **No** |
| NO_EVIDENCE | No receipt for this task in the current repo | **No** |
| STALE | Receipt SHA no longer reachable (history rewritten) | **No** |
| BLOCKED | Receipt file present but unreadable/malformed | **No** |

**Exit codes:** 0 = every input task is VERIFIED. 1 = at least one task is not VERIFIED.

## /task clean — Safe Cleanup

**Rule:** Only exact task-linked VERIFIED receipts may authorize deletion.
**Never:** delete based solely on status=completed.
**Never:** ask the LLM to manually inspect every task when receipts are available.
**Receipts are preserved after deletion.**

`/task clean` operates on the tracker mirror (`_tasks.json` files in `P:/.claude/state/task_tracker/`) — the native live task list has no public TaskDelete API.

```bash
/task clean [ids...]           # Dry-run: shows what would be deleted
/task clean [ids...] --apply   # Actually removes VERIFIED-receipt tasks from tracker mirror
```

If a task lacks evidence, leave it untouched and report the exact reason (NO_EVIDENCE, STALE, BLOCKED).

## Usage Guide

```bash
/task add "Fix auth bug"                    # Create task
/task done 1 --verify "pytest -q"           # Complete with verification
/task verify                                # Check all tasks (reads receipts)
/task verify 1 2 --json                     # Check specific tasks, JSON output
/task clean                                 # Dry-run cleanup
/task clean 1 2 --apply                     # Remove VERIFIED tasks from tracker
/task list --suggest                        # List with suggestions
/task scan                                  # Scan for unresolved items
```

## Phase 1: Workflow (Generation Only)

1. **Parse sub-command** - Extract first argument as operation (list, add, done, verify, clean, scan, search, start)
2. **Route to handler** - Delegate to appropriate implementation
3. **Execute tool** - Call built-in tool (TaskCreate/TaskUpdate/TaskList/TaskGet) + optional receipt write
4. **Return result** - Display formatted output

## Phase Gate 1 → 2

**STOP condition before validation:**

```json
{"ok": false, "reason": "STOP: Generation phase incomplete", "missing": "<step>"}
```

Validation phase MUST NOT execute unless ALL of the following are true:
- Parse step completed (valid sub-command extracted)
- Route step completed (handler identified)
- Execute step completed (tool called successfully)

---

## Phase 2: Validation

### Pre-Route Validation
- **Before routing**: Validate sub-command exists
- **STOP**: Unknown sub-command -> halt, show usage

### Pre-Create Validation
- **Before task creation**: Check subject is not empty
- **STOP**: Empty subject -> halt, return error

### Pre-Update Validation
- **Before task update**: Verify task ID exists
- **STOP**: Non-existent task ID -> halt, return error

### Post-Operation Validation
- **After operations**: Show confirmation with task details
- **E1**: Claim code absent only after confirmed Read/Grep/git failure
- **E4**: Do NOT answer without reading relevant source files first
- **E5**: No "I assume", "I think", "probably" without tool verification

### Prohibited Actions
- Marking non-existent tasks
- Bulk ops without confirmation
- Creating separate task system
- Running CHS/CKS/scraper queries during default `/task list` (opt-in only)

## Integration

- **PostToolUse task tracker**: Persists task changes to file system
- **Session management**: Tasks survive compaction and restore
- **Unresolved suggester**: Disabled by default (opt-in via `/task list --suggest` or `/task scan`)
- **PreToolUse dispatch**: TaskCreate/TaskUpdate/TaskList/TaskGet (NOT bare "Task")
- **PreToolUse self-doc gate**: Blocks vague tasks (subject+description), fixes wrong param names

## Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| `scripts/task_receipt.py` | Write/read/list durable completion receipts | skill scripts dir |
| `scripts/task_verify.py` | Receipt-based bucket verifier + clean commands | skill scripts dir |
| `scripts/verify_completed.py` | DEPRECATED - subject-based verifier removed (FP) | skill scripts dir (shim) |
| `~/.claude/hooks/PreToolUse_task_self_doc_gate.py` | Blocks vague TaskCreate/TaskUpdate | hooks dir |
| `~/.claude/hooks/PreToolUse_task_done_evidence_gate.py` | Advisory nudge when completing without receipt | hooks dir |

## References

| File | Contents |
|------|----------|
| [implementation-details.md](references/implementation-details.md) | Sub-command workflows, tool API reference |
| [output-format.md](references/output-format.md) | Full output templates, status indicators |

## Why This Matters

Prevents task list chaos:
- Tasks accumulate without cleanup -> `/task clean`
- Lost track of pending -> `/task list --status pending`
- Completion verification is deterministic (receipt-based) -> `/task verify`
- Cheap default -> `/task list` does not burn CHS/CKS quota
