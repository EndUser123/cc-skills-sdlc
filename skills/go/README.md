# /go - Evidence-First SDLC Orchestrator

Thin orchestrator that stays on `main`. Acquires tasks, dispatches through selected mode, enforces quality gates, and records outcomes.

## Purpose

`/go` is the **delivery loop** for bounded SDLC tasks. It does NOT replace `/code` TDD workflow, `/refactor` cleanup logic, or `/planning` task breakdown — it orchestrates them.

## Core Sequence

Worktree Check → Task Selection → Classify → Dispatch → Verify → Simplify → 7-Pass Review → QA Verification → Mutation Gate (critical-path) → PR Artifacts → Loop Check

## Dispatch Modes

| Mode | Behavior |
|------|----------|
| `pi` | External pi harness via `pi -p --mode json --model <resolved>` |
| `local` | No worker; runs verification/review/artifact gates against current checkout |
| `claude` | Blocked with `unsupported-automated-dispatch` |

## Required Environment

```bash
export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${GO_RUN_ID:-$(uuidgen)}"
export GO_STATE_DIR="${CLAUDE_PROJECT_DIR:-P:/}.claude/.artifacts/${TERMINAL_ID}/go"
mkdir -p "$GO_STATE_DIR"
```

## Professional SDLC Enhancements (v2.0.0)

### Quality Gates
- **coverage-gate.py**: Enforces minimum test coverage (default 80%)
- **regression-runner.py**: Baseline comparison with tolerance support
- **refactor-review.py**: Analyzes git diff for API surface changes

## Usage

```bash
/go "fix the failing tests"
/go --dispatch pi "fix the failing tests"
/go --dispatch local "verify config-only changes"
```

## Completion Tokens

- `<promise>PR_READY</promise>` — task done, all gates passed, artifacts written
- `<promise>BLOCKED</promise>` — task cannot proceed or max attempts reached
- `<promise>MORE_TASKS_IN_PLAN</promise>` — current task done, more remain
- `<promise>ALL_TASKS_COMPLETE</promise>` — no eligible tasks remain

## State Root

`.claude/.artifacts/{TERMINAL_ID}/go/`

## See Also

- `SKILL.md` — Full contract and workflow details
- `GO-QUICK-REFERENCE.md` — Quick command reference
- `IMPLEMENTATION-GUIDE.md` — Implementation patterns
- `ROUTING.md` — Routing table details