---
name: go
version: 2.0.0
description: Local-only Ralph loop with canonical JSON contracts, per-terminal isolation, task-scoped runs, atomic gates, and /go -> /code orchestration.
category: execution
enforcement: blocking
triggers:
  - '/go'
aliases:
  - '/go-local'
  - '/local-pr-ready'
workflow_steps:
  - worktree_enforcement
  - task_selection
  - dispatch_code
  - verify_result
  - simplify_changes
  - review_passes
  - pr_artifacts
  - plan_progress_update
suggest: []
---

# /go — Select, Code, Verify, Ship

**MANDATORY SEQUENCE:** Worktree Check → Task Selection → /code Dispatch → Verify Result → Simplify → Review Passes → PR Artifacts → Plan Progress Update

**State Pattern:** `.claude/.artifacts/{TERMINAL_ID}/go/`
**Run Model:** exactly one selected task per `RUN_ID`
**Canonical Contracts:** `active-plan.json`, `active-task_{RUN_ID}.json`, `task-result_{RUN_ID}.json`

---

## Ralph Loop

This skill supports autonomous iteration with **terminal isolation**, **task-scoped runs**, and **atomic step gating**.

**Completion tokens:**
- `<promise>BLOCKED</promise>` — selected task cannot progress or max attempts reached
- `<promise>PR_READY</promise>` — selected task completed and local PR artifacts were generated
- `<promise>MORE_TASKS_IN_PLAN</promise>` — current task completed, more eligible tasks remain
- `<promise>ALL_TASKS_COMPLETE</promise>` — current task completed, no eligible tasks remain

**Loop behavior:**
- Each terminal has a unique `TERMINAL_ID`.
- Each task run has a unique `RUN_ID`.
- One `/go` run selects **exactly one** task.
- Ralph loops should keep the same `TERMINAL_ID` and create a **new `RUN_ID` per task**.
- Flags persist in `.claude/.artifacts/{TERMINAL_ID}/go/`.
- No downstream step may proceed unless the prior step's gate file exists.

**Token order:**
1. Emit `<promise>BLOCKED</promise>` immediately if the selected task fails irrecoverably.
2. Emit `<promise>PR_READY</promise>` after local artifacts are created.
3. Then emit either `<promise>MORE_TASKS_IN_PLAN</promise>` or `<promise>ALL_TASKS_COMPLETE</promise>` after updating `active-plan.json`.

---

## Initialization

**Export environment variables:**

```bash
export TERMINAL_ID=$(uuidgen | cut -d'-' -f1)
export RUN_ID=$(uuidgen)
export MAX_ATTEMPTS=3

ARTIFACT_DIR=".claude/.artifacts/$TERMINAL_ID/go"
PLAN_FILE="$ARTIFACT_DIR/active-plan.json"
ACTIVE_TASK_FILE="$ARTIFACT_DIR/active-task_$RUN_ID.json"
TASK_RESULT_FILE="$ARTIFACT_DIR/task-result_$RUN_ID.json"

mkdir -p "$ARTIFACT_DIR"
```

---

## STEP 0: WORKTREE ENFORCEMENT (MANDATORY)

**Creates flag:** `.worktree-ready_{RUN_ID}`

**Action:**

```bash
CURRENT_BRANCH=$(git branch --show-current)
IN_WORKTREE=$(git worktree list --porcelain | grep -q "$(pwd)" && echo "true" || echo "false")
```

**Gate:**
- Fail if not in a git worktree.
- Fail if on `main` or `master`.
- Fail if `active-plan.json` does not exist in the artifact directory.
- Fail if `active-plan.json` is invalid JSON.

**On success:**

```bash
touch "$ARTIFACT_DIR/.worktree-ready_$RUN_ID"
echo "✓ Worktree check passed"
```

---

## STEP 1: TASK SELECTION (MANDATORY)

**Checks flag:** `.worktree-ready_{RUN_ID}`
**Creates flag:** `.task-selected_{RUN_ID}`
**Creates file:** `active-task_{RUN_ID}.json`

**Pre-check:**

```bash
if [ ! -f "$ARTIFACT_DIR/.worktree-ready_$RUN_ID" ]; then
  echo "ERROR: STEP 0 must complete first"
  exit 1
fi

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: active-plan.json not found"
  exit 1
fi
```

**Action:**
Read `active-plan.json` and select **exactly one eligible task**.

**Eligible task rules:**
- `status == "pending"`
- dependencies are satisfied
- not already reserved by another active run
- has objective, allowed files, forbidden files, acceptance criteria, and verification commands

**Selection rules:**
- Select one task only.
- Never infer the task from git diff.
- Never invent missing acceptance criteria.
- If no eligible task exists, emit `<promise>ALL_TASKS_COMPLETE</promise>` and stop.

**Write `active-task_{RUN_ID}.json` with this shape:**

```json
{
  "run_id": "RUN_ID",
  "terminal_id": "TERMINAL_ID",
  "task_id": "TASK-001",
  "title": "Example task",
  "objective": "Implement the requested change.",
  "scope": {
    "in": ["packages/cc-skills-sdlc/skills/go/**"],
    "out": ["docs/archive/**"]
  },
  "allowed_files": [
    "packages/cc-skills-sdlc/skills/go/SKILL.md"
  ],
  "forbidden_files": [
    ".git/**",
    "main",
    "master"
  ],
  "acceptance_criteria": [
    "The selected task is implemented",
    "Verification evidence is captured"
  ],
  "verification_commands": [
    "bash -n packages/cc-skills-sdlc/skills/go/go-safe.sh"
  ],
  "selected_at": "2026-04-20T16:05:00Z",
  "status": "selected"
}
```

**On success:**

```bash
touch "$ARTIFACT_DIR/.task-selected_$RUN_ID"
echo "✓ Task selected"
```

---

## STEP 2: DISPATCH `/code` (MANDATORY)

**Checks flag:** `.task-selected_{RUN_ID}`
**Creates flag:** `.coded_{RUN_ID}` on success
**Creates flag:** `.attempt_{N}_{RUN_ID}` on retryable failure
**Creates flag:** `.blocked_{RUN_ID}` on terminal failure
**Creates file:** `task-result_{RUN_ID}.json`

**Pre-check:**

```bash
if [ ! -f "$ARTIFACT_DIR/.task-selected_$RUN_ID" ]; then
  echo "ERROR: STEP 1 must complete first"
  exit 1
fi

ATTEMPT_COUNT=$(find "$ARTIFACT_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
if [ "$ATTEMPT_COUNT" -ge "$MAX_ATTEMPTS" ]; then
  echo "ERROR: Max attempts reached"
  touch "$ARTIFACT_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
fi
```

**Action:**
Invoke `/code` exactly once for the selected task described in `active-task_{RUN_ID}.json`.

`/code` must:
- operate only on the selected task
- respect `allowed_files`
- avoid `forbidden_files`
- perform the requested implementation
- write `task-result_{RUN_ID}.json`

**Required `task-result_{RUN_ID}.json` shape:**

```json
{
  "run_id": "RUN_ID",
  "task_id": "TASK-001",
  "status": "completed",
  "summary": "Implemented the requested task changes.",
  "changed_files": [
    "packages/cc-skills-sdlc/skills/go/SKILL.md"
  ],
  "commands_executed": [
    "bash -n packages/cc-skills-sdlc/skills/go/go-safe.sh"
  ],
  "verification_evidence": [
    "bash syntax check passed"
  ],
  "blockers": [],
  "notes": [
    "No forbidden files changed"
  ],
  "completed_at": "2026-04-20T16:10:00Z"
}
```

**Failure handling:**
- If `/code` does not produce valid `task-result_{RUN_ID}.json`, create `.attempt_{N}_{RUN_ID}` and stop.
- If max attempts are exhausted, create `.blocked_{RUN_ID}` and emit `<promise>BLOCKED</promise>`.

**On success:**

```bash
touch "$ARTIFACT_DIR/.coded_$RUN_ID"
echo "✓ /code completed"
```

---

## STEP 3: VERIFY RESULT (MANDATORY)

**Checks flag:** `.coded_{RUN_ID}`
**Creates flag:** `.verified_{RUN_ID}` on success
**Creates flag:** `.attempt_{N}_{RUN_ID}` on failure
**Creates flag:** `.blocked_{RUN_ID}` on terminal failure
**Creates file:** `verification-results_{RUN_ID}.txt`

**Pre-check:**

```bash
if [ ! -f "$ARTIFACT_DIR/.coded_$RUN_ID" ]; then
  echo "ERROR: STEP 2 must complete first"
  exit 1
fi
```

**Action:**
Verify that `task-result_{RUN_ID}.json` is valid and that the implementation satisfies `active-task_{RUN_ID}.json`.

**Verification must confirm:**
- `task_id` matches
- `run_id` matches
- all changed files are within `allowed_files`
- no `forbidden_files` were changed
- acceptance criteria are actually satisfied
- verification commands were executed or independently reproduced
- evidence is concrete, not prose-only

Capture output and findings in `verification-results_{RUN_ID}.txt`.

**Failure handling:**
- On verification failure, create `.attempt_{N}_{RUN_ID}`.
- If max attempts are exhausted, create `.blocked_{RUN_ID}` and emit `<promise>BLOCKED</promise>`.

**On success:**

```bash
touch "$ARTIFACT_DIR/.verified_$RUN_ID"
echo "✓ Verification passed"
```

---

## STEP 4: SIMPLIFY (CODE-AWARE QUALITY GATE)

**Checks flag:** `.verified_{RUN_ID}`
**Creates flag:** `.simplified_{RUN_ID}`
**Creates file:** `simplify-status_{RUN_ID}.md`

**Pre-check:**

```bash
if [ ! -f "$ARTIFACT_DIR/.verified_$RUN_ID" ]; then
  echo "ERROR: STEP 3 must complete first"
  exit 1
fi
```

**Action:**
Determine whether the selected task changed code or only docs/artifacts using `task-result_{RUN_ID}.json` and/or actual git diff.

**Case A: Code changes**
- Run `/simplify`
- If HIGH or CRITICAL findings remain unresolved, stop and do not proceed

**Case B: Docs-only or artifact-only changes**
- Write `SKIPPED: docs-only or artifact-only change` to `simplify-status_{RUN_ID}.md`

**On success:**

```bash
touch "$ARTIFACT_DIR/.simplified_$RUN_ID"
echo "✓ Simplify passed"
```

---

## STEP 5: REVIEW PASSES (MANDATORY)

**Checks flag:** `.simplified_{RUN_ID}`
**Creates flag:** `.reviews-passed_{RUN_ID}`
**Creates files:**
- `review-pass-correctness_{RUN_ID}.md`
- `review-pass-scope_{RUN_ID}.md`
- `review-pass-tests_{RUN_ID}.md`
- `review-pass-simplicity_{RUN_ID}.md`
- `review-pass-regressions_{RUN_ID}.md`
- `review-pass-maintainability_{RUN_ID}.md`
- `review-pass-pr-ready_{RUN_ID}.md`

**Pre-check:**

```bash
if [ ! -f "$ARTIFACT_DIR/.simplified_$RUN_ID" ]; then
  echo "ERROR: STEP 4 must complete first"
  exit 1
fi
```

**Action:**
Run all 7 review passes for the selected task.

Each review file must contain:
- pass name
- checklist
- findings
- status: `PASS` or `REVIEW_REQUIRED`

**Failure handling:**
- If any pass is `REVIEW_REQUIRED`, stop and do not create `.reviews-passed_{RUN_ID}`.

**On success:**

```bash
touch "$ARTIFACT_DIR/.reviews-passed_$RUN_ID"
echo "✓ Review passes completed"
```

---

## STEP 6: PR ARTIFACTS (LOCAL ONLY)

**Checks flag:** `.reviews-passed_{RUN_ID}`
**Creates flag:** `.pr-ready_{RUN_ID}`
**Creates files:**
- `commit-message_{RUN_ID}.txt`
- `pr-title_{RUN_ID}.txt`
- `pr-body_{RUN_ID}.md`
- `pr-ready_{RUN_ID}.md`

**Pre-check:**

```bash
if [ ! -f "$ARTIFACT_DIR/.reviews-passed_$RUN_ID" ]; then
  echo "ERROR: STEP 5 must complete first"
  exit 1
fi
```

**Action:**
Generate:
- a conventional commit message
- a one-line PR title
- a PR body summarizing task, implementation, verification, simplify, and review outcomes
- a `pr-ready_{RUN_ID}.md` file containing local next steps and `<promise>PR_READY</promise>`

**Gate:** all 4 files must exist before `.pr-ready_{RUN_ID}` is created.

**On success:**

```bash
touch "$ARTIFACT_DIR/.pr-ready_$RUN_ID"
echo "✓ PR artifacts created locally"
echo "<promise>PR_READY</promise>"
```

---

## STEP 7: PLAN PROGRESS UPDATE

**Checks flag:** `.pr-ready_{RUN_ID}` or `.blocked_{RUN_ID}`
**Reads file:** `active-plan.json`
**Writes file:** updated `active-plan.json`

**Action:**
Update the selected task in `active-plan.json`.

If successful:
- set task `status` to `done`
- record `run_id`
- record `terminal_id`
- record `completed_at`

If blocked:
- set task `status` to `blocked`
- record blocker details
- record `run_id`
- record `terminal_id`
- record `updated_at`

**Loop decision:**
- If eligible pending tasks remain, emit `<promise>MORE_TASKS_IN_PLAN</promise>`
- Otherwise emit `<promise>ALL_TASKS_COMPLETE</promise>`

---

## Canonical JSON Contracts

### `active-plan.json`

```json
{
  "plan_id": "plan-001",
  "created_at": "2026-04-20T16:00:00Z",
  "updated_at": "2026-04-20T16:00:00Z",
  "tasks": [
    {
      "task_id": "TASK-001",
      "title": "Example task",
      "status": "pending",
      "priority": 1,
      "depends_on": [],
      "objective": "Implement the requested change.",
      "scope": {
        "in": ["packages/cc-skills-sdlc/skills/go/**"],
        "out": ["docs/archive/**"]
      },
      "allowed_files": [
        "packages/cc-skills-sdlc/skills/go/SKILL.md",
        "packages/cc-skills-sdlc/skills/go/go-safe.sh",
        "packages/cc-skills-sdlc/skills/go/ralph-go-loop.sh"
      ],
      "forbidden_files": [
        ".git/**",
        "main",
        "master"
      ],
      "acceptance_criteria": [
        "Selected task can be executed by /code",
        "Verification evidence is captured",
        "PR artifacts are generated locally"
      ],
      "verification_commands": [
        "bash -n packages/cc-skills-sdlc/skills/go/go-safe.sh",
        "bash -n packages/cc-skills-sdlc/skills/go/ralph-go-loop.sh"
      ]
    }
  ]
}
```

### `active-task_{RUN_ID}.json`

```json
{
  "run_id": "RUN_ID",
  "terminal_id": "TERMINAL_ID",
  "task_id": "TASK-001",
  "title": "Example task",
  "objective": "Implement the requested change.",
  "scope": {
    "in": ["packages/cc-skills-sdlc/skills/go/**"],
    "out": ["docs/archive/**"]
  },
  "allowed_files": [
    "packages/cc-skills-sdlc/skills/go/SKILL.md",
    "packages/cc-skills-sdlc/skills/go/go-safe.sh",
    "packages/cc-skills-sdlc/skills/go/ralph-go-loop.sh"
  ],
  "forbidden_files": [
    ".git/**",
    "main",
    "master"
  ],
  "acceptance_criteria": [
    "Selected task can be executed by /code",
    "Verification evidence is captured",
    "PR artifacts are generated locally"
  ],
  "verification_commands": [
    "bash -n packages/cc-skills-sdlc/skills/go/go-safe.sh",
    "bash -n packages/cc-skills-sdlc/skills/go/ralph-go-loop.sh"
  ],
  "selected_at": "2026-04-20T16:05:00Z",
  "status": "selected"
}
```

### `task-result_{RUN_ID}.json`

```json
{
  "run_id": "RUN_ID",
  "task_id": "TASK-001",
  "status": "completed",
  "summary": "Implemented the requested task changes.",
  "changed_files": [
    "packages/cc-skills-sdlc/skills/go/SKILL.md",
    "packages/cc-skills-sdlc/skills/go/go-safe.sh"
  ],
  "commands_executed": [
    "bash -n packages/cc-skills-sdlc/skills/go/go-safe.sh"
  ],
  "verification_evidence": [
    "bash syntax check passed for go-safe.sh"
  ],
  "blockers": [],
  "notes": [
    "No forbidden files changed"
  ],
  "completed_at": "2026-04-20T16:10:00Z"
}
```

---

## State Directory Structure

```
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

## Prohibited Actions

- Editing on `main` or `master`
- Proceeding without required gate files
- Selecting more than one task per run
- Inferring task intent from git diff alone
- Accepting prose-only `/code` output without `task-result_{RUN_ID}.json`
- Claiming acceptance criteria are met without evidence
- Pushing remotely from `/go`
- Proceeding past max attempts
