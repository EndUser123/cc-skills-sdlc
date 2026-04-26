---
name: code
version: 4.0.0
description: Single-task TDD implementation engine. Takes a task contract from /go, produces a task result. No loop, no review, no planning — /go owns all orchestration.
category: development
enforcement: strict
domain: development
depends_on:
  - sdlc: ">=0.1.0"
triggers:
  - 'code feature'
  - 'build feature'
  - 'new feature'
  - 'implement feature'
  - 'start development'
argument-hint: <task_description|stats|continue> [--fast] [--no-checklist]
context: main
user-invocable: true
status: new
depends_on_skills: ['/search']
requires_tools: ['python', 'git', 'pytest']
aliases:
  - '/code'
workflow_steps:
  - read_task
  - pre_execution_checklist
  - analyze_query_intent
  - explore_codebase
  - design_solution
  - tdd_red
  - tdd_green
  - tdd_refactor
  - smoke_validation
  - write_task_result
---

# /code v4.0 — Single-Task TDD Implementation Engine

## Purpose

Under `/go` as the outer delivery loop, `/code` is the inner implementation engine: **receive task → TDD → smoke-validate → produce result → done**.

`/go` owns all orchestration: worktree enforcement, task selection, loop control, simplify gating, 7-pass review, and PR artifact generation. `/code` runs ONE task to completion.

## Quick Start

```bash
# Task from /go (canonical path)
/code --task-file "active-task_{RUN_ID}.json"

# Direct use (for simple/standalone tasks)
/code "Add user authentication"

# Fast route (trivial changes)
/code "fix typo" --fast --no-checklist

# Stats mode
/code stats
```

## Input Contract

`/code` is designed to be called by `/go` via `--task-file`:

```
/code --task-file "active-task_{RUN_ID}.json"
```

The task file is JSON with schema `go.selected-task.v1`:
- `task_id`, `title`, `objective`
- `task_type`: implementation, refactor, design, planning
- `scope_in`, `scope_out`, `forbidden_files`
- `acceptance_criteria`, `verification_hint`
- `candidate_routes`: hint for routing decision

If `--task-file` is not provided, falls back to direct argument or session context (for standalone use).

## Output Contract

After completion, `/code` produces `task-result_{RUN_ID}.json`:

```json
{
  "schema_version": "go.task-result.v1",
  "go_run_id": "...",
  "task_id": "...",
  "route": "code",
  "status": "completed|blocked|failed",
  "tdd_phases": {
    "red": true,
    "green": true,
    "refactor": true
  },
  "smoke_validated": true,
  "verification_results": [...],
  "artifacts_produced": [...],
  "blocked_by": [...],
  "completed_at": "ISO8601"
}
```

## Core Workflow

1. **Read task** — load `--task-file` or argument, parse objective and scope
2. **Pre-execution checklist** — verify intent clarity, context readiness
3. **Explore** — understand codebase relevant to task
4. **Design** — solution approach (minimal, no pre-mortem, no GoT)
5. **TDD RED** — write failing test for acceptance criteria
6. **TDD GREEN** — implement minimal code to pass test
7. **TDD REFACTOR** — clean up without changing behavior
8. **Smoke validation** — prove implementation works
9. **Done** — write `task-result_{RUN_ID}.json` and emit completion token

**No loop. No review. No planning inside.** If task is ambiguous, route back to `/planning` — don't guess.

## Key Flags

| Flag | Effect |
|------|--------|
| `--fast` | Skip ceremony, minimum viable route |
| `--no-checklist` | Skip pre-execution checklist |
| `--task-file` | Path to `active-task_{RUN_ID}.json` from `/go` |

Removed from v3.0: `--ralph-*`, `--no-loop` (loop belongs to `/go`), `--got`, `--tot`, `--full`, `--interactive`.

## What /go delegates to /code

| Delegation | What /code does |
|-----------|----------------|
| Route: `implementation` | Run TDD RED → GREEN → REFACTOR |
| Route: `refactor` | Behavior-preserving cleanup via TDD |

## What /code does NOT do (belongs to /go)

- **Worktree enforcement** — `/go` PreToolUse hook enforces
- **Task selection** — `/go` selects one task per RUN_ID
- **Loop control** — single-task by default, no autonomous iteration
- **Simplify gating** — `/go` runs simplify after `/code` completes
- **7-pass review** — `/go` runs this after `/code` completes
- **PR artifact generation** — `/go` handles this
- **GoT/ToT planning** — belongs to `/planning`
- **Multi-task plan parsing** — `/go` handles task queue

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **TDD mandatory**: All code changes follow RED → GREEN → REFACTOR
- **Evidence-based**: Verify each phase before proceeding

### Technical Context
- **Input**: `active-task_{RUN_ID}.json` (from `/go`)
- **Output**: `task-result_{RUN_ID}.json` (to `/go`)
- **State dir**: `.claude/.artifacts/{TERMINAL_ID}/go/`

## Pre-Execution Checklist

Before starting, answer 5 questions:
1. Do I understand what "done" looks like?
2. Do I know where the relevant code lives?
3. Is the scope clear and bounded?
4. Do I need `/search` or `/explore` first?
5. Are there existing tests that cover this area?

**Opt-out:** `--no-checklist` (for `--fast` or continued work).
