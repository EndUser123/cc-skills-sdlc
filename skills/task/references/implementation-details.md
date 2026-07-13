# Implementation Details

## How This Skill Works

When you invoke `/task <command>`, the following occurs:
1. **Skill tool loads this SKILL.md** - The markdown documentation IS the handler
2. **Claude parses your sub-command** - Extracts the operation (list/add/done/start/scan/search/verify/clean/help)
3. **Claude executes the appropriate tool(s)** - Calls TaskList/TaskCreate/TaskUpdate/TaskGet directly (NOT bare "Task")
4. **Optional receipt write** - `/task done` writes a durable receipt via `scripts/task_receipt.py`
5. **Results are formatted and returned** - You see the output

**There is no separate Python handler file** - This SKILL.md document IS the implementation. Claude reads this file and follows the described workflow.

## Sub-Command Workflows

### List Tasks (Cheap Default, Opt-In Suggestion Mode)

```
1. User: /task list [--status=pending] [--all] [--suggest]
2. Claude: Reads this SKILL.md, identifies "list" command
3. Claude: Calls TaskList() tool (no CHS/CKS by default)
4. Claude: Filters tasks by terminal_id unless --all flag specified
5. Claude: Filters by status if --status specified
6. Claude: If --suggest: runs opt-in search + unresolved detection
7. Claude: Formats compact output (no large descriptions)
```

**Quota-saving design:** Default `/task list` is a single TaskList() call. No CHS/CKS/search/suggestions. Use `--suggest` or `/task scan` for enriched output.

### Terminal Filtering (Default Behavior)
- By default, `/task list` shows only tasks for current terminal (extract from task file name)
- Use `--all` flag to show all terminals

### Add Task
```
1. User: /task add "Fix authentication bug"
2. Claude: Reads this SKILL.md, identifies "add" command
3. Claude: Validates subject is not empty
4. Claude: Calls TaskCreate(subject="Fix authentication bug", status="pending")
5. Claude: Returns confirmation with task ID
```

### Complete Task (with Receipt)
```
1. User: /task done 123 --verify "pytest -q"
2. Claude: Calls TaskUpdate(taskId="123", status="completed")
3. Claude: Runs scripts/task_receipt.py write --task-id 123 --verify "pytest -q"
4. Claude: Returns confirmation with receipt evidence_class
```

### Verify Completed Tasks (Receipt-Based)
```
1. User: /task verify [ids...]
2. Claude: Calls scripts/task_verify.py verify [ids...]
3. Claude: Reports VERIFIED / REVIEW / NO_EVIDENCE / STALE / BLOCKED buckets
4. Exit code 0 = all VERIFIED. 1 = at least one non-VERIFIED.
```

### Clean (Safe, Receipt-Gated)
```
1. User: /task clean [ids...] [--apply]
2. Claude: Calls scripts/task_verify.py clean [ids...] [--apply]
3. Only VERIFIED-receipt tasks are emitted as native deletion candidates; the script never mutates the tracker mirror. The caller issues native `TaskUpdate(status="deleted")`, then verifies absence with `TaskList`.
4. Receipts are preserved. Dry-run by default.
```

## Tool Reference

```python
# List tasks
tasks = TaskList()
for task in tasks:
    print(f"#{task['id']} [{task['status']}] {task['subject']}")

# Create task
TaskCreate(
    subject="Fix bug",
    description="Details...",
    status="pending"
)

# Update task
TaskUpdate(
    taskId="123",
    status="completed"
)

# Get specific task
task = TaskGet(taskId="123")
```

## Integration Points

- **TaskCreate/TaskUpdate/TaskList/TaskGet**: Native tools (NOT "Task" which does not exist)
- **PostToolUse task tracker**: Persists task changes to file system (`P:/.claude/state/task_tracker/`)
- **Session management**: Tasks survive compaction and restore
- **Completion receipts**: `P:/.claude/state/task_receipts/{terminal_id}/{task_id}.json` (deterministic verification)
- **Unresolved suggester**: Disabled by default (opt-in via env var TASK_UNRESOLVED_SUGGEST_ENABLED or `/task list --suggest`)
- **PreToolUse self-doc gate**: Blocks vague TaskCreate/TaskUpdate at the hook layer
- **PreToolUse done-evidence gate**: Advisory nudge when completing without a receipt (non-blocking)

## PreToolUse Dispatch (Real Tool Names)

The PreToolUse router has been updated to use the actual Claude tool names:

| Tool | Hooks | 
|------|-------|
| TaskCreate | PreToolUse_task_self_doc_gate.py |
| TaskUpdate | PreToolUse_task_self_doc_gate.py, PreToolUse_task_done_evidence_gate.py |
| TaskList | (no PreToolUse gates) |
| TaskGet | (no PreToolUse gates) |
