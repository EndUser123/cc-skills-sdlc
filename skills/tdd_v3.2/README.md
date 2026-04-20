# TDD Skill

Test-Driven Development workflow enforcement for Claude Code.

## Migration Plan

**Plan:** [twinkly-soaring-sunbeam.md](twinkly-soaring-sunbeam.md) - TDD Hook Migration to Skill-Based Hooks with Terminal Isolation

## Overview

The `/tdd` skill enforces proper Test-Driven Development workflow with intent detection:
1. **Write test first** (RED phase)
2. **Write implementation** (GREEN phase)
3. **Refactor** (REFACTORING phase)

## Intent Detection

`/tdd` automatically detects the work type from your input:

| Pattern | Intent | Workflow Variant |
|---------|--------|------------------|
| "fix X", "bug in X", "X broken", "X error", "X crash" | Bug fix | Bug-fixing workflow (see below) |
| "implement X", "add feature X", "new feature" | New feature | Full RED→GREEN→REFACTOR |
| "refactor X", "simplify X", "reduce complexity" | Refactoring | Refactoring workflow |

## Bug-Fixing Workflow

When intent = "bug fix" (detected from "fix", "bug", "broken", "error", "crash"):

### Bug-Fixing Constraints

- **YAGNI**: Fix the actual bug, don't add "defensive" code for hypothetical scenarios
- **Data vs Logic**: If the bug is environmental (missing file, auth), recommend operational fix, not code workaround

### Workflow Adaptations

| Phase | Bug Fix Adaptation |
|-------|-------------------|
| DISCOVER | If error provided, grep for error location; if regression, suggest git bisect |
| RED | If test exists: verify test fails, proceed to GREEN; if no test: write regression test |
| GREEN | Fix ONLY the reported bug (YAGNI constraint) |
| VERIFY | Run actual command with bug reproduction |
| REGRESSION | Run related tests |
| CLOSURE | Search/Grep to ensure NO other instances remain |

### Closure Protocol

After GREEN phase for bug fixes:
```bash
# Search for similar patterns that might have the same bug
grep -r "PATTERN" --include="*.py" | grep -v "test_"
```

Report findings to ensure complete fix.

## Architecture

- **State isolation**: Terminal-specific state directories prevent cross-terminal collision
- **No caching**: Direct file reads prevent cross-process stale state
- **Skill-based hooks**: PreToolUse, PostToolUse, and SessionEnd hooks manage TDD lifecycle

## Hooks

| Hook | Purpose |
|------|---------|
| `PreToolUse_tdd_gate.py` | Blocks invalid phase transitions |
| `PostToolUse_tdd_state.py` | Tracks phase changes after tool execution |
| `SessionEnd_tdd_cleanup.py` | Cleans up expired state files |

## Usage

Invoke `/tdd` to start a TDD cycle. The skill will guide you through:
- Writing failing tests
- Implementing to make tests pass
- Refactoring while keeping tests green

**Examples:**
```
/tdd implement search by channel name
/tdd memory leak in download handler
/tdd simplify function_name
```

## Implementation Details

See [twinkly-soaring-sunbeam.md](twinkly-soaring-sunbeam.md) for complete architecture documentation and migration rationale.
