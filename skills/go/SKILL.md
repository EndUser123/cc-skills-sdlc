---
name: go
version: 2.12.0
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
  PreToolUse:
    - matcher: .*
      hooks:
        - type: command
          command: python "$CLAUDE_PLUGIN_ROOT"/skills/go/hooks/go_delegation_enforce_PreToolUse.py
          description: Enforce delegation_policy mutation authority at the tool-call boundary
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
| `claude` | Native Claude Code subagent. The orchestrator writes `claude-task-request_{RUN_ID}.json` and returns `<promise>SPAWN_CLAUDE_SUBAGENT</promise>`; the main-loop Claude spawns the in-session `Agent(...)` call, writes `claude-task-result_{RUN_ID}.json`, then resumes via `--claude-resume`. Worker mutation scope is enforced by the PreToolUse delegation gate (TASK-001.4). Opt out with `GO_DISABLE_CLAUDE_TASK_SUBAGENT=1`. |

---

## What /go Must Do

1. Enforce worktree + branch preconditions (auto-create if on main)
2. Acquire a task from one of three input sources
3. Classify task complexity → select model via Bifrost
4. Dispatch through `pi`, run local verification, or hand off to a native Claude subagent
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
- `<promise>SPAWN_CLAUDE_SUBAGENT</promise>` — `--dispatch claude` phase 1 complete: `claude-task-request_{RUN_ID}.json` written. The main-loop Claude must spawn the in-session `Agent(...)` call with the request's `model`/`tools`/`prompt`/`subagent_type`, write `claude-task-result_{RUN_ID}.json`, then re-invoke the orchestrator with `--claude-resume <RUN_ID>` for phase 2 (verify/review/artifact tail).
- `<promise>SPAWN_COMPLETION_VERIFIER</promise>` — Step 9.7 (high-risk only): `completion-verify-request_{RUN_ID}.json` written and `.completion-verify-pending_{RUN_ID}` set. The main-loop Claude must spawn a **read-only** verifier `Agent(...)` (`tools: [Read, Grep, Glob, Bash]`, no mutation), compare the task's `acceptance_criteria` against the diff/worker report, write `completion-verify-result_{RUN_ID}.json` (schema `completion-verifier.v1`: `verdict: PROCEED | ADVISORY_REVISE | BLOCK`, plus `addressed/omitted/uncertain/evidence`), then re-invoke the orchestrator with `--completion-verify-resume <RUN_ID>` to run pr-artifacts + tail. Advisory-first: `ADVISORY_REVISE` is surfaced but does **not** hard-block `.pr-ready`. Opt the whole gate out with `GO_COMPLETION_VERIFY_SKIP=1`. See STEP 6.7.

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
  markers, `.pr_ready`, `.blocked`, or `task.done_when`), let the
  deterministic gate drive continuation. Setting `/goal` on top re-enables
  the brittle native evaluator for no benefit.
- **When `done_when` is set, the orchestrator runs it as the primary
  completion check** — before the phase-marker gate. Exit code 0 = done,
  non-zero = not done. This is the binary proof the 9-section template
  requires.
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
| Plan-handoff (bare `/go`) | — | Auto-bind freshest implementation-ready plan with `go_next_task` (see STEP 0.4) |
| Current session transcript | `identity.json` | Path to this session's transcript (read directly by the orchestrator) |
| Handoff transcript | `HANDOFF_TRANSCRIPT` | Path to prior session transcript |
| Plan file | `GO_PLAN_FILE` | Path to `.md` plan file |
| Task queue | `GO_TASKS_FILE` | JSON file with queued tasks |

Priority: `GO_PROMPT` > **plan-handoff resolver (bare invocation only)** > **current session transcript** > `HANDOFF_TRANSCRIPT` > `GO_PLAN_FILE` > `GO_TASKS_FILE`

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
  "done_when": "pytest tests/test_target.py exits 0",
  "stop_rules": { "max_turns": 10, "max_attempts": 3 },
  "output": "Summary of changes + test results",
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
  "done_when": "pytest -q exits 0",
  "stop_rules": { "max_turns": 10, "max_attempts": 3 },
  "output": "Files changed, test output, any caveats",
  "task_type": "implementation",
  "requires_approval": false
}
```

**Allowed `task_type` values:** `implementation`, `refactor`, `design`, `planning`, `testing`

**New fields (from 9-section `/goal` template alignment):**

| Field | Type | Purpose |
|-------|------|---------|
| `done_when` | string | **Single binary observable condition** — a command whose exit code 0 = done. This is the authoritative completion signal. `acceptance_criteria` are supplementary. |
| `stop_rules.max_turns` | integer | Hard cap on LLM turns before force-stop. Prevents infinite loops. Default: 10. |
| `stop_rules.max_attempts` | integer | Max retry attempts on verification failure. Default: 3. Overrides global `MAX_ATTEMPTS`. |
| `output` | string | What to surface when done — summary, test results, artifacts. |

**Why `done_when` exists alongside `acceptance_criteria`:**
- `acceptance_criteria` is a list of conditions ("tests pass", "no regressions", "docs updated") — useful for human review
- `done_when` is a **single executable command** that the orchestrator can run to prove completion — useful for deterministic gating
- Example: `done_when: "pytest tests/test_auth.py"` is a concrete, runnable proof. `acceptance_criteria: ["auth tests pass"]` is the human-readable version of the same thing.

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
| `claude` | Phase 1: write `claude-task-request_{RUN_ID}.json` (tier-resolved model, scrubbed prompt, tools, scope) and return `<promise>SPAWN_CLAUDE_SUBAGENT</promise>`. Phase 2 (below): main-loop Claude spawns `Agent(...)`, then `--claude-resume` runs the tail. |

`/go` remains on `main` throughout — it orchestrates, workers execute.

**Submodule-aware provisioning (#916).** `create_worktree` resolves each `scope_in` path to its nearest `.git` root and creates the worktree via `git -C <repo>` — so a task targeting an embedded/gitlink plugin (cc-skills-sdlc, skill-guard, snapshot, cc-skills-ai-api, cc-skills-media, cc-skills-utils, search-research — gitlinks without `.gitmodules`) gets a *populated* worktree, not an empty parent-level dir. `scope_in` spanning more than one git repo → `<promise>BLOCKED</promise>` (split the task). Override the worktree root with `GO_WORKTREE_ROOT` (default `P:/worktrees`).

### Claude native-subagent dispatch (two-phase)

`/go` runs as a Bash-invoked Python script and cannot call the in-session
`Agent(...)` tool itself, so Claude dispatch is split into two phases around
the spawn:

**Phase 1 — request write (orchestrator):** `dispatch_claude()` reads
`active-task` + `task-proposal`, resolves the tier model
(`direct_answer`→haiku, `local_surgical`/`local_rigorous`/`full_go`→sonnet,
`pause_for_authorization` or `task_type=design`→opus; advisory), scrubs the
assembled prompt, and writes `claude-task-request_{RUN_ID}.json`:

```json
{"run_id":"...", "model":"sonnet", "subagent_type":"general-purpose",
 "tools":["Read","Grep","Glob","Edit","Write","Bash"], "prompt":"...",
 "scope_in":[...], "forbidden_files":[...], "execution_tier":"...", "task_type":"..."}
```

It emits `.dispatched_{RUN_ID}` + `.delegation-worker_{RUN_ID}` (the PreToolUse
gate activates worker-scope enforcement), then returns
`<promise>SPAWN_CLAUDE_SUBAGENT</promise>`. Opt out with
`GO_DISABLE_CLAUDE_TASK_SUBAGENT=1` (writes `blocked_{RUN_ID}.json`).

**Phase 2 — spawn + resume (main-loop Claude):** when the orchestrator emits
`SPAWN_CLAUDE_SUBAGENT`, the main-loop Claude:

1. Reads `$GO_STATE_DIR/claude-task-request_$RUN_ID.json`.
2. Invokes the in-session `Agent(...)` tool with `subagent_type`, `model`,
   `tools`, and `prompt` from the request. Worker mutation scope is enforced
   by the `go_delegation_enforce_PreToolUse` gate (TASK-001.4) and the
   `tools:` allowlist (hard enforcement — memory #1120).
3. Writes `claude-task-result_$RUN_ID.json` (`{run_id, status, summary, ts}`).
   If the worker observed code-level structural issues while doing the task, it
   MUST also populate a `discovery_evidence` field (or write a sibling
   `discovery-evidence_$RUN_ID.json`) so the merge reader can escalate to
   `/refactor`. Each finding needs `source` (what produced it), `provenance`
   (`verified` | `inference` | `assumption`), `summary`, optional
   `structural_issues` from the canonical set
   (`dead_producer_consumer`, `inert_code`, `duplicated_responsibility`,
   `wrong_layer_ownership`, `repeated_patching`, `state_identity_lifecycle_ambiguity`,
   `broad_cross_file_change_needed`, `excessive_test_setup_due_to_design_complexity`),
   and `evidence` (file/path/grep/test citation — REQUIRED when `provenance="verified"`).
   Report only what was actually observed; never fabricate findings.
4. Re-invokes the orchestrator:
   ```bash
   GO_RUN_ID="$RUN_ID" python ".claude/skills/go/scripts/orchestrate.py" --claude-resume "$RUN_ID"
   ```
   This runs the common tail (verify → simplify → 7-pass → QA → artifacts) on
   the current checkout — no worktree, the subagent worked in-place.

The tier map is advisory; the PreToolUse gate is the load-bearing mutation
control regardless of which model the subagent runs on.

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

## STEP 0.4: Bare-Invocation Plan-Handoff Resolver

When `/go` is invoked with no `--prompt`, `--plan`, or `--tasks` (the bare
`/go` handoff pattern — e.g. right after `/planning` says "say the word"),
`scripts/resolve_plan_handoff.py` scans `~/.claude/plans/*.md` for a plan
that is **ready to resume**:

- frontmatter `status: implementation-ready`
- frontmatter `unresolved_blockers: 0`
- a `go_next_task` block declaring the explicit next task

The `go_next_task` frontmatter contract (written by `/planning` or the plan
author when the plan becomes implementation-ready):

```yaml
go_next_task:
  task_id: TASK-001.1
  title: short title
  objective: one-sentence objective (full contract lives in the plan body)
  verification_commands: pytest -q, python -m pytest tests/   # optional, comma-delimited
  priority: P1                                              # optional, default P1
```

**Resolution rules:**

| Candidates | Exit | Behavior |
|------------|------|----------|
| Exactly 1 | 0 | Bind: write `active-task_{RUN_ID}.json` (`source: "plan-handoff"`) with a `plan_binding` block pointing at the source plan. Freshest plan (by mtime) wins. |
| >1 | 2 | Pause: write `.paused_{RUN_ID}` listing candidates; the run stops — disambiguate by passing `GO_PLAN_FILE`. |
| 0 | 3 | Fall through to `select-task.py` (`GO_TASKS_FILE` queue). STEP 0.5 transcript synthesis does not run on the bare-invocation path — it is reached only when `GO_PROMPT`/transcript input is present. |

The resolver carries only what is needed to **identify and start** the task
(`task_id`, `title`, `objective`, `verification_commands`). The full task
contract — acceptance criteria, scope, invariants — lives in the plan body;
the worker reads it via `active-task.source_ref → plan_path`.

The resolver is skipped when `GO_PLAN_FILE` is set (explicit plan pointer) or
when `--tasks` is passed (explicit queue). It fires only on the fully-bare
invocation that previously fell through to transcript synthesis, losing the
plan's constraints.

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

## Discoverability rule — before declaring blocked (missing_input)

`/go` is the **primary owner** of the discoverability classification. Before
declaring a task blocked on missing input, emit:

```
missing_input: <what's missing>
discoverability: DISCOVERABLE | USER_ONLY | UNKNOWN
discovery_attempted: <tool run + result, or "none">
evidence: <file:line / command output / "not found">
remaining_need: <what's still missing after discovery>
```

**Rule:** if `discoverability` is `DISCOVERABLE`, run the discovery BEFORE
emitting blocked. A read-only command, grep, file read, filesystem search,
repo search, or web/search tool can answer it. Asking the user for a
DISCOVERABLE fact is a contract violation equal to inventing it — both
offload work the agent should do.

Only emit `USER_ONLY` (and ask the user with a precise `NEED: <question>`)
when the fact is a preference, approval, credential, intent, private fact,
destructive permission, budget decision, or inaccessible system.

Full rule + worked examples at
`cc-skills-analysis/skills/debrief/references/discoverability-classification.md`.

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

## STEP 1.6: Task Intent & Execution Tier (Ceremony Policy)

The preflight artifact (`task-proposal_{RUN_ID}.json`, from `scripts/preflight_propose.py`)
classifies the prompt on **two orthogonal axes**:

- **`task_type`** (routing axis, in `active-task`): `implementation | refactor | design | planning | validation | testing` — decides *where* a task routes (`/code`, `/refactor`, `/design`, `/planning`, `/t`).
- **`task_intent`** (ceremony axis, in the proposal): `implement | investigate | validate | decide | mixed` — decides *how* `/go` runs.

`task_intent` drives `execution_tier` and `report_gate`. Read these from the proposal before STEP 2.

**`execution_tier` values** (minimum sufficient ceremony):

| Tier | When | Ceremony |
|------|------|----------|
| `direct_answer` | conversational / status / pure evidence lookup | answer directly, no dispatch, no mutation |
| `local_surgical` | small isolated low-risk patch | local edit → targeted tests → direct smoke → report |
| `local_rigorous` | local patch touching higher-risk surface | local edit → targeted tests → direct smoke → **registered-path smoke** → report |
| `full_go` | `pi` dispatch, implementation work | worktree → dispatch → verify → simplify → 7-pass → QA → PR artifacts |
| `pause_for_authorization` | `decide`, or high-risk without prompt-review support, or `requiresApproval` | emit `decision_advisory` and STOP — no dispatch |

**Ceremony rules by `task_intent`:**

| Intent | Execution | Report gate |
|--------|-----------|-------------|
| `investigate` | evidence ledger + recommendation; `local_surgical` if read-only recon else `direct_answer` | **no implementation-completion claim** |
| `validate` | validation artifact; `local_surgical`/`direct_answer` | **no implementation-completion claim**; no full SDLC gates unless implementation is also requested |
| `decide` | `decision_advisory` then `pause_for_authorization` (unless `agent_decidable`) | **no implementation-completion claim** |
| `implement` | tier by risk (`local_surgical`/`local_rigorous`/`full_go`) | completion claim allowed only at `full_go`/`local_rigorous`; `local_surgical` may claim a targeted fix only |
| `mixed` | split in prose/report; execute only items the user request already authorized; defer decisions with recommendations | **no bundled completion claim** across deferred items |

**`/go` may skip delegation for small tasks, but MUST NOT skip the chosen tier's minimum verification.**

### Report gate (no false completion)

The proposal's `report_gate` field carries `allow_implementation_completion_claim`. If it is `false`:

- Do NOT emit `<promise>PR_READY</promise>` or "Fixed."/"Done."/"Verified." for that run.
- Emit the evidence ledger / validation artifact / decision advisory instead, with an explicit note that no implementation-completion claim is being made.
- **Scoped-test reporting (no greenwashing):** a targeted green suite MUST NOT obscure broader red state. When reporting verification, scope the claim to the exact suite run ("intent/mixed-report tests: 48/48 pass") and explicitly name any known unrelated failures in the broader suite ("full /go suite: 8 known unrelated failures tracked as #1115"). Never say "all verification green" globally when any suite covering the changed surface is red.
- For `mixed`: name which children were executed and which were deferred. Use this sentence template when splitting:

> This is mixed work. I executed the authorized low-risk item(s) now: `[A]`. I produced evidence for the investigation item(s): `[B]`. I am leaving the design/decision item(s) `[C]` unimplemented until you approve, because `[reason]`.

### Closure check — reproduce-first + confirm-closed (reqs. 1-11)

Bugfix / regression / hook-FP / stale-warning tasks must prove the **original symptom** is gone, not just that a related test passes. The proposal carries a `closure_check` block and a `repro_policy` block, derived deterministically from prompt markers.

`closure_check` schema (req. 2):

| Field | Meaning |
|-------|---------|
| `required` | true for bugfix/regression/hook-FP/stale-warning intents (req. 3) |
| `source` | `user_reported_symptom` \| `repro_command` \| `field_failure` \| `hook_fp` \| `regression` \| `none` |
| `command_or_procedure` | the repro / closure command — **worker fills** |
| `expected_before` | the failing repro / observed symptom — **worker fills** |
| `expected_after` | what the symptom looks like AFTER the fix — **worker fills** |
| `evidence_path` / `evidence_summary` | pre-fix failing repro + post-fix symptom-gone evidence — **worker fills** |
| `unavailable_reason` | set ONLY when direct closure is genuinely impossible (req. 4) |
| `reproduce_first_required` | mirrors `required` (req. 5) |
| `cannot_reproduce_artifact_allowed` | true when prompt signals flaky/intermittent/non-deterministic |
| `registered_path_required` | true for hook-FP / high-risk surfaces — use the actual entry point or registered path (req. 7) |

**Reproduce-first (req. 5):** for required tasks the worker produces either a **pre-fix failing repro/test**, or a `cannot_reproduce` / `no_pre_fix_repro` artifact with evidence. A cannot-reproduce artifact lets the report *proceed* but does **NOT** authorize a "Fixed" claim over the original symptom.

**Confirm-closed (reqs. 4, 6, 11):** a task may NOT claim `fixed` / `complete` / `Done` / `Verified` unless `confirm_closed_passes(closure_check)` — which requires `evidence_path`/`evidence_summary` **AND** `expected_after` — OR `unavailable_reason` is set. **A passing unit test alone is NOT sufficient** (`report_gate.unit_test_alone_is_insufficient: true`). Confirm-closed must re-check the **original reported symptom** (req. 6); for hook/gate/state/identity/cache/plugin issues it must use the **actual entry point or registered path** (req. 7).

**Defaults (req. 9):** missing/malformed `closure_check` on a required task blocks silent completion (`allow_implementation_completion_claim: false` at preflight; `notes` surfaces `CLOSURE_CHECK required`). investigate/validate/decide tasks default to `required=false` (req. 8) and MUST NOT use fixed/completed language.

**Report content (req. 10):** when `closure_check.required`, `plain_english_report.closure_report` scaffolds five content fields the worker fills — `original_symptom`, `reproduce_first_evidence` (or `reproduce_first_unavailable_reason`), `verification_tests`, `confirm_closed_evidence`, `remaining_risk` — plus `may_claim_fixed` (the `confirm_closed_passes` verdict). Until these are populated, the report may not claim completion.

### Discovery-first — operational questions, verification ranking, lifecycle hygiene

Operational questions involving **hooks, gates, worktrees, state, markers, cache, dispatch, sessions, exports, or artifact lifecycle** get a discovery contract before any implementation prescription. The proposal carries an `operational_discovery` block.

**Discovery-first (reqs. 2, 3):** before recommending implementation, identify and (when cheap to inspect) observe:
1. writer/creator · 2. storage/location · 3. reader/consumer · 4. lifecycle/cleanup path · 5. authority · 6. stale/failure direction · 7. observed current state

Do not guess from memory or trace only the easiest path — discover the real writer/reader/lifecycle by reading the code, then state what was observed vs. what was only inferred.

**Verification ranking (req. 4):** when confidence is uncertain (investigate/decide/mixed), `operational_discovery.verification_paths` lists ≥2 paths ranked by confidence-per-effort:

| Path | Confidence | Effort |
|------|-----------|--------|
| empirical end-to-end reproduction against a real oracle | highest | high |
| direct invocation of the registered entry point (hook/router) | high | medium |
| integration test crossing the real state/dispatch boundary | high | medium |
| targeted unit test on the pure-logic transform | medium | low |
| static code trace (grep/read of writer/reader path) | medium-low | low |

`empirical_oracle_preferred = true`. State what tracing proves and misses: empirical reproduction proves the symptom is gone **for the tested path** but not the writer/reader invariant in every branch or under concurrency; static trace proves the invariant but not the runtime.

**Lifecycle hygiene (req. 5):** `/go`-created resources — worktrees, branches, state dirs, session pointers, markers, cache copies, temporary exports/artifacts — carry a cleanup obligation. `operational_discovery.lifecycle_resources` enumerates which the prompt touches.

**Worktree prune predicate (req. 6):** `operational_discovery.worktree_prune_predicate` is the *only* authorized prune path, and it is **report-only + approval-gated** — ALL conditions must hold:

- age ≥ threshold (default 14d since creation)
- `git status` clean (no uncommitted / unstaged work)
- branch merged into main OR explicitly marked disposable by the director
- report-only dry run first (list, do not remove)
- **no removal without explicit director approval**

Never auto-delete unverified work. SessionStart may surface the reclaimable count but must not delete.

**Report evidence (reqs. 7, 8) — gate-enforced, not scaffold-only:** when `operational_discovery.required`, `plain_english_report.discovery_evidence` scaffolds **before** `what_i_recommend` and the report gate refuses to present the recommendation as verified until findings exist and each carries a valid `provenance` tier ∈ {`verified`, `inference`, `assumption`}. If findings are empty or any provenance is missing/invalid, the gate sets `discovery_incomplete = true`, `allow_recommendation_as_verified = false`, demotes `what_i_recommend` to advisory ("advisory, NOT verified — discovery incomplete"), and adds a `discovery_incomplete` line to `what_is_blocked`. Verified fact, inference, and assumption stay visibly distinct, never flattened into one claim.

**Surface matching (reqs. 1, 2):** operational surfaces are detected by **word-boundary** token match (`\bmarker(s)?\b` for alphanumeric markers; literal substring for symbolic ones like `.artifacts`, `router.py`), so a bare marker like `gate` does **not** fire inside `investigate`. Plural form (`worktrees`, `markers`, `branches`) is tolerated.

**No silent cleanup (req. 9):** `operational_discovery.cleanup_requires_approval = true`. No cleanup action runs without explicit approval.

### Mechanism-change resolution (`mechanism_change`)

When `operational_discovery.required` is already true (the existing source-anchored discovery contract), the proposal also carries a `mechanism_change` block so a meta-change task resolves the change against existing machinery **before editing**:

- `closest_existing_mechanisms` — the worker names the nearest existing mechanism(s) after reading source (anti-duplication).
- `extension_path` — the worker resolves the change as exactly one of `NO_CHANGE | CLARIFY_EXISTING | EXTEND_EXISTING | SIMPLIFY_EXISTING | NEW_MECHANISM_JUSTIFIED | BLOCKED`.

**No-edit enforcement:** if `extension_path` resolves to `NO_CHANGE` or `BLOCKED`, the report gate sets `mechanism_change_report_only = true` and `allow_implementation_completion_claim = false` — `/go` reports only and does **not** edit. The plain-English report surfaces this in `what_is_blocked`.

**New gate/classifier discipline:** `NEW_MECHANISM_JUSTIFIED` for a new *blocking* gate/classifier requires real corpus/eval evidence (expected TP + acceptable FP). If `closest_existing_mechanisms` is empty under `NEW_MECHANISM_JUSTIFIED`, the gate flags `mechanism_change_new_unjustified` (advisory) — the director decides; it is never silently accepted as completion.

**Activation boundary (intentional):** there is **no prompt keyword classifier** for meta-change. Real `/go` prompts are dominated by plan-handoff resumptions ("continue", "proceed", "implement the plan"); meta-change intent lives upstream in `/design` or `/planning` artifacts, not in `/go` prompt text. Activation rides the existing `operational_discovery.required` signal, or an `upstream_signal` passed through by the orchestrator when a plan/design handoff declares a mechanism-change task (a future extension point — today the worker fills `extension_path` via the discovery-evidence merge from `discovery-evidence_{run_id}.json` or `claude-task-result_{run_id}.json`).

### Mixed-work status (`mixed_work_status`)

The single old `pause_for_authorization` bucket conflated four different situations. The proposal now carries `mixed_work_status` so the report can say *why* `/go` paused:

| Status | Means | Ask the user? |
|--------|-------|---------------|
| `partial_readonly_done` | Safe read-only narrowing already proceeded (investigate/validate, no mutation) | No |
| `recommendation_ready` | `decide` intent; advisory produced, awaiting director | Yes — for a decision, not approval |
| `pause_for_authorization` | Genuine shared-state authority (e.g. `settings.json`/`hooks.json`/`router.py` mutation) | Yes |
| `blocked_prerequisite` | Missing evidence (corpus/baseline/transcript) or high-risk surface without prompt-review support | **No** — state the blocker + next evidence step |
| `blocked_policy` | Prompt tries to weaken a gate/hook (fail-open, demote-to-warn, bypass, exempt) | **No** — state the policy block; propose as a separate decision |

**Req. 7 (do not ask the user to approve a blocker):** `blocked_prerequisite` and `blocked_policy` MUST NOT request user approval. State the blocker and the next evidence-gathering step (e.g. "produce the missing corpus, then re-run"). Only `pause_for_authorization` and `recommendation_ready` may address the user.

### Per-item authority (`decision_kind`)

| Kind | When | Ask the user? |
|------|------|---------------|
| `safe_readonly_next_step` | investigate/validate or `direct_answer` | No — auto-execute |
| `agent_decidable` | low-regret reversible implement at `local_surgical`/`local_rigorous` | No |
| `user_preference` | `decide` intent | Yes — decision |
| `shared_state_authorization` | shared config mutation (`settings.json`, `hooks.json`, `plugin.json`, `router.py`, `.env`, marketplace) | Yes — authority |
| `blocked_by_missing_evidence` | missing corpus/baseline/transcript | **No** — evidence step |
| `blocked_by_policy` | gate-weakening intent | **No** — policy block |

### Plain-English report format (reqs. 8, 10, 11, 16.l)

Every `/go` report carries `plain_english_report` with four sections, emitted in this fixed order — **before** any internal label (`pause_for_authorization`, `blocked_prerequisite`, `prompt_review_required`, `prompt_review_support=absent`):

1. **What I did** — concrete actions taken (files read, commands run, mutations made or none).
2. **What I recommend** — the recommendation and the next step (evidence-gathering for blockers, the advisory for `decide`).
3. **What is blocked** — only `blocked_prerequisite`/`blocked_policy` items; explicitly note "not asked of you (req. 7)".
4. **What I need from you** — only `pause_for_authorization`/`recommendation_ready` items; for `partial_readonly_done` this is "Nothing right now."

Internal labels (`mixed_work_status`, `decision_kind`, `execution_tier`) appear **only after** these four sections.

**No-mutation evidence requirement (req. 16.l):** any "no mutation performed" / "read-only" claim in **What I did** MUST be backed by `git status --short` (or equivalent) evidence shown in the report. The proposal sets `plain_english_report.no_mutation_evidence_required: true` to flag this. Do not claim "no mutation" without showing `git status --short` output.

### `prompt_review_required` (high-risk surfaces)

When the prompt matches a high-risk surface — **hook/gate/state/identity/dispatch/cache/plugin** (`Stop`, `PreToolUse`, `PostToolUse`, `SessionStart`, `router`, `settings.json`, `hooks.json`, `plugin.json`, auth tokens) — the proposal sets `prompt_review_required: true`.

Today `prompt_review_support: "absent"` (no prompt-review artifact gate exists yet). Therefore:

- The execution tier becomes `pause_for_authorization`.
- `run_preflight` writes a tracked prerequisite artifact: `prompt-review-prerequisite_{RUN_ID}.json`.
- **Do NOT pretend review occurred.** Either block the high-risk dispatch, or surface the prerequisite and proceed only with explicit director authorization recorded in the run report.

### Artifact freshness

A proposal authorizes dispatch or completion **only when its `runid` matches the current `RUN_ID`**. `assert_fresh(proposal, run_id)` enforces this. A stale or mismatched proposal (different run, or pre-preflight-regeneration) must be regenerated before it can authorize anything. Missing/malformed/ambiguous `task_intent` defaults to `implement` → `full_go` (never a silent direct edit).

---

## STEP 1.7: Delegation Policy (Role / Authority / Freshness)

`delegation_policy` is emitted on every proposal. It assigns bounded roles across the surfaces /go can delegate to — **no new multi-agent orchestrator**; the existing preflight classifier computes it deterministically.

**Roles** (`roles.worker`, `roles.advisory_reviewer`):
- `claude_main` — orchestrator, integrator, final reporter.
- `claude_subagent` — **default** bounded Claude reviewer/worker when context protection is enough. Preferred over `pi_ccr` whenever the goal is only context protection and no model diversity / failover / local execution is needed.
- `local_fast` — cheap fast local advisory reviewer; may be the `local_surgical` worker when `dispatch="local"`.
- `agy` — adversarial outside-model reviewer for prompt/design/ROI/decision tasks (`decide` intent or adversarial markers).
- `pi_ccr` — model-diverse external worker/reviewer, failover route, or isolated harness route. Selected as worker **only** at `full_go` when a model-diversity marker is present.

**Mutation authority** (`mutation_authority`, fixed per role):
- Advisory reviewers (`agy`, advisory-mode `local_fast`/`claude_subagent`) **cannot mutate** repo or shared state.
- `claude_subagent` worker may mutate **only** within the explicitly assigned bounded scope.
- `local_fast` worker may mutate **only** for explicitly selected `local_surgical` tasks.
- `pi_ccr` may mutate **only** in an isolated worktree / `full_go` path — never the main tree directly.
- **Final completion authority stays with the /go evidence gates**, not any worker (`final_authority`).

**Blocking** (`required_review`, `blocking`):
- Non-blocking advisory review may fail without blocking low-risk tasks.
- High-risk hook/gate/state/identity/dispatch/cache/plugin tasks set `required_review=true`; at `pause_for_authorization` the review is `blocking=true` — missing/stale/rejecting review blocks dispatch.

**Freshness** (`freshness`):
- Advisory artifacts must match `run_id` **and** `prompt_hash` (`assert_advisory_fresh`).
- Diff reviews must also match `diff_hash` (unknown at preflight; required when a diff-review artifact is produced).

**Advisory is evidence, not authority** (`advisory_is_evidence_not_authority: true`): reviewer output is reported as evidence for the director; it never authorizes completion on its own.

**Enforcement boundary** (`worker_scope`, `worker_enforcement`): mutation authority is enforced at two real boundaries, not in policy text alone.
- **Tool-call boundary** — `hooks/go_delegation_enforce_PreToolUse.py` (registered via this skill's frontmatter) reads the active proposal + a `.delegation-{advisory|worker}_{run_id}` phase marker and denies disallowed mutations: advisory roles are denied all mutating tools (`Edit`/`Write`/`MultiEdit`/`NotebookEdit` and Bash shared-state subcommands); `claude_subagent`/`local_fast` workers are path-bounded to `worker_scope` when it is resolvable (`worker_enforcement="path-bound"`), else type-bounded (`"type-bound"` — mutating tools allowed in scope but shared-state Bash still denied for `local_fast`); `pi_ccr` direct main-tree edits are denied.
- **pi subprocess boundary** — `scripts/adapters/pi/harness.py` refuses to spawn if the worktree branch is `main`/`master` (`pi_ccr` mutates only in an isolated feature worktree).
- **Task-subagent spawn boundary** — the PreToolUse gate above does *not* propagate into spawned Task subagents (SKILL-frontmatter hooks are not inherited by subagent contexts unless listed in the agent's `skills:`). So when you spawn an advisory review subagent during a `.delegation-advisory` phase, pick a read-only agent type whose `tools:` omit `Bash`/`Edit`/`Write` (e.g. `tools: [Read, Grep, Glob]`). The capability layer then omits mutating tools from the subagent's function schema entirely — the call cannot be formed, which is stronger than a propagated hook would be. This is spawn-time discipline, not gate-enforced; a mutating-capable agent type spawned during advisory can mutate freely and the gate will not see it.
- Markers are flipped by `orchestrate.set_delegation_mode()`: `worker` at the `dispatched` phase, `advisory` at `transcript-reviewed`. Outside a gated phase the gate is inert (silent allow).

**Enforcement honesty** (req. 14 — `delegation_policy.enforcement_status`): distinguish *declared* policy from *verified runtime* enforcement. The proposal carries `enforcement_status` with three lists:

- **`verified`** — the five points that must all hold to claim a role's mutation authority is enforced at runtime: (1) writer (`derive_delegation_policy` emits `mutation_authority` + `worker_scope`); (2) marker/state (`.delegation-{advisory,worker}_{run_id}` written by `orchestrate.py`); (3) reader/gate (`go_delegation_enforce_PreToolUse.py` wired via this skill's frontmatter); (4) active runtime window (gate fires on Claude's tool calls during `/go`); (5) dispatch path (`harness.py` worktree-branch assertion for `pi_ccr`).
- **`advisory_or_unverified`** — paths NOT enforced at the `/go` layer: Task-tool subagent propagation of PreToolUse is **unverified** (research parked; mitigate with capability-layer `tools:` restriction, which IS hard enforcement); `agy` runs in its own subprocess worktree, outside Claude's tool-call boundary (advisory only here).
- **`role_enforcement`** — per role: `claude_main` verified (main-session PreToolUse); `claude_subagent`/`local_fast` PreToolUse propagation unverified, use `tools:` for hard enforcement; `pi_ccr` verified (harness worktree assertion); `agy` advisory.

**Do NOT claim `delegation_policy` enforces all role mutation authority** unless all five `verified` points hold for that role. **Do NOT recommend read-only advisory subagent profiles unless they exist in the current agent registry or this task creates them** — reference real agent types (e.g. `adversarial-critic`, `code-reviewer`, `explore`) rather than inventing profiles. The `declared_vs_verified_note` field restates this on every proposal.

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
DOCS_ONLY="$(python -c 'import json; d=json.load(open("'${CLAUDE_PROJECT_DIR:-P:/}'.claude/.artifacts/'${TERMINAL_ID}'/go/diff-summary_'${RUN_ID}'.json")); print("true" if d.get("docs_only") else "false")' 2>/dev/null || echo false)"
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

## STEP 6.6: Capability-Claim Audit (Consolidation/Deprecation/Routing Tasks)

For tasks involving command consolidation, deprecation, absorption, routing, or cleanup, verify capability claims against real implementation paths before allowing "shipped"/"absorbed"/"production" wording.

**Trigger:** `task.capability_audit` present in the active task (auto-detected by preflight from trigger terms: consolidation, deprecation, absorption, routing, stubs, cleanup, migration, visible surface, decommission, sunset, retire).

```bash
python ".claude/skills/go/scripts/capability_claim_audit.py" "$GO_STATE_DIR" "$RUN_ID"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  echo "CAPABILITY AUDIT FAILED: overclaim(s) detected"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
fi
touch "$GO_STATE_DIR/.capability-audit-passed_$RUN_ID"
```

**Classification schema** (per command/mode):

| Classification | Meaning |
|----------------|---------|
| `true_stub` | Command body replaced with pass-through/no-op |
| `deprecation_header_on_retained_engine` | Has deprecation warning but still runs real logic |
| `retained_engine` | Full implementation still present, not stubbed |
| `routed_to_parent` | Delegates to parent command/mode |
| `pending_backend` | Routing exists but backend runner/module missing |
| `deleted` | Command removed entirely |
| `unknown` | Cannot determine from source inspection |

**Report-gate behavior:**
- Visible-surface verification alone is insufficient when capability migration is claimed
- Reports must distinguish: visible consolidation complete | routing complete | backend implementation complete | pending capability intentionally deferred
- "shipped"/"absorbed"/"production" wording blocked when `capability_audit.audit_passed: false`

**Confirm-closed for consolidation** must include:
- Visible command surface check
- Model auto-invocation surface check (where relevant)
- Routed capability backend check
- Stale docs/language check

**Artifacts:** `capability-audit-{RUN_ID}.json` with per-claim evidence, classification, and overall audit verdict. Ingested into `verification-result.capability_audit`.

---

## STEP 6.7: Completion Evidence Review (Post-Implementation Review Gate)

After tests pass and coverage gates verify, but **before** `.pr-ready` is touched and `.pr_ready` is emitted, the orchestrator runs the read-only **Completion Evidence Review** over the worker's completion report.

This gate exists because the user catches gaps after target LLMs report "PASS": helpers with no runtime caller, synthetic-only tests, wrong-layer hook logic, missing writers/readers, stale git/cache evidence, silent failures, and overclaimed live behavior. Without this gate, /go would happily mark done on a worker report that checks structural boxes but leaves dead features and unbacked claims in the tree.

**Trigger policy** (`completion_evidence_review.task_should_trigger`):

| Condition | Runs review? |
|-----------|--------------|
| Always for hook/gate/cache/plugin/routing/model/dispatch/state/session/telemetry tasks | Yes |
| Always when worker claims PASS on live/wired/registered/failover/activation behavior | Yes |
| Optional for small low-risk local edits (use `GO_COMPLETION_REVIEW_SKIP=1`) | No |

The reviewer is **read-only by default**: it inspects source, artifacts, tests, and git/cache state via fresh current-terminal `git` invocations (no latest-file reads; no stale cross-terminal pointers). It may run safe validation commands (`git grep`, `git diff`, `git log`). It does NOT modify files unless explicitly authorized by a separate task.

**Verdict schema** (`completion-evidence-review_{RUN_ID}.json`):

| Verdict | Meaning | commit_push_safe |
|---------|---------|-------------------|
| `PASS` | Clean evidence packet, no gaps, no overclaim | True |
| `PASS WITH FOLLOW-UP` | Non-blocking gaps; safe to mark done, log follow-ups | True |
| `REVISE` | Blocking gap (revise before next review) | False |
| `BLOCK` | Overclaim, wrong layer, or hard failure | False |
| `INCOMPLETE` | Missing required inputs (worker report missing/corrupt) | False |

**Reviewer output fields** (per `completion-evidence-review.v1`):

- `evidence[]` — table of `claim / required_evidence / observed_evidence / verdict (OK|WEAK|MISSING|OVERCLAIM) / note`
- `blocking_gaps[]` — list of strings naming each gap the worker must address
- `overclaims[]` — list of unbacked live-behavior terms
- `recommended_next_action` — plain-English next step
- `commit_push_safe` — boolean
- `generated_at` — ISO timestamp

**Detectors:**

| Failure class | Detector | Verdict on hit |
|---------------|----------|----------------|
| Helper exists, no runtime caller | `git grep -w -F` across the worktree | REVISE |
| Worker claimed live/wired/registered behavior without smoke/cache-rebuild/registration artifact | Evidence artifact scan + claim term scan | REVISE / BLOCK |
| Stop hook or `router.py` was edited with broad-analysis verbs (pattern detection, dry-run, refactor analysis) | Per-file diff for `_BROAD_ANALYSIS_VERBS` | BLOCK |
| New tracking path (telemetry, metrics, stop_block, anomaly, completion-authority, completion_evidence, review_passes) is read but no `write_text`/`write_json`/`json.dump`/`.touch()` writer emits it | `git grep -E` for writers | REVISE |
| Synthetic-only failover/fallback claim (`@patch`, `MagicMock`, `Mock(` without `subprocess.run`/`run_script`) | Diff density scan | BLOCK |
| Layer-placement violation (broad-verb in prompt + Stop/router edits) | Prompt + file-edit cross-check | BLOCK |
| Plugin/hook file changes without cache-rebuild artifact | File pattern + artifact scan | REVISE |
| Multi-terminal pollution risk (top-level `state.json`, `latest` paths) | File-path pattern scan | WEAK (PASS WITH FOLLOW-UP) |
| Report overclaim: unbacked live-behavior terms | Per-term OK-row check | BLOCK |

**Multi-terminal requirements (codified):**

- All git/cache/log/artifact claims use fresh current-terminal evidence (`git diff`/`git grep` invoked at review time, not latest-file reads)
- `run_id`-scoped artifact paths preferred
- Stale / missing / corrupt data fails toward no claim, never toward PASS

**Artifact:** `completion-evidence-review_{RUN_ID}.json` (verdict + evidence table) and `completion-evidence-review_{RUN_ID}.jsonl` (append-only ledger). Touches `.completion-reviewed_{RUN_ID}` on success.

**Scope:** the reviewer does NOT add logic to `Stop_enforce_gate.py` (per requirements). It runs in the orchestrator's process between coverage-gate and pr-artifacts. Reviewer logic does not propagate to the Stop hook; the existing `completion-authority` overclaim gate (in `Stop_enforce_gate.py`) is the Stop-side check and remains unchanged.

**Tests:** `skills/go/tests/test_completion_evidence_review.py` — 7 cases covering helper-no-caller, source-only-live, wrong-layer-Stop-hook, missing-writer-for-reader, synthetic-only-failover, clean-packet-pass, follow-up-only.

---

## STEP 6.8: Completion Verifier — High-Risk Semantic Review (advisory-first)

Immediately after the Completion Evidence Review (STEP 6.7) and the Omission
Audit (STEP 9.6 of `run_common_tail`), for **high-risk tasks only**
(`task_should_trigger` markers: hook/cache/plugin/router/model/dispatch/state/
session/telemetry/identity), the orchestrator writes a read-only verifier
request and pauses for an in-session semantic review. Low-risk tasks skip this
gate entirely. Opt out with `GO_COMPLETION_VERIFY_SKIP=1`.

**Why it exists:** mechanical gates catch overclaim and wrong-layer, but cannot
detect a *dropped acceptance criterion* — "task asked for X/Y/Z, worker did X/Y
and silently omitted Z." That requires reading the diff against intent, which is
LLM-shaped. The verifier is **advisory-first**: it does NOT hard-block
`.pr-ready` on ordinary semantic disagreement until corpus calibration proves
acceptable TP/FP (gate-discrimination rule).

### Two-phase spawn (mirrors `SPAWN_CLAUDE_SUBAGENT`)

The orchestrator is a Bash-invoked Python script and cannot call the
in-session `Agent(...)` tool itself, so the verifier is split around the spawn.

**Phase 1 — request write (orchestrator, `_completion_verify_gate`):**
- Reads `active-task` + the CER verdict, writes
  `completion-verify-request_{RUN_ID}.json` (schema `completion-verify-request.v1`):
  `{run_id, title, objective, acceptance_criteria, scope_in/out, constraints,
  worker_summary, mechanical_review_verdict, mechanical_review_evidence,
  calibration_mode: "advisory", agent_contract}`.
- Sets `.completion-verify-pending_{RUN_ID}` and emits
  `<promise>SPAWN_COMPLETION_VERIFIER</promise>`.

**Phase 2 — spawn + resume (main-loop Claude):** when the orchestrator emits
`SPAWN_COMPLETION_VERIFIER`, the main-loop Claude:

1. Reads `$GO_STATE_DIR/completion-verify-request_$RUN_ID.json`.
2. Spawns a **read-only** verifier `Agent(...)` with `tools: [Read, Grep, Glob,
   Bash]` (no `Edit`/`Write`/`MultiEdit` — the capability layer then cannot
   form a mutating call; memory #1120). The agent compares each
   `acceptance_criteria` item against the actual diff and worker report, and
   returns JSON.
3. Writes the result to `$GO_STATE_DIR/completion-verify-result_$RUN_ID.json`
   (schema `completion-verifier.v1`):
   ```json
   {"schema": "completion-verifier.v1", "run_id": "...",
    "verdict": "PROCEED | ADVISORY_REVISE | BLOCK",
    "addressed": [], "omitted": [], "uncertain": [], "evidence": [],
    "recommended_next_action": "...", "calibration_mode": "advisory"}
   ```
4. Re-invokes the orchestrator:
   ```bash
   GO_RUN_ID="$RUN_ID" python ".claude/skills/go/scripts/orchestrate.py" --completion-verify-resume "$RUN_ID"
   ```
   This runs **only** pr-artifacts + tail (steps 1–9.6 already ran; resume does
   not re-verify or re-dispatch).

### Advisory semantics (resume)

`_apply_completion_verify_result` reads the result and records the outcome to
the run-scoped `completion-verify-ledger.jsonl` (not a persistent pattern DB):

| Verdict | `.pr-ready`? | Notes |
|---|---|---|
| `PROCEED` | proceeds | clean |
| `ADVISORY_REVISE` | **proceeds** (advisory) | omissions surfaced to `.completion-verify-advisory_{RUN_ID}` + ledger; **not** a hard block |
| `BLOCK` | proceeds unless `infrastructure_failure: true` | in calibration mode, an LLM `BLOCK` is treated as advisory — only the verifier's own infrastructure failure hard-blocks |
| missing/malformed result | **hard-blocks** (`.blocked_{RUN_ID}`) | fail-closed: the review machinery itself failed, not the work |

**Calibration gate:** do **not** promote `ADVISORY_REVISE` to a hard `.pr-ready`
block until a later task measures real-corpus TP/FP on `completion-verify-ledger.jsonl`.

**Tests:** `skills/go/tests/test_completion_verify.py` — 8 cases covering
high-risk-writes-request-and-pauses, low-risk-skips, SKIP-env,
resume-PROCEED-runs-tail, resume-ADVISORY-REVISE-does-not-block,
resume-missing-result-fails-closed, resume-malformed-records-ledger, and
request-payload-carries-CER-verdict.

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

## Thought Partner Addendum

In a `/go` **final implementation report** (not a trivial task), emit a
Thought Partner Addendum (TPA) when the run surfaced something material the
task framing did not ask about — a broader root cause, a hidden risk, an
activation gap (plugin bumped but not enabled), cost-waste, or a deferred
prerequisite. Each item carries `observation`, `why_it_matters`, `evidence`,
`recommended_action`, `urgency: now | later | watch`. Omit the section for
trivial tasks or when nothing material was found; never displace the report's
primary result or evidence block. Canonical contract + worked examples at
`debrief/references/thought-partner-addendum.md` (canonical owner: `/improve`).
The TPA is prompt-advisory only.

## Report-Contract Vocabularies

`/go` emits claims under the cross-command report contracts. The canonical
field definitions live at
`debrief/references/report-contract-vocabularies.md`:

- **Coverage Authority** — name `sampled | targeted | whole_repo_static |
  runtime_surface | live_behavior` on any audit claim (no bare "full coverage").
- **Activation Truth Model** — name one of `source_changed | cache_rebuilt |
  plugin_loaded | command_resolves | behavior_observed` on any "live / wired"
  claim. Do not claim live behavior from a source/cache evidence alone.
- **Bounded Action Continuation** — when the goal is authorized and the next
  action is bounded + reversible + directly implied, complete it directly
  instead of ending with "say the word."
- **Manifest generator** — before claiming `whole_repo_static` evidence breadth,
  run `cc-skills-architect/skills/ask/lib/abstraction_audit_manifest.py` and
  cite the produced `manifest.json`.

Advisory status: prompt-advisory. Static-invariant-tested at most. No runtime
hook enforces these fields.

## Partner Posture

`/go`'s posture is **Execution Partner** (see the Partner Posture Map in
`debrief/references/thought-partner-addendum.md`). `/go` completes bounded
implementation work, avoids avoidable blockers, uses deterministic-first
workflow before LLM or subagent dispatch, and reports activation, tests,
drift, and evidence honestly. It surfaces broader root causes only when they
affect execution, sequencing, cost, risk, or future work. Posture is
prompt-advisory.
