---
name: go
version: 3.0.0
description: Execute a task from user input, plan file, or tasks.json queue and drive it to PR-ready completion. Handles intent parsing, task selection, worktree enforcement, verification, simplification, 7-pass review, and local artifact generation. Uses the shared enforce layer for phase gate tracking. Not for architecture, design, or refactoring — use /planning, /design_1.0, or /refactor instead.
category: execution
enforcement: strict
workflow_steps:
  - worktree_enforcement
  - task_selection
  - verify_end_to_end
  - simplify_code
  - seven_pass_review
  - local_pr_artifacts
  - loop_check
suggest:
  - /planning
  - design
  - /code
  - refactor
hooks:
  Stop:
    - matcher: ".*"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PLUGIN_ROOT\"/skills/go_v3.0/hooks/Stop_enforce_gate.py"
          description: "Verify all Gen 2 phase gates via shared enforce layer"
---

# /go v3.0 — Thin Orchestrator (Shared Enforce Layer)

## What changed from v2.0

v3.0 replaces the inline Python Stop hook with the **shared enforce layer** (`enforce/stop_gate.py`). The enforcement logic is identical — only the infrastructure moved to a reusable shared library.

Phase gates (Gen 2 artifacts):
- HARD (blocking if missing): `worktree_ready`, `task_selected`, `code_completed`, `verified`, `simplified`, `reviews_passed`, `pr_ready`
- ADVISORY (warning only): `loop_sanity_check`, `trace_verification`

Evidence checked via Gen 2 flag files + JSON artifacts in `.claude/.artifacts/{TERMINAL_ID}/go/`.

All other behavior is identical to `/go` v2.0.

---

# /go — Thin Orchestrator (full reference)

**Role:** `/go` is a **thin orchestrator** that stays on `main`. It acquires a task (from user intent, a plan file, or a tasks.json queue), routes it to the correct SDLC skill, and records the outcome.

**Unified Schema:** All tasks and plans MUST adhere to the schemas defined in `__lib/sdlc_schemas.py`.

**MANDATORY SEQUENCE:** Worktree Check → Task Selection → Verify → Simplify → 7-Pass Review → PR Artifacts → Loop Check

**State root:** `.claude/.artifacts/{TERMINAL_ID}/go/`

## Completion Tokens

- `<promise>PR_READY</promise>` — task done, all gates passed, artifacts written
- `<promise>BLOCKED</promise>` — task cannot proceed or max attempts reached
- `<promise>MORE_TASKS_IN_PLAN</promise>` — current task done, more remain
- `<promise>ALL_TASKS_COMPLETE</promise>` — no eligible tasks remain

## Required Environment

```bash
export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${GO_RUN_ID:-$(uuidgen)}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export GO_STATE_DIR=".claude/.artifacts/${TERMINAL_ID}/go"
export GO_TASKS_FILE="${GO_TASKS_FILE:-.claude/tasks/tasks.json}"
export GO_PROMPT="${GO_PROMPT:-}"
export HANDOFF_TRANSCRIPT="${HANDOFF_TRANSCRIPT:-}"
export GO_PLAN_FILE="${GO_PLAN_FILE:-}"
mkdir -p "$GO_STATE_DIR"
```

## Task Input Sources

| Source | Env Var | Description |
|--------|---------|-------------|
| Direct prompt | `GO_PROMPT` | User's task description at invocation |
| Handoff transcript | `HANDOFF_TRANSCRIPT` | Path to prior session transcript |
| Plan file | `GO_PLAN_FILE` | Path to `.md` plan file |
| Task queue | `GO_TASKS_FILE` | JSON file with queued tasks |

Priority: `GO_PROMPT` > `HANDOFF_TRANSCRIPT` > `GO_PLAN_FILE` > `GO_TASKS_FILE`

## Routing Table

| Condition | Route |
|-----------|-------|
| Code behavior change needed | `/code` (or `/code_v4.0`) |
| Cleanup without behavior change | `/refactor` |
| Architecture or contract unclear | `/design_1.0` |
| Scope unclear or decomposition needed | `/planning` |
| Config/infra only | direct verify → reviews |

## STEP 0: Worktree Provisioning

`/go` stays on `main`. Creates a worktree for the worker, then dispatches the worker into it. Touches `.worktree-ready_{RUN_ID}` on success.

## STEP 1: Task Acquisition

From intent or queue. Touches `.task-selected_{RUN_ID}` on success.

## STEP 2: Route & Dispatch

Routes by `task_type`. On code completion, touches `.coded_{RUN_ID}`.

## STEP 3: Verification

Runs verification commands. Touches `.verified_{RUN_ID}` on success.

## STEP 4: Simplify

Runs `/simplify` if code changed. Touches `.simplified_{RUN_ID}` on success.

## STEP 5: 7-Pass Review

Runs review passes. Touches `.reviews-passed_{RUN_ID}` on success.

## STEP 6: Local PR Artifacts

Generates PR artifacts. Touches `.pr-ready_{RUN_ID}` on success.

## STEP 7: Loop Check

Checks for remaining eligible tasks.

## Phase Gate Evidence (Gen 2 Artifacts)

| Phase | Gate | Evidence |
|-------|------|----------|
| `worktree_ready` | hard | `.worktree-ready_{RUNID}` flag file |
| `task_selected` | hard | `.task-selected_{RUNID}` flag file |
| `code_completed` | hard | `.coded_{RUNID}` flag + `task-result_{RUNID}.json` with `status=pr_ready` |
| `verified` | hard | `.verified_{RUNID}` flag + `verification-summary_{RUNID}.json` with `verified=true` |
| `simplified` | hard | `.simplified_{RUNID}` flag file |
| `reviews_passed` | hard | `.reviews-passed_{RUNID}` flag file |
| `pr_ready` | hard | `.pr-ready_{RUNID}` flag + PR artifact files present |
| `loop_sanity_check` | advisory | No real evidence yet (placeholder) |
| `trace_verification` | advisory | No real evidence yet (placeholder) |

## Prohibited Actions

- Workers making direct changes on `main` or `master`
- Using `plan.md` as scheduler source
- Proceeding without required prior flag
- Ignoring failed verification commands
- Ignoring HIGH/CRITICAL simplify findings
- Auto-pushing or creating remote PRs
- Modifying `forbidden_files` listed in task contract

---

**Version:** 3.0.0 | Uses shared enforce layer (`enforce/`). Phase definitions map to Gen 2 flag files.