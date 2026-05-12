---
name: go-ef
version: 1.1.0
description: "Execute a task from user input, plan file, or tasks.json queue and drive it to PR-ready completion. Handles intent parsing, task selection, worktree enforcement, verification, simplification, 7-pass review, merge/sync, post-clean, and local artifact generation. Uses the shared enforce layer for phase gate tracking. Not for architecture, design, or refactoring — use /planning, /design_1.0, or /refactor instead."
category: execution
enforcement: strict
workflow_steps:
  - pre_clean
  - worktree_enforcement
  - task_selection
  - verify_end_to_end
  - simplify_code
  - seven_pass_review
  - merge_sync
  - local_pr_artifacts
  - post_clean
  - loop_check
suggest:
  - /planning
  - design
  - /code
  - refactor
hooks:
  PreToolUse:
    - matcher: ^/go
      hooks:
        - type: command
          command: python "$CLAUDE_PLUGIN_ROOT"/skills/go-ef/hooks/PreToolUse_go_invocation_receipt.py
          description: Write invocation receipt to phase ledger
  Stop:
    - matcher: .*
      hooks:
        - type: command
          command: python "$CLAUDE_PLUGIN_ROOT"/skills/go-ef/hooks/Stop_enforce_gate.py
          description: Verify all Gen 2 phase gates via shared enforce layer
required_artifacts: []
response_requirements: {}
contract_type: workflow-execution

---

# /go-ef — Evidence-First Variant

## What changed from go2

`-ef` is the canonical naming format for evidence-first enforced skills.
Phase gates are managed by the shared enforce layer.

Evidence checked via ~/.claude/.state/enforce/go-ef/{TERMINAL_ID}/phase-ledger.json.


# /go — Thin Orchestrator

**Role:** `/go` is a **thin orchestrator** that stay on `main`. It acquires a task (from user intent, a plan file, or a tasks.json queue), routes it to the correct SDLC skill, and records the outcome.

**Unified Schema:** All tasks and plans MUST adhere to the schemas defined in `__lib/sdlc_schemas.py`.

**MANDATORY SEQUENCE:** Pre-Clean (advisory) → Worktree → Task → Verify → Simplify → 7-Pass Review → Merge → PR Artifacts → Post-Clean → Loop Check

**State root:** `.claude/.artifacts/{TERMINAL_ID}/go/`


## What /go Must Do

1. Enforce worktree + branch preconditions (auto-create if on main)
2. Acquire a task from one of three input sources
3. Classify task complexity → select model via Bifrost
4. Route to the correct SDLC skill based on task type and diff
5. Run verification commands from the task contract
6. Run `/simplify` if code changed
7. Run 7-pass review at the appropriate depth
8. Generate local PR artifacts
9. Emit the correct completion token

**What /go Must NOT Do:**
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

## STEP 0: Pre-Clean (Advisory)

Audits orphaned worktrees and stale state dirs. **Never destructive by default** — only reports findings. Use `--cleanup force` to actually prune.

| Mode | Behavior |
|------|----------|
| `audit` (default) | Report orphaned worktrees and stale state. Never remove anything. |
| `force` | Prune clean orphaned worktrees, archive stale state dirs. |
| `skip` | Skip pre-clean entirely. |

An orphaned worktree is one with no corresponding state dir. A stale state dir is one with no corresponding worktree. Pre-clean catches interrupted sessions and accumulated debris.

On every `/go` invocation, pre-clean runs in `audit` mode — reports what it finds, then proceeds. User can re-run with `force` to actually clean up.

## STEP 1: Worktree Provisioning

`/go` stays on `main`. It creates a worktree for the worker, then dispatches the worker into it.

**Create a worktree for the task:**

```bash
TS=$(date +%Y%m%d-%H%M%S)
WORKTREE=".claude/worktrees/ai-task-$TS"
git worktree add -b "ai/ai-task-$TS" "$WORKTREE" HEAD
```

**Dispatch a worker into the worktree** using one of:

| Method | When to use |
|--------|-------------|
| `Agent` tool with `isolation: "worktree"` | Subagent does code changes |
| `Agent` tool with prompt instructing `EnterWorktree` | Worker needs to choose its own worktree |
| `claude -p` with `--cd "$WORKTREE"` | External CLI-based LLM |

`/go` remains on `main` throughout — it orchestrates, workers execute.

## STEP 2: Task Acquisition

**From intent (GO_PROMPT / HANDOFF_TRANSCRIPT / GO_PLAN_FILE):** Parse intent and synthesize a task contract. Write `active-task_{RUN_ID}.json`.

**From queue (GO_TASKS_FILE):** Select the first task with `status` in `{ready, queued, approved}`.

```bash
python ".claude/skills/go/scripts/select-task.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.task-selected_$RUN_ID"
```

## STEP 2.5: Classify Complexity

Read `active-task_{RUN_ID}.json` and classify complexity. Select model for Bifrost routing.

```bash
python ".claude/skills/go/scripts/classify_complexity.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
```

Output: `model-selection_{RUN_ID}.json` with `{tier, model, confidence, signals}`.

| Tier | Model | Task types |
|------|-------|------------|
| T1-T3 | `M27` | implementation, refactor, config |
| T4 | `GLM-5.1` | design, planning |

Override: `GO_MODEL_OVERRIDE` env var bypasses classification.

---

## STEP 3: Route & Dispatch

Read `active-task_{RUN_ID}.json`. Route by `task_type`:

- `implementation` → `/code`
- `refactor` → `/refactor`
- `design` → `/design_1.0`
- `planning` → `/planning`

For `implementation`, check for existing code changes:
- `git diff --name-only HEAD` — if empty or docs only, skip TDD
- If code changes exist, invoke `/tdd` then `/code`

---

## STEP 4: Verification

Run every command in `task.verification_commands`. Record results.

```bash
python ".claude/skills/go/scripts/verify-task.py"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  ATTEMPT_NEXT=$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
  [ "$ATTEMPT_NEXT" -ge "$MAX_ATTEMPTS" ] && touch "$GO_STATE_DIR/.blocked_$RUN_ID" && echo "<promise>BLOCKED</promise>" && exit 1
  exit 1
fi
touch "$GO_STATE_DIR/.verified_$RUN_ID"
```

---

## STEP 5: Simplify

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

## STEP 6: 7-Pass Review

Run review passes at the depth determined by diff classification.

```bash
python ".claude/skills/go/scripts/review-passes.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.reviews-passed_$RUN_ID"
```

---

## STEP 7: Merge / Sync

Stage and commit worktree changes. Writes `commit-info.json` with `{commit, message}`. Branch stays alive — user reviews before pushing.

```bash
git -C "$WORKTREE" add .
git -C "$WORKTREE" commit -m "$TASK_TITLE"
```

Touches `.merge-done_{RUN_ID}` on success.

## STEP 8: Local PR Artifacts

Generate commit message, PR title, PR body, PR-ready report.

```bash
python ".claude/skills/go/scripts/pr-artifacts.py"
touch "$GO_STATE_DIR/.pr-ready_$RUN_ID"
echo "<promise>PR_READY</promise>"
```

---

## STEP 9: Post-Clean

Prunes worktree (after merge commit exists), purges stale `.attempt_*` files older than 7 days, archives run artifacts to `.artifacts/archive/`.

---

## STEP 10: Loop Check

Check if more eligible tasks remain.

```bash
python ".claude/skills/go/scripts/loop-check.py"
```

---

## Prohibited Actions

- Workers making direct changes on `main` or `master`
- Using `plan.md` as scheduler source
- Proceeding without required prior flag
- Ignoring failed verification commands
- Ignoring HIGH/CRITICAL simplify findings
- Auto-pushing or creating remote PRs
- Modifying `forbidden_files` listed in task contract
