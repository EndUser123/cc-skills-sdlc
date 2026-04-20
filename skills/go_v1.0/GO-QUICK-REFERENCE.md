# /go Gen 2 — Quick Reference

Gen 2 replaces markdown task contracts and `plan.md` loop control with canonical JSON contracts and `/go -> /code` orchestration.

---

## Core Model

`/go` does exactly one task per `RUN_ID`.

Flow:

1. Validate worktree
2. Read `active-plan.json`
3. Select one eligible task
4. Write `active-task_{RUN_ID}.json`
5. Invoke `/code`
6. Require `task-result_{RUN_ID}.json`
7. Verify
8. Simplify
9. Review
10. Create local PR artifacts
11. Update `active-plan.json`
12. Emit loop token

---

## Canonical Files

All state lives in:

```text
.claude/.artifacts/{TERMINAL_ID}/go/
```

Key files:

```text
active-plan.json
active-task_{RUN_ID}.json
task-result_{RUN_ID}.json
verification-results_{RUN_ID}.txt
simplify-status_{RUN_ID}.md
review-pass-correctness_{RUN_ID}.md
review-pass-scope_{RUN_ID}.md
review-pass-tests_{RUN_ID}.md
review-pass-simplicity_{RUN_ID}.md
review-pass-regressions_{RUN_ID}.md
review-pass-maintainability_{RUN_ID}.md
review-pass-pr-ready_{RUN_ID}.md
commit-message_{RUN_ID}.txt
pr-title_{RUN_ID}.txt
pr-body_{RUN_ID}.md
pr-ready_{RUN_ID}.md
```

---

## Flag Files

Gen 2 gate files:

```text
.worktree-ready_{RUN_ID}
.task-selected_{RUN_ID}
.coded_{RUN_ID}
.verified_{RUN_ID}
.simplified_{RUN_ID}
.reviews-passed_{RUN_ID}
.pr-ready_{RUN_ID}
.blocked_{RUN_ID}
.attempt_{N}_{RUN_ID}
```

Meaning:

- `.worktree-ready_{RUN_ID}` — worktree and plan validation passed
- `.task-selected_{RUN_ID}` — one task was selected from `active-plan.json`
- `.coded_{RUN_ID}` — `/code` completed and wrote `task-result_{RUN_ID}.json`
- `.verified_{RUN_ID}` — implementation matched contract and evidence passed
- `.simplified_{RUN_ID}` — simplify gate passed or valid skip recorded
- `.reviews-passed_{RUN_ID}` — all 7 review passes passed
- `.pr-ready_{RUN_ID}` — local PR artifacts exist
- `.blocked_{RUN_ID}` — task cannot proceed
- `.attempt_{N}_{RUN_ID}` — retry counter for this run

---

## Environment Variables

```bash
export TERMINAL_ID=$(uuidgen | cut -d'-' -f1)
export RUN_ID=$(uuidgen)
export MAX_ATTEMPTS=3
```

Derived paths:

```bash
ARTIFACT_DIR=".claude/.artifacts/$TERMINAL_ID/go"
PLAN_FILE="$ARTIFACT_DIR/active-plan.json"
ACTIVE_TASK_FILE="$ARTIFACT_DIR/active-task_$RUN_ID.json"
TASK_RESULT_FILE="$ARTIFACT_DIR/task-result_$RUN_ID.json"
```

---

## JSON Contracts

### `active-plan.json`

Scheduler source of truth.

Each task should contain:

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

### `active-task_{RUN_ID}.json`

Selected-task snapshot for one run.

Required fields:

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

### `task-result_{RUN_ID}.json`

Required `/code` output.

Required fields:

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

## Eligibility Rules

A task is eligible when:

- `status == "pending"`
- all `depends_on` tasks are already `done`
- it is not reserved by another active run
- it has all required contract fields

If no eligible task exists, `/go` should stop with:

```text
<promise>ALL_TASKS_COMPLETE</promise>
```

---

## Completion Tokens

```text
<promise>BLOCKED</promise>
<promise>PR_READY</promise>
<promise>MORE_TASKS_IN_PLAN</promise>
<promise>ALL_TASKS_COMPLETE</promise>
```

Interpretation:

- `BLOCKED` — current selected task failed terminally
- `PR_READY` — current selected task completed and PR artifacts exist
- `MORE_TASKS_IN_PLAN` — current task is done, more eligible tasks remain
- `ALL_TASKS_COMPLETE` — no eligible tasks remain

---

## Manual Run

```bash
bash go-safe.sh
```

Expected behavior:

1. validate worktree
2. validate `active-plan.json`
3. preview next eligible task
4. write `.env_{RUN_ID}`
5. invoke `/go`
6. print selected-task/result artifacts if present

---

## Ralph Loop

```bash
bash ralph-go-loop.sh 10
```

Loop behavior:

- keep one `TERMINAL_ID` for the session
- create a new `RUN_ID` each cycle
- read `active-plan.json` before each cycle
- call `/go`
- inspect `.blocked_{RUN_ID}` and `.pr-ready_{RUN_ID}`
- reread `active-plan.json`
- continue if eligible tasks remain
- exit when all are complete or blocked

---

## State Layout

```text
.claude/.artifacts/
└── {TERMINAL_ID}/
    └── go/
        ├── active-plan.json
        ├── .worktree-ready_{RUN_ID}
        ├── .task-selected_{RUN_ID}
        ├── .coded_{RUN_ID}
        ├── .verified_{RUN_ID}
        ├── .simplified_{RUN_ID}
        ├── .reviews-passed_{RUN_ID}
        ├── .pr-ready_{RUN_ID}
        ├── .blocked_{RUN_ID}
        ├── .attempt_{N}_{RUN_ID}
        ├── active-task_{RUN_ID}.json
        ├── task-result_{RUN_ID}.json
        ├── verification-results_{RUN_ID}.txt
        ├── simplify-status_{RUN_ID}.md
        ├── review-pass-correctness_{RUN_ID}.md
        ├── review-pass-scope_{RUN_ID}.md
        ├── review-pass-tests_{RUN_ID}.md
        ├── review-pass-simplicity_{RUN_ID}.md
        ├── review-pass-regressions_{RUN_ID}.md
        ├── review-pass-maintainability_{RUN_ID}.md
        ├── review-pass-pr-ready_{RUN_ID}.md
        ├── commit-message_{RUN_ID}.txt
        ├── pr-title_{RUN_ID}.txt
        ├── pr-body_{RUN_ID}.md
        └── pr-ready_{RUN_ID}.md
```

---

## What Gen 2 Removed

Gen 1 concepts that no longer apply:

- `task-contract_{RUN_ID}.md`
- diff-classified review depth
- `plan.md` as loop source of truth
- verification driven from markdown task contract
- single `RUN_ID` across an entire Ralph loop

---

## Fast Smoke Test

1. create `.claude/.artifacts/{TERMINAL_ID}/go/active-plan.json`
2. run `bash go-safe.sh`
3. verify:
   - `active-task_{RUN_ID}.json` exists
   - `task-result_{RUN_ID}.json` exists
   - `.pr-ready_{RUN_ID}` exists for successful task
4. run `bash ralph-go-loop.sh 10`
5. confirm plan drains to `ALL_TASKS_COMPLETE`

---

## Failure Rules

Stop immediately if any of these happen:

- not in a worktree
- on `main` or `master`
- `active-plan.json` missing
- `active-plan.json` invalid
- no valid selected task
- `/code` does not emit valid `task-result_{RUN_ID}.json`
- forbidden files changed
- verification fails
- simplify remains HIGH or CRITICAL
- any review pass is `REVIEW_REQUIRED`

---

## Recommended Operator Order

Use this order only:

1. replace `SKILL.md`
2. replace `go-safe.sh`
3. replace `ralph-go-loop.sh`
4. replace this quick reference
5. replace implementation guide
6. create starter `active-plan.json`
7. run `bash go-safe.sh`
8. run `bash ralph-go-loop.sh 10`
