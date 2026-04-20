---
name: go
version: 3.1.0
description: Thin SDLC orchestrator that selects one task, routes to planning/design_v1.1/code/refactor, and records canonical per-terminal orchestration state.
category: execution
enforcement: blocking
triggers:
  - '/go'
aliases:
  - '/go-v3'
  - '/go-router'
  - '/execute-next-task'
workflow_steps:
  - initialize_orchestrator_state
  - worktree_enforcement
  - select_task
  - classify_route
  - dispatch_skill
  - capture_outcome
  - emit_next_action
suggest: []
---

# /go — SDLC Orchestrator v3.1

**ROLE:** `/go` is a **thin orchestrator**, not a replacement for `/planning`, `/design_v1.1`, `/code`, or `/refactor`.

**MANDATORY SEQUENCE:** Initialize → Worktree Check → Select Task → Route Task → Dispatch Existing Skill → Capture Outcome → Emit Next Action

**CANONICAL STATE PATTERN:** `.claude/.artifacts/{TERMINAL_ID}/go/`

**NON-NEGOTIABLE RULE:** `/go` owns orchestration state only.
It MUST NOT duplicate or replace the internal workflow logic of:
- `/planning`
- `/design_v1.1`
- `/code`
- `/refactor`

Those skills remain authoritative for their own execution, gates, evidence, and validation.

---

## Core Contract

`/go` is responsible for exactly five things:

1. Select exactly one task.
2. Normalize that task into a canonical task record.
3. Decide which existing SDLC skill should handle it.
4. Invoke that skill.
5. Record the outcome and next state.

`/go` is NOT responsible for:
- replacing `/code` TDD or evidence ledger
- replacing `/refactor` discovery/RED/regression logic
- replacing `/planning` plan synthesis or adversarial review
- replacing `/design_v1.1` validation or ADR gating
- remote git push/deploy
- hidden multi-step autonomous execution across several tasks in one untracked leap

---

## Completion Tokens

`/go` MUST end each run with exactly one orchestration result token:

- `<promise>GO_DISPATCHED</promise>` — task selected and routed successfully
- `<promise>TASK_COMPLETE</promise>` — delegated skill completed and task is done
- `<promise>TASK_BLOCKED</promise>` — delegated skill or route precondition blocked task
- `<promise>AWAITING_SKILL_OUTPUT</promise>` — dispatch occurred, outcome not yet confirmed
- `<promise>MORE_TASKS_REMAIN</promise>` — current task resolved, queue still has pending work
- `<promise>NO_TASKS_AVAILABLE</promise>` — no eligible task found

---

## Required Environment

Before doing anything else, ensure:

```bash
export CLAUDE_TERMINAL_ID="${CLAUDE_TERMINAL_ID:-$(uuidgen | cut -d'-' -f1)}"
export GO_RUN_ID="${GO_RUN_ID:-$(uuidgen)}"
export GO_ARTIFACT_DIR="${CLAUDE_CODE_ARTIFACTS_DIR:-.claude/.artifacts}/${CLAUDE_TERMINAL_ID}/go"
mkdir -p "$GO_ARTIFACT_DIR"
```

If `CLAUDE_TERMINAL_ID` already exists for the current terminal/session, reuse it.
Do NOT generate a new terminal ID mid-session.

---

## Artifact Files

All files for this `/go` run live under:

```text
.claude/.artifacts/{TERMINAL_ID}/go/
```

### Required files for every run

- `run_{GO_RUN_ID}.json`
- `selected-task_{GO_RUN_ID}.json`
- `dispatch-decision_{GO_RUN_ID}.json`
- `dispatch-result_{GO_RUN_ID}.json`
- `next-action_{GO_RUN_ID}.md`

### Optional files

- `task-source-snapshot_{GO_RUN_ID}.md`
- `blocked-reason_{GO_RUN_ID}.md`
- `skill-output-summary_{GO_RUN_ID}.md`

### Required flags

- `.initialized_{GO_RUN_ID}`
- `.worktree-ready_{GO_RUN_ID}`
- `.task-selected_{GO_RUN_ID}`
- `.routed_{GO_RUN_ID}`
- `.dispatched_{GO_RUN_ID}`
- `.completed_{GO_RUN_ID}`
- `.blocked_{GO_RUN_ID}`

Only create flags that are true.
Never create both `.completed_{GO_RUN_ID}` and `.blocked_{GO_RUN_ID}`.

---

## Step 0: Initialize Orchestrator State

**Creates:** `run_{GO_RUN_ID}.json`, `.initialized_{GO_RUN_ID}`

Create `run_{GO_RUN_ID}.json`:

```json
{
  "go_run_id": "{GO_RUN_ID}",
  "terminal_id": "{CLAUDE_TERMINAL_ID}",
  "status": "initialized",
  "created_at": "ISO-8601",
  "skill_version": "3.1.0",
  "orchestrator_role": "thin-router",
  "artifact_dir": ".claude/.artifacts/{TERMINAL_ID}/go"
}
```

Then create:

```bash
touch "$GO_ARTIFACT_DIR/.initialized_${GO_RUN_ID}"
```

---

## Step 1: Worktree Enforcement

**Precondition:** `.initialized_{GO_RUN_ID}`
**Creates:** `.worktree-ready_{GO_RUN_ID}` or `.blocked_{GO_RUN_ID}` + `blocked-reason_{GO_RUN_ID}.md`

Run:

```bash
CURRENT_BRANCH="$(git branch --show-current)"
IN_WORKTREE="$(git worktree list --porcelain | grep -F "$(pwd)" -q && echo true || echo false)"
```

### Gate rules

Fail if any are true:
- current directory is not a git worktree
- current branch is `main` or `master`
- worktree state is ambiguous

On success:

```bash
touch "$GO_ARTIFACT_DIR/.worktree-ready_${GO_RUN_ID}"
```

If blocked, write `blocked-reason_{GO_RUN_ID}.md`, create `.blocked_{GO_RUN_ID}`, and emit:

```xml
<promise>TASK_BLOCKED</promise>
```

Then stop.

---

## Step 2: Select Exactly One Task

**Precondition:** `.worktree-ready_{GO_RUN_ID}`
**Creates:** `selected-task_{GO_RUN_ID}.json`, `.task-selected_{GO_RUN_ID}`

`/go` must select exactly one executable task.

### Preferred sources, in order

1. Existing structured plan/task artifact if available
2. `plan.md` or equivalent current plan document
3. Explicit user instruction in current conversation
4. Staged diff / current branch intent as fallback context

### Selection rules

The selected task MUST be:
- singular
- actionable
- testable or reviewable
- scoped tightly enough for one delegated skill
- free of mixed intent ("implement X and refactor Y and redesign Z")

If no task qualifies, emit `NO_TASKS_AVAILABLE`.

### Canonical selected task schema

Write `selected-task_{GO_RUN_ID}.json`:

```json
{
  "task_id": "string",
  "title": "string",
  "objective": "single-sentence objective",
  "task_type": "planning|design|implementation|refactor|unknown",
  "source": "structured-plan|plan-md|conversation|git-context",
  "source_ref": "string",
  "scope_in": ["..."],
  "scope_out": ["..."],
  "acceptance_criteria": ["..."],
  "verification_hint": ["..."],
  "blocked_by": [],
  "status": "selected"
}
```

Then create:

```bash
touch "$GO_ARTIFACT_DIR/.task-selected_${GO_RUN_ID}"
```

---

## Step 3: Route Classification

**Precondition:** `.task-selected_{GO_RUN_ID}`
**Creates:** `dispatch-decision_{GO_RUN_ID}.json`, `.routed_{GO_RUN_ID}`

`/go` decides which existing skill is authoritative.

### Routing table

#### Route to `/planning`
Use `/planning` if the task is primarily:
- decomposition
- prioritization
- sequencing
- task generation
- plan repair
- scope clarification requiring a formal executable plan

#### Route to `/design_v1.1`
Use `/design_v1.1` if the task has:
- architecture blockers
- unresolved contract boundaries
- cross-component design uncertainty
- CAP / ADR style design requirements
- explicit design intent that should trigger strict validation

#### Route to `/code`
Use `/code` if the task is primarily:
- feature implementation
- bug fix implementation
- targeted code changes
- tests plus implementation
- consumer/producer behavior changes already sufficiently designed

#### Route to `/refactor`
Use `/refactor` if the task is primarily:
- code cleanup without changing intended behavior
- duplication removal
- simplification
- maintainability improvements
- restructuring with characterization tests first

### Priority of routes when ambiguous

Use this precedence:

1. `design_v1.1` if architecture is unresolved
2. `planning` if executable scope is still unclear
3. `refactor` if behavior should stay the same and cleanup dominates
4. `code` if behavior change / implementation dominates

### Dispatch decision schema

Write `dispatch-decision_{GO_RUN_ID}.json`:

```json
{
  "go_run_id": "{GO_RUN_ID}",
  "task_id": "string",
  "route": "planning|design_v1.1|code|refactor",
  "reasoning_short": [
    "brief reason 1",
    "brief reason 2"
  ],
  "blocking_preconditions": [],
  "dispatch_status": "routed"
}
```

Then create:

```bash
touch "$GO_ARTIFACT_DIR/.routed_${GO_RUN_ID}"
```

---

## Step 4: Dispatch Existing Skill

**Precondition:** `.routed_{GO_RUN_ID}`
**Creates:** `dispatch-result_{GO_RUN_ID}.json`, `.dispatched_{GO_RUN_ID}`

`/go` now delegates to the selected existing skill.

### Dispatch contract

The delegated skill receives:
- the selected task title
- the objective
- scope_in
- scope_out
- acceptance criteria
- any route-specific blocker notes

### Invocation policy

`/go` MUST invoke exactly one of:
- `/planning`
- `/design_v1.1`
- `/code`
- `/refactor`

`/go` MUST NOT invoke more than one primary SDLC skill in the same untracked step.

If a delegated skill itself performs a documented nested handoff, that is allowed because it belongs to that skill's internal architecture.

### Dispatch result schema

Write `dispatch-result_{GO_RUN_ID}.json`:

```json
{
  "go_run_id": "{GO_RUN_ID}",
  "task_id": "string",
  "route": "planning|design_v1.1|code|refactor",
  "dispatch_status": "dispatched",
  "delegated_skill": "/code",
  "delegated_at": "ISO-8601",
  "expected_outcome_type": "plan|adr|implementation|refactor-result",
  "orchestrator_wait_state": "awaiting-skill-outcome"
}
```

Then create:

```bash
touch "$GO_ARTIFACT_DIR/.dispatched_${GO_RUN_ID}"
```

Immediately emit:

```xml
<promise>GO_DISPATCHED</promise>
```

---

## Step 5: Capture Outcome

**Precondition:** `.dispatched_{GO_RUN_ID}`
**Creates:** updated `dispatch-result_{GO_RUN_ID}.json`, optionally `skill-output-summary_{GO_RUN_ID}.md`, plus either `.completed_{GO_RUN_ID}` or `.blocked_{GO_RUN_ID}`

After delegated execution, `/go` records normalized outcome only.

### Valid normalized outcomes

#### Completed
Use when the delegated skill clearly completed the selected task or produced the required next artifact.

Set:

```json
"final_status": "completed"
```

Create:

```bash
touch "$GO_ARTIFACT_DIR/.completed_${GO_RUN_ID}"
```

#### Blocked
Use when the delegated skill reports or clearly implies:
- missing design decision
- failed verification gate
- unresolved plan ambiguity
- worktree/precondition issue
- skill-level refusal due to its own governance rules

Set:

```json
"final_status": "blocked"
```

Create:

```bash
touch "$GO_ARTIFACT_DIR/.blocked_${GO_RUN_ID}"
```

### Outcome recording requirements

Append or update fields in `dispatch-result_{GO_RUN_ID}.json`:

```json
{
  "final_status": "completed|blocked",
  "completion_summary": "brief summary",
  "produced_artifacts": ["..."],
  "next_recommended_skill": "planning|design_v1.1|code|refactor|null",
  "next_recommended_action": "string"
}
```

---

## Step 6: Emit Next Action

**Precondition:** `.completed_{GO_RUN_ID}` or `.blocked_{GO_RUN_ID}`
**Creates:** `next-action_{GO_RUN_ID}.md`

Write a short operator-facing file:

### If completed
`next-action_{GO_RUN_ID}.md` must include:
- task completed
- artifact paths produced
- whether more tasks remain
- recommended next task or next command

Emit one of:

```xml
<promise>TASK_COMPLETE</promise>
```

or

```xml
<promise>MORE_TASKS_REMAIN</promise>
```

### If blocked
`next-action_{GO_RUN_ID}.md` must include:
- what blocked the task
- which skill blocked it
- the minimal next action to unblock

Emit:

```xml
<promise>TASK_BLOCKED</promise>
```

---

## State Directory Example

```text
.claude/.artifacts/
└── {TERMINAL_ID}/
    └── go/
        ├── .initialized_{GO_RUN_ID}
        ├── .worktree-ready_{GO_RUN_ID}
        ├── .task-selected_{GO_RUN_ID}
        ├── .routed_{GO_RUN_ID}
        ├── .dispatched_{GO_RUN_ID}
        ├── .completed_{GO_RUN_ID}
        ├── run_{GO_RUN_ID}.json
        ├── selected-task_{GO_RUN_ID}.json
        ├── dispatch-decision_{GO_RUN_ID}.json
        ├── dispatch-result_{GO_RUN_ID}.json
        ├── skill-output-summary_{GO_RUN_ID}.md
        └── next-action_{GO_RUN_ID}.md
```

Blocked run example:

```text
.claude/.artifacts/
└── {TERMINAL_ID}/
    └── go/
        ├── .initialized_{GO_RUN_ID}
        ├── .worktree-ready_{GO_RUN_ID}
        ├── .task-selected_{GO_RUN_ID}
        ├── .routed_{GO_RUN_ID}
        ├── .dispatched_{GO_RUN_ID}
        ├── .blocked_{GO_RUN_ID}
        ├── run_{GO_RUN_ID}.json
        ├── selected-task_{GO_RUN_ID}.json
        ├── dispatch-decision_{GO_RUN_ID}.json
        ├── dispatch-result_{GO_RUN_ID}.json
        ├── blocked-reason_{GO_RUN_ID}.md
        └── next-action_{GO_RUN_ID}.md
```

---

## Hard Rules

### `/go` MUST
- use per-terminal artifact isolation
- select exactly one task
- route to exactly one primary SDLC skill
- preserve existing SDLC ownership boundaries
- write normalized orchestration records
- stop when blocked
- stop after recording one task outcome

### `/go` MUST NOT
- replace `/code` implementation workflow
- replace `/refactor` TDD/refactor workflow
- replace `/planning` synthesis/review workflow
- replace `/design_v1.1` strict validation workflow
- silently execute multiple primary tasks in one run
- push remotely
- claim completion without recording outcome artifacts

---

## Routing Heuristics

Use these short rules when choosing route:

- "Need a plan" → `/planning`
- "Need architecture clarity" → `/design_v1.1`
- "Need behavior change or implementation" → `/code`
- "Need cleanup without behavior change" → `/refactor`

If uncertain between `/code` and `/refactor`, ask:

**Is intended behavior changing?**
- yes → `/code`
- no → `/refactor`

If uncertain between `/planning` and `/design_v1.1`, ask:

**Is the blocker primarily architecture/contract related?**
- yes → `/design_v1.1`
- no → `/planning`

---

## Minimal Examples

### Example A: feature task
Selected task = "Add retry handling to Context7 resolver"
Route = `/code`

### Example B: unclear boundary
Selected task = "Split planner output contract from design handoff packet"
Route = `/design_v1.1`

### Example C: duplicate cleanup
Selected task = "Deduplicate repeated path normalization helpers without behavior change"
Route = `/refactor`

### Example D: plan formation
Selected task = "Break bundle findings into sequenced executable tasks"
Route = `/planning`

---

## Upgrade Notes from older `/go`

Compared with older artifact-safe `/go`, version 3.1 changes the role of `/go`:

- old `/go`: directly owned verify/simplify/review/pr loop
- new `/go`: owns only orchestration, routing, and normalized task state

What stays:
- `.claude/.artifacts/{TERMINAL_ID}/go/`
- per-run flags
- per-terminal isolation
- blocking gates
- auditable state trail

What moves out:
- verification authority → delegated skill
- simplification authority → delegated skill
- review authority → delegated skill
- implementation/refactor logic → delegated skill

---

## Default Operator Behavior

When user says:
- "go"
- "do the next task"
- "continue"
- "pick the next item"
- "execute the next planned change"

`/go` should:
1. select one task
2. route it
3. dispatch the proper SDLC skill
4. capture outcome
5. emit the correct promise token