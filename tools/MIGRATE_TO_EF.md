# migrate_to_ef.py

Purpose-built migration utility for the evidence-first (`-ef`) skill naming rollout.

## What it does

Creates new `*-ef` skill directories non-destructively, wired to the shared `enforce/` layer, without touching the original skill.

## Why `-ef`

Numeric version suffixes (`code_v4.0`, `go_v3.0`) were an experimental convention. The `-ef` suffix signals that a skill uses the **evidence-first methodology**: hard gates only exist when backed by concrete, machine-checkable evidence (ledger entries, flag files, JSON artifacts, command exit codes). Advisory phases without real evidence are placeholders and never produce warnings.

## How to use

```bash
# Dry run (no changes)
python tools/migrate_to_ef.py --base refactor --dry-run
python tools/migrate_to_ef.py --base planning --dry-run

# Apply
python tools/migrate_to_ef.py --base refactor
python tools/migrate_to_ef.py --base planning --target planning-ef

# Force overwrite (existing target)
python tools/migrate_to_ef.py --base refactor --force
```

## Arguments

| Flag | Description |
|------|-------------|
| `--base` | Base skill name (required) |
| `--target` | Target name (default: `{base}-ef`) |
| `--source` | Override source skill path |
| `--dry-run` | Print plan, no filesystem changes |
| `--force` | Allow overwrite of existing target |
| `--no-validate` | Skip `-ef` naming validation |

## What gets created

For each migration:
- `skills/{target}/SKILL.md` — updated frontmatter (name, version → 1.0.0, enforcement → strict, triggers rewritten)
- `skills/{target}/hooks/Stop_enforce_gate.py` — thin hook: `skill_id = "{target}"`, calls `enforce/stop_gate.py`
- `enforce/configs/__init__.py` — config entry with advisory phases derived from source `workflow_steps`

## Evidence policy

> Hard gates require robust evidence. Stub configs default all phases to `advisory`. Do not invent hard gates for migrated skills — wire real evidence before promoting phases to hard.

To promote phases from advisory to hard, add concrete evidence to the phase config:
- `ledger_only` — ledger entry written by a PreToolUse/PostToolUse hook
- `file_flag` — a flag file written at phase completion
- `json_file` — a JSON artifact with a specific key/value
- `command` — a command that exits 0 on success

## Example migrations

```bash
# refactor → refactor-ef
python tools/migrate_to_ef.py --base refactor

# planning → planning-ef
python tools/migrate_to_ef.py --base planning

# Custom target (bypasses -ef validation)
python tools/migrate_to_ef.py --base planning --target custom-ef --no-validate
```
