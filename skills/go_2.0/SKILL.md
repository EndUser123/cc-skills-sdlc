---
name: go_2.0
version: 2.0.0
description: Thin orchestrator — selects one task from `.claude/tasks/tasks.json`, runs it through verify → simplify → 7-pass review → local PR artifacts. Use when: tasks are queued in `.claude/tasks/tasks.json`, user says "do the next task", "run /go", "pick the next item", or "execute the planned changes". Do not use for architecture, design, or refactoring — route those to `/planning`, `/design_1.0`, or `/refactor` instead.
category: execution
enforcement: strict
triggers:
  - '/go_2.0'
aliases:
  - '/go-local'
  - '/local-pr-ready'
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
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: |
            git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
              echo "ERROR: not in git repo"; exit 2
            }
            BRANCH="$(git branch --show-current)"
            case "$BRANCH" in main|master)
              echo "ERROR: /go cannot run on $BRANCH"; exit 2
            esac
            git worktree list --porcelain | grep -F "worktree $(pwd)" >/dev/null 2>&1 || {
              echo "ERROR: not in registered git worktree"; exit 2
            }
          description: "Block non-worktree or main-branch Bash calls"
  Stop:
    - hooks:
        - type: command
          command: |
            STATE_DIR=".claude/.artifacts/${CLAUDE_TERMINAL_ID:-unknown}/go"
            RUN_ID="${GO_RUN_ID:-unknown}"
            if [ -f "$STATE_DIR/.verified_$RUN_ID" ] && [ -f "$STATE_DIR/.reviews-passed_$RUN_ID" ]; then
              exit 0
            else
              echo "WARNING: /go completed without all gates passed"
              exit 1
            fi
          description: "Self-verify all gates passed on Stop"
---

# /go_2.0 — Thin Orchestrator

**Role:** `/go_2.0` is a **thin orchestrator**. It selects one task, routes it to the correct SDLC skill, and records the outcome. It does not implement TDD, simplification, or review logic itself — it delegates to `/code`, `/refactor`, `/planning`, or `/design_1.0`.

**MANDATORY SEQUENCE:** Worktree Check → Task Selection → Verify → Simplify → 7-Pass Review → PR Artifacts → Loop Check

**State root:** `.claude/.artifacts/{TERMINAL_ID}/go/`

---

## What /go_2.0 Must Do

1. Enforce worktree + branch preconditions
2. Select exactly **one** task from `$GO_TASKS_FILE`
3. Route to the correct SDLC skill based on task type and diff
4. Run verification commands from the task contract
5. Run `/simplify` if code changed
6. Run 7-pass review at the appropriate depth
7. Generate local PR artifacts
8. Emit the correct completion token

**What /go_2.0 Must NOT Do:**
- Replace `/code` TDD workflow
- Replace `/refactor` cleanup logic
- Replace `/planning` task breakdown
- Use `plan.md` as a scheduler source
- Auto-push or create remote PRs

---

## Completion Tokens

- `<promise>PR_READY</promise>` — task done, all gates passed, artifacts written
- `<promise>BLOCKED</promise>` — task cannot proceed or max attempts reached
- `<promise>MORE_TASKS_IN_PLAN</promise>` — current task done, more remain
- `<promise>ALL_TASKS_COMPLETE</promise>` — no eligible tasks remain

---

## Required Environment

```bash
export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${GO_RUN_ID:-$(uuidgen)}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export GO_STATE_DIR=".claude/.artifacts/${TERMINAL_ID}/go"
export GO_TASKS_FILE="${GO_TASKS_FILE:-.claude/tasks/tasks.json}"
mkdir -p "$GO_STATE_DIR"
```

---

## Task Source-of-Truth Contract

`$GO_TASKS_FILE` must be valid JSON:

```json
{
  "version": "1.0",
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Short title",
      "objective": "One-sentence objective",
      "status": "ready",
      "priority": "P1",
      "scope_in": ["fileA", "fileB"],
      "scope_out": ["fileC"],
      "forbidden_files": ["secrets.env"],
      "acceptance_criteria": ["Criterion 1", "Criterion 2"],
      "verification_commands": ["pytest -q", "npm test"],
      "task_type": "implementation",
      "requires_approval": false
    }
  ]
}
```

**Allowed `status` values:** `ready`, `queued`, `approved`

---

## Routing Table

Read `ROUTING.md` for the full decision table. Summary:

| Condition | Route |
|-----------|-------|
| Code behavior change needed | `/code` |
| Cleanup without behavior change | `/refactor` |
| Architecture or contract unclear | `/design_1.0` |
| Scope unclear or decomposition needed | `/planning` |
| Config/infra only | direct verify → reviews |

---

## STEP 0: Worktree Enforcement

Fail immediately if not in a registered git worktree or on `main`/`master`.

```bash
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "ERROR: not in git repo"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
}
BRANCH="$(git branch --show-current)"
case "$BRANCH" in main|master)
  echo "ERROR: /go cannot run on $BRANCH"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
esac
git worktree list --porcelain | grep -F "worktree $(pwd)" >/dev/null 2>&1 || {
  echo "ERROR: not in registered git worktree"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
}
touch "$GO_STATE_DIR/.worktree-ready_$RUN_ID"
```

---

## STEP 1: Task Selection

Select the first task with `status` in `{ready, queued, approved}`. Write `active-task_{RUN_ID}.json`.

```bash
python ".claude/skills/go_2.0/scripts/select-task.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.task-selected_$RUN_ID"
```

---

## STEP 2: Route & Dispatch

Read `active-task_{RUN_ID}.json`. Classify the task type:

- `task_type: implementation` → `/code`
- `task_type: refactor` → `/refactor`
- `task_type: design` → `/design_1.0`
- `task_type: planning` → `/planning`

For `task_type: implementation`, check for code changes first:
- `git diff --name-only HEAD` — if empty or docs only, skip TDD
- If code changes exist, invoke `/tdd` then `/code`

**Direct dispatch example:**
```bash
SKILL_ROUTE="/code"
"$SKILL_ROUTE" --task-file "$GO_STATE_DIR/active-task_$RUN_ID.json" \
  --output "$GO_STATE_DIR/task-result_$RUN_ID.json" \
  2>&1 | tee "$GO_STATE_DIR/dispatch-log_$RUN_ID.txt"
```

After dispatch, write `task-result_{RUN_ID}.json` or the skill's output artifact.

---

## STEP 3: Verification

Run every command in `task.verification_commands`. Record results.

```bash
python ".claude/skills/go_2.0/scripts/verify-task.py"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  ATTEMPT_NEXT=$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
  [ "$ATTEMPT_NEXT" -ge "$MAX_ATTEMPTS" ] && touch "$GO_STATE_DIR/.blocked_$RUN_ID" && echo "<promise>BLOCKED</promise>" && exit 1
  exit 1
fi
touch "$GO_STATE_DIR/.verified_$RUN_ID"
```

---

## STEP 4: Simplify

If docs-only diff, skip. Otherwise run `/simplify`.

```bash
DOCS_ONLY="$(python -c 'import json; d=json.load(open(".claude/.artifacts/'${TERMINAL_ID}'/go/diff-summary_'${RUN_ID}'.json")); print("true" if d.get("docs_only") else "false")' 2>/dev/null || echo false)"
if [ "$DOCS_ONLY" = "true" ]; then
  echo "Skipping simplify (docs-only)"
else
  /simplify > "$GO_STATE_DIR/simplify-status_$RUN_ID.md" 2>&1 || true
  grep -qiE 'CRITICAL|HIGH' "$GO_STATE_DIR/simplify-status_$RUN_ID.md" && {
    echo "ERROR: simplify HIGH/CRITICAL findings"
    touch "$GO_STATE_DIR/.blocked_$RUN_ID"
    echo "<promise>BLOCKED</promise>"
    exit 1
  }
fi
touch "$GO_STATE_DIR/.simplified_$RUN_ID"
```

---

## STEP 5: 7-Pass Review

Run review passes at the depth determined by diff classification.

```bash
python ".claude/skills/go_2.0/scripts/review-passes.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.reviews-passed_$RUN_ID"
```

---

## STEP 6: Local PR Artifacts

Generate commit message, PR title, PR body, PR-ready report.

```bash
python ".claude/skills/go_2.0/scripts/pr-artifacts.py"
touch "$GO_STATE_DIR/.pr-ready_$RUN_ID"
echo "<promise>PR_READY</promise>"
```

---

## STEP 7: Loop Check

Check if more eligible tasks remain.

```bash
python ".claude/skills/go_2.0/scripts/loop-check.py"
```

---

## Prohibited Actions

- Running on `main` or `master`
- Using `plan.md` as scheduler source
- Proceeding without required prior flag
- Ignoring failed verification commands
- Ignoring HIGH/CRITICAL simplify findings
- Auto-pushing or creating remote PRs
- Modifying `forbidden_files` listed in task contract
