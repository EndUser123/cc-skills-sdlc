# /go Gen 2 Implementation Guide

This is the second-generation redesign of `/go`.

Gen 1 used:
- markdown task contracts
- diff-based review-depth logic
- `plan.md` as loop source of truth
- older wrapper assumptions

Gen 2 replaces that with:
- canonical JSON contracts
- one selected task per `RUN_ID`
- `/go -> /code` orchestration
- artifact-driven verification and plan progression

---

## Deliverables

This Gen 2 bundle consists of:

1. `SKILL.md`
2. `scripts/orchestrate.py` (canonical runtime)
3. `ralph-go-loop.sh`
4. `GO-QUICK-REFERENCE.md`
5. `IMPLEMENTATION-GUIDE.md`
6. `active-plan.json` starter file

---

## Design Goal

The goal is to make `/go` deterministic, machine-readable, interruption-safe, and multi-terminal safe.

Core properties:

- per-terminal isolation via `.claude/.artifacts/{TERMINAL_ID}/go/`
- per-task isolation via one `RUN_ID` per selected task
- exact task boundary via `active-task_{RUN_ID}.json`
- exact execution result via `task-result_{RUN_ID}.json`
- loop continuation based on updated plan state, not markdown prose

---

## Gen 2 Architecture

### Source of truth

`active-plan.json` is the scheduler source of truth.

It replaces:
- `plan.md`
- ad hoc task discovery
- git-diff-based task interpretation

### Task execution model

Each `/go` run:

1. validates worktree and plan
2. selects exactly one eligible task
3. writes `active-task_{RUN_ID}.json`
4. dispatches `/code`
5. requires `task-result_{RUN_ID}.json`
6. verifies evidence
7. runs simplify
8. runs all review passes
9. writes local PR artifacts
10. updates `active-plan.json`

### Loop execution model

Each Ralph loop session:

- keeps one `TERMINAL_ID`
- creates a new `RUN_ID` per cycle
- reevaluates `active-plan.json` after each completed task

---

## Canonical Contracts

### 1. `active-plan.json`

This file drives scheduling.

Each task must define:

- `task_id`
- `title`
- `status`
- `priority`
- `depends_on`
- `objective`
- `scope`
- `allowed_files`
- `forbidden_files`
- `acceptance_criteria`
- `verification_commands`

### 2. `active-task_{RUN_ID}.json`

This file is the frozen task contract for a single run.

It must include:

- `run_id`
- `terminal_id`
- `task_id`
- `title`
- `objective`
- `scope`
- `allowed_files`
- `forbidden_files`
- `acceptance_criteria`
- `verification_commands`
- `selected_at`
- `status`

### 3. `task-result_{RUN_ID}.json`

This file is required output from `/code`.

It must include:

- `run_id`
- `task_id`
- `status`
- `summary`
- `changed_files`
- `commands_executed`
- `verification_evidence`
- `blockers`
- `notes`
- `completed_at`

---

## File Replacements

### `SKILL.md`

Replace the Gen 1 skill with the Gen 2 skill definition.

Required differences from Gen 1:

- remove `task-contract_{RUN_ID}.md`
- remove diff classification step
- remove `plan.md` loop semantics
- add `active-plan.json`
- add `active-task_{RUN_ID}.json`
- add `task-result_{RUN_ID}.json`
- add `/go -> /code` dispatch model

### `orchestrate.py` (canonical runtime)

Replace the wrapper so it:

- validates worktree
- validates `active-plan.json`
- previews next eligible task
- writes `.env_{RUN_ID}`
- invokes `/go`
- prints selected-task and task-result artifacts

### `ralph-go-loop.sh`

Replace the loop driver so it:

- keeps one `TERMINAL_ID`
- creates a new `RUN_ID` per cycle
- reads `active-plan.json` before each cycle
- uses artifact state as authoritative truth
- rereads `active-plan.json` after each cycle
- exits on `BLOCKED`
- exits on `ALL_TASKS_COMPLETE`

### Docs

Replace both docs so they no longer mention:

- markdown task contracts
- diff-based review depth
- `plan.md`
- one-`RUN_ID`-per-session loop behavior

---

## Installation Order

Do these in order:

1. replace `SKILL.md`
2. invoke `scripts/orchestrate.py`
3. replace `ralph-go-loop.sh`
4. replace `GO-QUICK-REFERENCE.md`
5. replace `IMPLEMENTATION-GUIDE.md`
6. create `active-plan.json`
7. run smoke test

---

## Starter Plan Location

Place the starter plan here:

```text
.claude/.artifacts/{TERMINAL_ID}/go/active-plan.json
```

This must exist before `scripts/orchestrate.py` runs.

---

## Smoke Test

### Manual

```bash
python scripts/orchestrate.py --help
```

Confirm:

- worktree validation passes
- plan preview appears
- `active-task_{RUN_ID}.json` is written
- `task-result_{RUN_ID}.json` is written
- `.pr-ready_{RUN_ID}` exists for successful completion

### Ralph loop

```bash
bash ralph-go-loop.sh 10
```

Confirm:

- same `TERMINAL_ID` across loop
- new `RUN_ID` each cycle
- plan state updates after each cycle
- `MORE_TASKS_IN_PLAN` appears when tasks remain
- `ALL_TASKS_COMPLETE` appears when plan drains

---

## Failure Conditions

Treat these as hard failures:

- invalid git worktree state
- running on `main` or `master`
- missing `active-plan.json`
- invalid `active-plan.json`
- no eligible task when one is expected
- missing or invalid `active-task_{RUN_ID}.json`
- missing or invalid `task-result_{RUN_ID}.json`
- forbidden file changes
- failed verification commands
- unresolved HIGH/CRITICAL simplify result
- any review pass marked `REVIEW_REQUIRED`

---

## Migration Notes From Gen 1

If you previously installed the Gen 1 artifact-pattern bundle, the main conceptual migrations are:

| Gen 1 | Gen 2 |
|------|-------|
| `task-contract_{RUN_ID}.md` | `active-task_{RUN_ID}.json` |
| `plan.md` | `active-plan.json` |
| verification from markdown task contract | verification from selected-task + task-result JSON |
| diff-classified review depth | fixed structured task contract |
| one loop session may reuse one run model | each task cycle gets a new `RUN_ID` |

Do not mix the two models in the same active installation.

---

## Recommended Test Tasks

Use three starter tasks:

1. replace `SKILL.md`
2. invoke `scripts/orchestrate.py`
3. replace `ralph-go-loop.sh`

This validates:
- plan selection
- single-task execution
- loop continuation
- per-task `RUN_ID` behavior

---

## Operator Guidance

If you are debugging Gen 2, inspect in this order:

1. `active-plan.json`
2. `active-task_{RUN_ID}.json`
3. `task-result_{RUN_ID}.json`
4. `verification-results_{RUN_ID}.txt`
5. `simplify-status_{RUN_ID}.md`
6. review-pass files
7. `pr-ready_{RUN_ID}.md`

This order follows the actual control flow.

---

## Final Rule

Do not keep extending Gen 1 assumptions inside Gen 2 files.

If a file still depends on:
- `task-contract_{RUN_ID}.md`
- diff classification
- `plan.md`
- one `RUN_ID` per full loop session

then it is not migrated yet.
