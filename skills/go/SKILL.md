---
name: go
version: 2.0.1
description: Use when a user asks to run /go, execute the next planned task, process a tasks.json queue, or drive a bounded SDLC task through enforced evidence gates.
category: execution
enforcement: strict
dispatch_default: pi
dispatch_modes:
  - pi
  - claude
  - local
allowed_first_tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
  - MultiEdit
  - Skill
  - AskUserQuestion
  - TodoWrite
required_first_command_patterns: []
workflow_steps: []
hooks:
  Stop:
    - matcher: .*
      hooks:
        - type: command
          command: python "$CLAUDE_PLUGIN_ROOT"/skills/go/hooks/Stop_enforce_gate.py
          description: Verify /go phase gates via shared enforce layer
---
# /go - Evidence-First SDLC Orchestrator

**Role:** `/go` is a **thin orchestrator** that stays on `main`. It acquires a task (from user intent, a plan file, or a tasks.json queue), dispatches or verifies through the selected mode, and records the outcome.

**Unified Schema:** All tasks and plans MUST adhere to the schemas defined in `schemas/` and shared helper contracts.

**MANDATORY SEQUENCE:** Worktree Check -> Task Selection -> Classify -> Dispatch -> Verify -> Simplify -> 7-Pass Review -> QA Verification -> PR Artifacts -> Loop Check

**State root:** `.claude/.artifacts/{TERMINAL_ID}/go/`

**Orchestrator:** `scripts/orchestrate.py`

---

## Dispatch Contract

Default dispatch is `pi`.

```bash
/go "fix the failing tests"
/go --dispatch pi "fix the failing tests"
/go --dispatch claude "fix the failing tests"
/go --dispatch local "verify config-only changes"
```

Dispatch precedence:

1. `--dispatch`
2. `GO_DISPATCH`
3. `pi`

Valid modes:

| Mode | Worker |
|------|--------|
| `pi` | External pi harness via `pi -p --mode json --model <resolved>` |
| `local` | No worker; runs verification/review/artifact gates against the current checkout |
| `claude` | Blocked with `unsupported-automated-dispatch` until a real non-interactive worker exists |

---

## What /go Must Do

1. Enforce worktree + branch preconditions (auto-create if on main)
2. Acquire a task from one of three input sources
3. Classify task complexity → select model via Bifrost
4. Dispatch through `pi`, run local verification, or block unsupported `claude`
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

## Pi Dispatch Mode

When dispatch is `pi`, the classifier output is resolved through `scripts/adapters/pi/resolve_model.py`.

| Classifier Output | pi --model flag | Provider |
|---|---|---|
| `M3` | `minimax/MiniMax-M3` | MiniMax |
| `GLM-5.2` | `zai/glm-5.2` | Z.ai |

`GO_MODEL_OVERRIDE` bypasses classification and is passed through as the pi model flag.

---

## Completion Tokens

- `<promise>PR_READY</promise>` — task done, all gates passed, artifacts written
- `<promise>BLOCKED</promise>` — task cannot proceed or max attempts reached
- `<promise>MORE_TASKS_IN_PLAN</promise>` — current task done, more remain
- `<promise>ALL_TASKS_COMPLETE</promise>` — no eligible tasks remain
- `<promise>PAUSED_FOR_APPROVAL</promise>` — run paused at a plan-declared gate: the only remaining tasks are `requires_approval: true` and not yet `approved`. Resume by flipping a gated task's `status` to `approved` and re-running `/go`.

---

## Continuation Policy: Deterministic Gate vs Native `/goal`

`/go` task-completion is decided by the **deterministic continuation gate**
(`scripts/go_continuation_gate.py`), registered as a direct project-settings
Stop hook (`P:/.claude/settings.json` `hooks.Stop[3]`). It reads
machine-readable `/go` state — not an LLM transcript judgment — so it does not
inherit the native goal-loop evaluator's intermittent "JSON validation failed"
failures.

**Policy:**

- **Do not pair native `/goal` with state-expressible `/go` task-completion
  work.** If the success condition is expressible in `/go` state (phase
  markers, `.pr_ready`, `.blocked`), let the deterministic gate drive
  continuation. Setting `/goal` on top re-enables the brittle native evaluator
  for no benefit.
- **Use deterministic `/go` state continuation for task-completion goals.**
- **Use tier-2 review/critic (e.g. `/av`, `/pre-mortem`, pi/GLM reviewers) for
  fuzzy quality goals** the gate cannot express (subjective correctness,
  design quality). Those are not state-expressible and legitimately belong to
  an LLM evaluator — but prefer a dedicated reviewer subagent over the raw
  native goal loop.
- **Warn when a setup appears to rely on native `/goal` unnecessarily.** If a
  `/go` run is active and a state-expressible completion condition is also
  set as a `/goal`, surface the redundancy: the deterministic gate already
  covers it.

The gate is **additive** — it does not disable the native evaluator (no plugin
API exists for that). It coexists as Stop[3] and is self-scoping: when no
state pointer exists for the current session, the gate prints nothing and is
inert in every non-`/go` session.

**Validation tasks:** Use `--validation` flag when running `/go` for
validation/audit/review/field-test tasks. This sets `task_type=validation` in
the task contract, which allows G5 (SDLC enforce gate) to accept Stop when the
validation contract is satisfied (`.pr-ready` or `status=completed`) without
requiring all SDLC hard gates. Implementation tasks always require full gates.

**Never use native `/goal` for state-expressible `/go` validation.** The native
goal-loop evaluator is flaky and can produce "JSON validation failed" errors.
Use the deterministic `/go` state checks (G4 + G5) instead.

---

## Required Environment

```bash
export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${GO_RUN_ID:-$(uuidgen)}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export GO_DISPATCH="${GO_DISPATCH:-pi}"
export GO_STATE_DIR="${CLAUDE_PROJECT_DIR:-P:/}.claude/.artifacts/${TERMINAL_ID}/go"
export GO_DEFAULT_VERIFICATION_COMMANDS="${GO_DEFAULT_VERIFICATION_COMMANDS:-python -m pytest -q}"
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
| Current session transcript | `identity.json` | Path to this session's transcript (read directly by the orchestrator) |
| Handoff transcript | `HANDOFF_TRANSCRIPT` | Path to prior session transcript |
| Plan file | `GO_PLAN_FILE` | Path to `.md` plan file |
| Task queue | `GO_TASKS_FILE` | JSON file with queued tasks |

Priority: `GO_PROMPT` > **current session transcript** > `HANDOFF_TRANSCRIPT` > `GO_PLAN_FILE` > `GO_TASKS_FILE`

When using prompt/transcript/plan, the task is synthesized into the contract below. When using the task queue, `/go` selects the eligible task with the lowest numeric `priority` value (`P1` before `P2`); file order breaks ties.

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

**Allowed `task_type` values:** `implementation`, `refactor`, `design`, `planning`, `testing`

(`testing` routes to `/t` — use for mutation audits, coverage strategy, or test architecture work. `/tdd --phase mutation --module <dotted>` is the **execution-side** route used during a TDD run as a side-channel quality gate; it writes a signed `MutationReceipt` that `validate_tdd.py` and `verification_result.mutation` both consume.)

---

## Routing Table

| Condition | Route |
|-----------|-------|
| Code behavior change needed | `/code` |
| Cleanup without behavior change | `/refactor` |
| Architecture or contract unclear | `/design_1.0` |
| Scope unclear or decomposition needed | `/planning` |
| Config/infra only | direct verify → reviews |
| Mutation testing or test audit (planning) | `/t --mode mutation` |
| Mutation gate during a TDD run (side-channel) | `/tdd --phase mutation --module <dotted.name>` |

---

## STEP 0: Worktree Provisioning

`/go` stays on `main`. For `pi`, it creates a worker worktree and dispatches the pi harness into it. For `local`, it skips worker creation and runs verification/review/artifact gates against the current checkout. For `claude`, it writes an unsupported-dispatch artifact and returns `<promise>BLOCKED</promise>`.

**Create a worktree for the task:**

```bash
TS=$(date +%Y%m%d-%H%M%S)
WORKTREE=".claude/worktrees/ai-task-$TS"
git worktree add -b "ai/ai-task-$TS" "$WORKTREE" HEAD
```

**Dispatch behavior:**

| Dispatch | Behavior |
|----------|----------|
| `pi` | Create `P:/worktrees/pi-task-*`, resolve model, run `pi -p --mode json --model <resolved>` |
| `local` | Use current checkout as the worktree for verification/review/artifact gates |
| `claude` | Write `dispatch-result_{RUN_ID}.json` with `unsupported-automated-dispatch`, then block |

`/go` remains on `main` throughout — it orchestrates, workers execute.

PI dispatch is headless and artifact-first:

- Session dir: `$GO_STATE_DIR/pi-sessions/$RUN_ID`
- Transcript/events: `$GO_STATE_DIR/pi-events_$RUN_ID.jsonl` and `$GO_STATE_DIR/pi-transcript_$RUN_ID.jsonl`
- Resume hint: `$GO_STATE_DIR/resume_$RUN_ID.txt`
- Dispatch artifact: `$GO_STATE_DIR/dispatch-result_$RUN_ID.json`
- Active run pointer: `$GO_STATE_DIR/current-run_$TERMINAL_ID.json`
- Conservative flags: `--no-context-files --no-extensions --no-skills --no-prompt-templates --no-themes`
- Tool allowlist: `GO_PI_TOOLS`, defaulting to `read,grep,find,ls,edit,write,bash`
- Timeout/binary/nonzero failures write `dispatch-result_$RUN_ID.json` and `.blocked_$RUN_ID`

---

## STEP 0.5: Synthesize from Current Session Transcript

When `GO_PROMPT` is empty, read the current session transcript directly and synthesize the task from the last substantive user directive. This uses the orchestrator's native context-reading ability — no hook injection required.

**Transcript path:** `~/.claude/.artifacts/{TERMINAL_ID}/identity.json` → `session.transcript_path`

**Synthesize from transcript:**
1. Read the transcript JSONL file
2. Scan backwards from the end
3. Skip meta-instructions (`thanks`, `summarize`, `revert`, slash-command invocations) and correction messages (`No, the task is not about...`, `That's not what I asked`)
4. Stop at session boundary (different `session_chain_id`) or topic shift
5. Take the first substantive directive found — this is the task goal
6. Synthesize into `active-task_{RUN_ID}.json` and proceed to STEP 1

**Output:** `active-task_{RUN_ID}.json` with the same contract shape as a queued task, with `source: "transcript"` and `message_intent` observability fields.

If no transcript path is found or the transcript cannot be read, fall back to `HANDOFF_TRANSCRIPT` → `GO_PLAN_FILE` → `GO_TASKS_FILE`.

---

## STEP 1: Task Acquisition

**From plan (GO_PLAN_FILE) — queue-pointer rule:** Before synthesizing, read the plan's
frontmatter. If it declares `go_tasks_file`, treat that path as `GO_TASKS_FILE` and acquire
from the **queue** (below) — this is what enables run-to-completion across all plan tasks
with plan-declared pause gates. Only fall back to single-task synthesis (next paragraph) when
no `go_tasks_file` is declared. This makes `/go <plan-path>` run the whole plan to completion.

**From intent (GO_PROMPT / HANDOFF_TRANSCRIPT / GO_PLAN_FILE):** Parse intent and synthesize a task contract. Write `active-task_{RUN_ID}.json`.
Prompt-synthesized tasks use `GO_DEFAULT_VERIFICATION_COMMANDS` split on `;` for verification. Set `GO_REQUIRE_EXPLICIT_VERIFICATION=1` to block prompt tasks unless that env var is explicitly set.

**From queue (GO_TASKS_FILE):** Select the highest-priority task with `status` in `{ready, queued, approved}`. Claiming uses a `tasks.json.lock` sidecar, writes `active-task_{RUN_ID}.json` before mutating the queue, then marks the source task `selected` with `selected_by` and `selected_at`. Stale locks older than `GO_TASK_LOCK_TTL_SECONDS` are recovered; default TTL is 3600 seconds.

```bash
python ".claude/skills/go/scripts/select-task.py"
STATUS=$?
# Plan-declared gate: only gated (requires_approval, not yet approved) tasks remain.
if [ -f "$GO_STATE_DIR/.paused_$RUN_ID" ]; then
  cat "$GO_STATE_DIR/.paused_$RUN_ID"
  echo "<promise>PAUSED_FOR_APPROVAL</promise>"
  exit 0
fi
# exit 2 with no pause flag = queue genuinely empty → plan complete.
if [ "$STATUS" -eq 2 ]; then
  echo "<promise>ALL_TASKS_COMPLETE</promise>"
  exit 0
fi
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.task-selected_$RUN_ID"
```

---

## STEP 1.5: Classify Complexity

Read `active-task_{RUN_ID}.json` and classify complexity. Select model for Bifrost routing.

```bash
python ".claude/skills/go/scripts/classify_complexity.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
```

Output: `model-selection_{RUN_ID}.json` with `{tier, model, confidence, signals}`.

| Tier | Model Selection | Task types |
|------|---------------|------------|
| T1-T3 | PI routing (see `/ai-cli --pi-model`) | implementation, refactor, config |
| T4 | PI routing (see `/ai-cli --pi-model`) | design, planning |

Override: `GO_MODEL_OVERRIDE` env var bypasses classification (use PI model format).

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
python ".claude/skills/go/scripts/review-passes.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.reviews-passed_$RUN_ID"
```

---

## STEP 6: QA Verification (GTO)

Run GTO quality verdict after 7-pass review, before PR artifacts. Routing-aware: design/planning tasks skip QA.

```bash
python ".claude/skills/go/scripts/run-qa-verification.py"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  QA_VERDICT="$GO_STATE_DIR/qa-verdict-${RUN_ID}.json"
  if [ -f "$QA_VERDICT" ]; then
    QA_STATUS=$(python -c "import json; print(json.load(open('$QA_VERDICT'))['qa_status'])")
    echo "QA failed with status: $QA_STATUS"
  fi
  ATTEMPT_NEXT=$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
  [ "$ATTEMPT_NEXT" -ge "$MAX_ATTEMPTS" ] && touch "$GO_STATE_DIR/.blocked_$RUN_ID" && echo "<promise>BLOCKED</promise>" && exit 1
  exit 1
fi
touch "$GO_STATE_DIR/.qa-passed_$RUN_ID"
```

Output: `qa-verdict-{RUN_ID}.json` with `qa_status` in `{accept, accept-with-concerns, redo, error, skipped}`.

**qa_status mapping:**
- `accept` — all gates 0, GTO status accept
- `accept-with-concerns` — escape_hatches > 0 OR mixed_substance > 0 OR unverified_impl_claims > 0
- `redo` — GTO status revise/reject/blocked
- `error` — runner crashed or produced unparseable output
- `skipped` — task_type is design/planning (QA not applicable)

**go is NOT blocked globally.** This step's non-zero exit means QA found concerns — go's local policy decides whether to proceed. `accept-with-concerns` exits 0 and continues.

---

## STEP 6.5: Mutation Gate (Critical-Path Modules)

For `implementation` tasks, check if any modified module is declared `tier: critical` in `quality_gates.json`. If so, mutation testing is **mandatory** before PR artifacts.

```bash
python ".claude/skills/go/scripts/mutation-gate.py"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  echo "ERROR: Mutation gate failed — critical-path module did not meet mutation score threshold."
  ATTEMPT_NEXT=$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
  [ "$ATTEMPT_NEXT" -ge "$MAX_ATTEMPTS" ] && touch "$GO_STATE_DIR/.blocked_$RUN_ID" && echo "<promise>BLOCKED</promise>" && exit 1
  exit 1
fi
touch "$GO_STATE_DIR/.mutation-passed_$RUN_ID"
```

Script logic:
1. Select modules from `GO_MUTATION_MODULES` when set; otherwise intersect `git diff --name-only HEAD` with critical-tier modules in `quality_gates.json`.
2. If no critical mutation target is selected, emit `mutation-gate-{RUN_ID}.json` with `status: skipped`, write `verification-result_{RUN_ID}.json` with `mutation.status: not-run`, and exit 0.
3. For each selected critical-tier module, run the shared `/t` mutation runner (`mutmut 3.x`) through `mutation_mode.run_mutation_for_module()`.
4. Treat `passed` and `waived` as non-blocking. Treat `failed`, `timeout`, `blocked`, and selected-module `skipped` as blocking when `quality_gates.json` has `block_pr_on_failure: true`.
5. On block, write `blocked_{RUN_ID}.json` with `reason_code: mutation_failed`, touch `.blocked_{RUN_ID}`, and exit 1.

**Artifacts:** `mutation-gate-{RUN_ID}.json` contains `{schema_version, run_id, status, modules[], generated_at}` plus `blocking_modules[]` when applicable. Each module entry carries `{module, tier, target_score, mutation_score, killed, survived, skipped, timeout, status, receipt_path}`. `verification-result_{RUN_ID}.json` mirrors the latest module summary under `mutation` and records `artifact_paths.mutation_gate`; when there is no separate signed TDD receipt, `mutation.receipt_path` points to the mutation-gate artifact itself.

**Result ingestion:** the per-run `verification-result.mutation` block (see `schemas/verification-result.schema.json`) carries the latest gate summary into the readiness object, and `run-status.active_route` may be set to `"mutation"` while a mutation phase is executing (returns to `"code"` on completion). Mutation is a **side-channel** quality gate — it does not block the TDD lifecycle phase machine, so `validate_tdd.py` and `verify-task.py` both consult `evidence.mutation` / `verification_result.mutation` independently of `phase`.

---

## STEP 7: Local PR Artifacts

Generate commit message, PR title, PR body, PR-ready report.

```bash
python ".claude/skills/go/scripts/pr-artifacts.py"
touch "$GO_STATE_DIR/.pr-ready_$RUN_ID"
echo "<promise>PR_READY</promise>"
```

---

## STEP 8: Loop Check

Check if more eligible tasks remain, then **continue automatically**. `/go` runs the
plan to completion: it stops ONLY on `PAUSED_FOR_APPROVAL` (a plan-declared gate),
`BLOCKED`, `MAX_ATTEMPTS`, or `ALL_TASKS_COMPLETE`. **Never stop mid-plan to ask
"should I continue?"** — that decision belongs to the plan's `requires_approval`
markers, not a mid-run judgment. This is the run-to-completion rule.

```bash
LOOP_TOKEN="$(python ".claude/skills/go/scripts/loop-check.py")"
echo "$LOOP_TOKEN"
```

- **`MORE_TASKS_IN_PLAN`** → loop back to **STEP 1** (Task Acquisition) in the same
  worktree. Do **not** re-run STEP 0 — the worktree persists across every task in the
  run. `select-task.py` emits `PAUSED_FOR_APPROVAL` on its own if the next task is
  `requires_approval: true` and not yet `approved`; you do not need to pre-check.
- **`ALL_TASKS_COMPLETE`** → the run is complete. Stop.

---

## Prohibited Actions

- Workers making direct changes on `main` or `master`
- Using `plan.md` as scheduler source
- Proceeding without required prior flag
- Ignoring failed verification commands
- Ignoring HIGH/CRITICAL simplify findings
- Auto-pushing or creating remote PRs
- Modifying `forbidden_files` listed in task contract
- **Stopping mid-plan to ask whether to continue** — the run stops ONLY on `PAUSED_FOR_APPROVAL` (a `requires_approval` gate), `BLOCKED`, `MAX_ATTEMPTS`, or `ALL_TASKS_COMPLETE`. A `MORE_TASKS_IN_PLAN` result at STEP 8 means loop back to STEP 1, not pause for direction.

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
