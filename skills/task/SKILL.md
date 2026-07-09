---
name: task
description: Task orchestration - manage Claude Code task list
workflow_steps: []
---
# /task - Task Orchestration

## Purpose

Orchestrator for Claude Code task list operations. Routes sub-commands to built-in TaskCreate/TaskUpdate/TaskList/TaskGet tools.

## Context

- **Solo-dev**: Task management for individual workflow, not team coordination
- **Tool-first**: Wraps built-in tools, not a replacement system
- **Evidence-based**: Task status reflects actual work, not aspirations
- **Persistence**: `.claude/state/task_tracker/{terminal_id}_tasks.json` via PostToolUse_task_tracker hook
- **Multi-terminal safe**: Tasks persist across compaction and sessions
- **No Python handler**: This SKILL.md IS the implementation

## Phase 1: Workflow (Generation Only)

1. **Parse sub-command** - Extract first argument as operation
2. **Route to handler** - Delegate to appropriate implementation
3. **Execute tool** - Call built-in tool (TaskCreate/TaskUpdate/etc)
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

## Phase 2: Validation (Validation Only)

### Pre-Route Validation

- **Before routing**: Validate sub-command exists
- **STOP**: Unknown sub-command → halt, show usage

### Pre-Create Validation

- **Before task creation**: Check subject is not empty
- **STOP**: Empty subject → halt, return error

### Pre-Update Validation

- **Before task update**: Verify task ID exists
- **STOP**: Non-existent task ID → halt, return error

### Post-Operation Validation

- **After operations**: Show confirmation with task details
- **E1**: Claim code absent only after confirmed Read/Grep/git failure
- **E4**: Do NOT answer without reading relevant source files first
- **E5**: No "I assume", "I think", "probably" without tool verification

### Prohibited Actions

- Marking non-existent tasks
- Bulk ops without confirmation
- Creating separate task system

## Usage

```bash
/task list                     # Tasks for current terminal (default)
/task list --all               # All terminals
/task list --status pending    # Filter by status
/task list --no-suggest        # Skip search suggestions

/task add "Fix auth bug"                  # Create task
/task add "Dark mode" --priority high     # With priority
/task start 123                           # Begin work
/task done 123                            # Complete
/task search "authentication"             # Search
/task verify                              # Check completed tasks have real evidence
/task clean                               # Remove completed (run verify first)
```

## Output Quick Reference

**Task format:** `#<id> [<status>] <subject> [owner=<owner>] [blockedBy=<ids>]`

**Status indicators:** `[pending]` / `[in_progress]` / `[completed]`

**List output includes:**
- Pending tasks for current terminal
- Suggested items (CKS/CHS search results) -- unless `--no-suggest`
- Unresolved chat history items with quick-add prompts -- unless `--no-suggest`

## References

| File | Contents |
|------|----------|
| [implementation-details.md](references/implementation-details.md) | Sub-command workflows, daemon status check, tool API reference |
| [output-format.md](references/output-format.md) | Full output templates, status indicators, suggestion formats |
| [search-integration.md](references/search-integration.md) | Terminal context building, CHS unresolved detection, search execution flow |

## Integration

- **PostToolUse_task_tracker.py**: Persists task changes to file system
- **Session management**: Tasks survive compaction and restore
- **Unified search**: Uses /search skill for contextual suggestions (see references/search-integration.md)

## Why This Matters

Prevents task list chaos:
- Tasks accumulate without cleanup -> `/task clean`
- Lost track of pending -> `/task list --status pending`
- No quick way to create -> `/task add "subject"`
- Completed tasks assumed done without evidence -> `/task verify` before `/task clean`

## /task verify — Evidence Check Before Deletion

**Purpose:** prove completed tasks have real evidence (file / commit / pickaxe / grep) before `/task clean` deletes them. Catches phantom completions where status says "completed" but no code/commit backs it.

**Workflow:**
1. Get completed tasks: `TaskList()` → filter `status == "completed"`
2. Write to temp file: `#ID. [completed] subject` per line at `P:/tmp/completed_tasks.txt`
3. Run: `python "$CLAUDE_PLUGIN_ROOT/skills/task/scripts/verify_completed.py" P:/tmp/completed_tasks.txt`
4. Report the script's three buckets verbatim — do NOT collapse them

**Output — three buckets (honesty contract):**

| Bucket | Means | Deletion safe? |
|--------|-------|----------------|
| VERIFIED | Evidence found (file/commit/pickaxe/grep matched) | Yes |
| UNVERIFIED | A signal was extracted and searched, no match | **No** — probably done but unproven; manual check |
| NO_SIGNAL | Subject too vague to auto-extract | **No** — manual or LLM judgment |

**Mandatory:** UNVERIFIED is NOT "done." Do not report "all completed tasks verified" when UNVERIFIED > 0. State the exact counts of all three buckets. The script exits non-zero if any UNVERIFIED/NO_SIGNAL remain — surface that, don't mask it.

**Recommended next step after verify:** `/task clean` is safe for VERIFIED tasks. For UNVERIFIED/NO_SIGNAL, spot-check manually (or run targeted greps with hand-tuned signals) before deleting.
