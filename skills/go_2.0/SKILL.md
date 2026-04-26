---
name: go_2.0
version: 2.0.0
description: Execute a task from user input, plan file, or tasks.json queue and drive it to PR-ready completion. Handles intent parsing, task selection, worktree enforcement, verification, simplification, 7-pass review, and local artifact generation. Not for architecture, design, or refactoring — use /planning, /design_1.0, or /refactor instead.
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
    - hooks:
        - type: command
          command: |
            python -c "import os,sys,glob; tid=os.environ.get('CLAUDE_TERMINAL_ID','unknown'); sd=f'.claude/.artifacts/{tid}/go'; sys.exit(0) if not glob.glob(f'{sd}/active-task_*.json') else None; rid=os.environ.get('GO_RUN_ID','unknown'); sys.exit(0) if os.path.isfile(f'{sd}/.verified_{rid}') and os.path.isfile(f'{sd}/.reviews-passed_{rid}') else (print('WARNING: /go completed without all gates passed',file=sys.stderr), sys.exit(1))"
          description: "Self-verify all gates passed on Stop"
---

# /go_2.0 — Thin Orchestrator

**Role:** `/go_2.0` is a **thin orchestrator**. It acquires a task (from user intent, a plan file, or a tasks.json queue), routes it to the correct SDLC skill, and records the outcome. It does not implement TDD, simplification, or review logic itself — it delegates to `/code`, `/refactor`, `/planning`, or `/design_1.0`.

**MANDATORY SEQUENCE:** Worktree Check → Task Selection → Verify → Simplify → 7-Pass Review → PR Artifacts → Loop Check

**State root:** `.claude/.artifacts/{TERMINAL_ID}/go/`

---

## What /go_2.0 Must Do

1. Enforce worktree + branch preconditions (auto-create if on main)
2. Acquire a task from one of three input sources
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
export GO_PROMPT="${GO_PROMPT:-}"
export HANDOFF_TRANSCRIPT="${HANDOFF_TRANSCRIPT:-}"
export GO_PLAN_FILE="${GO_PLAN_FILE:-}"
mkdir -p "$GO_STATE_DIR"
```

---

## Task Input Sources

| Source | Env Var | Description |
|--------|---------|-------------|
| Direct prompt | `GO_PROMPT` | User's task description at invocation |
| Handoff transcript | `HANDOFF_TRANSCRIPT` | Path to prior session transcript |
| Plan file | `GO_PLAN_FILE` | Path to `.md` plan file |
| Task queue | `GO_TASKS_FILE` | JSON file with queued tasks |

Priority: `GO_PROMPT` > `HANDOFF_TRANSCRIPT` > `GO_PLAN_FILE` > `GO_TASKS_FILE`

When using prompt/transcript/plan, the task is synthesized into the contract below. When using the task queue, the first task with `status` in `{ready, queued, approved}` is selected.

---

## Task Contract

**Synthesized task** (from intent parsing):

```json
{
  "task_id": "task-04221-1430",
  "title": "Short title",
  "objective": "One-sentence objective",
  "status": "ready",
  "priority": "P1",
  "scope_in": [],
  "scope_out": [],
  "forbidden_files": [],
  "acceptance_criteria": ["Criterion 1"],
  "verification_commands": [],
  "task_type": "implementation",
  "routing": { "skill": "/code", "route": "code" }
}
```

**Queued task** (from `$GO_TASKS_FILE`):

```json
{
  "id": "TASK-001",
  "title": "Short title",
  "objective": "One-sentence objective",
  "status": "ready",
  "priority": "P1",
  "scope_in": ["fileA"],
  "scope_out": ["fileB"],
  "forbidden_files": ["secrets.env"],
  "acceptance_criteria": ["Criterion 1"],
  "verification_commands": ["pytest -q"],
  "task_type": "implementation",
  "requires_approval": false
}
```

**Allowed `task_type` values:** `implementation`, `refactor`, `design`, `planning`

---

## Routing Table

| Condition | Route |
|-----------|-------|
| Code behavior change needed | `/code` |
| Cleanup without behavior change | `/refactor` |
| Architecture or contract unclear | `/design_1.0` |
| Scope unclear or decomposition needed | `/planning` |
| Config/infra only | direct verify → reviews |

---

## STEP 0: Worktree Enforcement

**If already in a registered git worktree:** proceed to Step 1.

**If on main or master:** auto-create a worktree.

```bash
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
  TS=$(date +%Y%m%d-%H%M%S)
  git worktree add -b "ai/ai-task-$TS" ".claude/worktrees/ai-task-$TS" HEAD
fi
```

The PreToolUse hook enforces this at the Bash level — if we reach this step, we're either already in a worktree or on main (which triggers creation).

---

## STEP 1: Task Acquisition

**From intent (GO_PROMPT / HANDOFF_TRANSCRIPT / GO_PLAN_FILE):** Parse intent and synthesize a task contract. Write `active-task_{RUN_ID}.json`.

**From queue (GO_TASKS_FILE):** Select the first task with `status` in `{ready, queued, approved}`.

```bash
python ".claude/skills/go_2.0/scripts/select-task.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.task-selected_$RUN_ID"
```

---

## STEP 2: Route & Dispatch

Read `active-task_{RUN_ID}.json`. Route by `task_type`:

- `implementation` → `/code`
- `refactor` → `/refactor`
- `design` → `/design_1.0`
- `planning` → `/planning`

For `implementation`, check for existing code changes:
- `git diff --name-only HEAD` — if empty or docs only, skip TDD
- If code changes exist, invoke `/tdd` then `/code`

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
