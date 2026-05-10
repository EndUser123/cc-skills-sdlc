---
title: "Skill-Guard Enforcement: Removing the Registry Shim"
date: 2026-04-14
tags: [skill-guard, hooks, enforcement, architecture]
source: /rca chat session
summary: "Removed brittle SKILL_EXECUTION_REGISTRY hardcoded map; replaced with declarative required_first_command_patterns in SKILL.md. Added advisory warnings for workflow skills missing this metadata."
relations:
  - target: wiki/concepts/skill-guard
    type: related
  - target: wiki/concepts/pretooluse-gate
    type: related
---

# Skill-Guard Enforcement: Removing the Registry Shim

## What Happened

When `/yt-is` was invoked and `csf-source list` was run *before* `csf-source sync`, no hook blocked the workflow deviation. The user investigated via `/rca` and discovered the root cause: a brittle hardcoded map called `SKILL_EXECUTION_REGISTRY` in `StopHook_skill_execution_gate.py`.

## Root Cause

The `SKILL_EXECUTION_REGISTRY` was a runtime Python dictionary mapping skill names to enforcement rules. It existed as a **compatibility shim** because:

1. Skills didn't declare machine-readable enforcement metadata in their SKILL.md files
2. The hook needed a quick way to decide which slash commands were enforceable
3. Someone hardcoded skill names and patterns as a stopgap

Problems with this approach:
- **Drift**: When a skill changed, nobody updated the map
- **Incomplete**: Only skills someone remembered to hardcode were enforced
- **Brittle**: Could not express nuanced workflows like "sync before list" for yt-is
- **Not authoritative**: Duplicated policy that already lives in skill files

## The Fix

### 1. Removed the registry shim

Deleted `SKILL_EXECUTION_REGISTRY` and the special-case branch that treated "not in registry" as an LLM-only skill bypass.

### 2. Made SKILL.md the source of truth

Added two new frontmatter fields to skill files:

```yaml
required_first_command_patterns:
  - tool: Bash
    command: "csf-source sync*"
    hint: "Run csf-source sync first to pull latest industrial triage data"
```

This declarative approach:
- Lives with the skill definition (no drift)
- Self-documenting (hint appears in enforcement messages)
- Expresses nuance (tool + command pattern + hint)

### 3. Added advisory warnings for undeclared workflow skills

If a skill has `workflow_steps` but no `required_first_command_patterns`, an advisory warning is emitted:

> Missing required_first_command_patterns for a workflow skill; the first backend command will not be enforced.

This surfaces without blocking execution, so operators can identify which skills need hardening.

### 4. Updated PreToolUse gate to validate first commands

Added first-command validator in `PreToolUse_skill_pattern_gate.py` that:
- Checks if the skill being invoked has `required_first_command_patterns`
- Validates the first backend tool against the pattern
- Blocks with a hint if the wrong command is used first

## Skills Now Hardened

| Skill | First Command Enforced |
|-------|----------------------|
| `git` | `python P:\\\\\\.claude/skills/git/sync.py ...` |
| `gto` | `python P:\\\\\\.claude/skills/gto/gto_orchestrator.py ...` |
| `yt-is` | `csf-source sync` |
| `yt-nlm` | `nlm login --check` |
| `yt-selenium` | `python -m csf.csf_selenium` |
| `yt-dlp` | `yt-dlp` |

## Design Principles Applied

1. **Declarative over hardcoded**: SKILL.md is authoritative, not runtime maps
2. **Skill-owned contracts**: Each skill declares its own enforcement rules
3. **Generic gate, specific declarations**: PreToolUse validates patterns; skills provide them
4. **Advisory over blocking for gaps**: Warning rather than hard block for missing metadata

## Verification

```bash
python -m pytest P:\\\\\\packages\skill-guard\tests\test_PreToolUse_skill_pattern_gate.py \
  P:\\\\\\packages\skill-guard\tests\test_frontmatter_validation.py \
  P:\\\\\\packages\skill-guard\tests\test_tracker_fixes.py -q
# Result: 28 passed
```

## Corrections

### Session metadata gap claim (2026-04-14)

An earlier analysis of this session claimed there was "no dedicated helper function" returning session metadata (session_id, transcript_path). This was **incorrect**.

The `evidence_store.py` already provides:
- `write_session_context(session_id, terminal_id)` — stores session context in a SQLite table
- `session_context` table in the evidence store

A `get_session_context()` helper could still be useful for reconciling multiple sources of session metadata (env var `CLAUDE_SESSION_ID`, handoff JSON `source_session_id`, hook input `transcript_path`), but this is a gap-filling convenience, not a missing primitive.

Grep confirmed `currentTurn` does not exist in the codebase — that part of the gap claim was accurate.

## Related

- [[skill-guard]] — Hook enforcement system
- [[pretooluse-gate]] — Pre-tool validation gate
- [[hooks-architecture]] — Hook system design