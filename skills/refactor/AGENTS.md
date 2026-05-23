# Agents

This document provides AI-readable context for refactor.

## What This Package Is

Multi-file refactoring with orchestration - discovers synergies and assigns tasks to agents.

## Package Type

`claude-plugin` — Claude Code plugin with skills for refactoring workflows.

## Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| refactor | /refactor | Multi-file refactoring orchestration |

## Hooks

| Hook | When | Purpose |
|------|------|---------|
| (none) | — | No hooks configured |

## Commands

| Command | Purpose |
|---------|---------|
| (none) | — | No commands configured |

## Key Files

| File | Purpose |
|------|---------|
| skills/refactor/SKILL.md | Skill definition |
| scripts/refactor_plan.py | Plan generation script |
| scripts/plan_review.py | Plan review script |
| scripts/code_scanner.py | Code scanning utility |
| .claude-plugin/plugin.json | Plugin manifest |

## Development Setup

```powershell
# Junction (Windows, no admin required)
# Point junction to WHERE SKILL.md lives:
#   - Plugin skills: skills/{skill-name}/SKILL.md → junction target: skills/{skill-name}/
#   - Standalone skills: skill/SKILL.md → junction target: skill/

# Sanitize name (remove @, ?, *, etc.)
$name = "refactor" -replace '[@?*:<>|+]', ''

New-Item -ItemType Junction -Path "$CLAUDE_ROOT/skills\$name" -Target "$CLAUDE_PLUGIN_ROOT/skills\refactor"
```

## Key Constraints

- Solo-dev environment: pragmatic solutions over enterprise patterns
- Plugin structure: `.claude-plugin/` + `scripts/` (NOT `src/`)
- All path references use `CLAUDE_PLUGIN_ROOT` for portability
- Junction target must point to the directory containing SKILL.md

## Workflow

1. `/refactor` — discover files, deduplicate, prioritize, plan, and execute refactoring

## Debugging

```powershell
# Check junction resolves correctly
Get-Item "$CLAUDE_ROOT/skills\refactor" | Select-Object LinkType, Target

# Check hooks directory for broken symlinks
Get-ChildItem P://.claude/hooks -Force | Where-Object { $_.LinkType -eq "SymbolicLink" -and -not (Test-Path $_.Target) }
```
