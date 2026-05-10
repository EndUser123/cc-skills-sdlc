---
name: go-pi
version: 1.0.0
description: Variant of /go that dispatches workers via the pi multi-provider agent harness instead of Claude Code subagents. Uses Bifrost model classification to select the target model, then invokes pi --model for task execution.
category: execution
enforcement: strict
workflow_steps:
  - worktree_enforcement
  - task_selection
  - classify_complexity
  - resolve_model
  - pi_dispatch
  - transcript_review
  - verify_end_to_end
  - simplify_code
  - seven_pass_review
  - local_pr_artifacts
  - loop_check
suggest:
  - /go
  - /bf
  - /ai-pcli
  - /code
hooks:
  Stop:
    - hooks:
        - type: command
          command: |
            python -c "import os,sys,glob; tid=os.environ.get('CLAUDE_TERMINAL_ID','unknown'); sd=f'.claude/.artifacts/{tid}/go-pi'; sys.exit(0) if not glob.glob(f'{sd}/active-task_*.json') else None; rid=os.environ.get('GO_RUN_ID','unknown'); sys.exit(0) if os.path.isfile(f'{sd}/.verified_{rid}') and os.path.isfile(f'{sd}/.reviews-passed_{rid}') else (print('WARNING: /go-pi completed without all gates passed',file=sys.stderr), sys.exit(1))"
          description: "Self-verify all gates passed on Stop"
---

# /go-pi — Pi-Dispatched SDLC Orchestrator

**Role:** `/go-pi` is a variant of `/go` that dispatches coding work to external LLMs via the **pi** agent harness instead of Claude Code subagents. It stays on `main`, classifies task complexity, selects the appropriate model, and dispatches via `pi --model <resolved>`.

**Unified Schema:** All tasks and plans MUST adhere to the schemas defined in `../go/schemas/` (shared with `/go`).

**MANDATORY SEQUENCE:** Worktree Check → Task Selection → Classify → Resolve Model → Pi Dispatch → Transcript Review → Verify → Simplify → 7-Pass Review → PR Artifacts → Loop Check

**State root:** `.claude/.artifacts/{TERMINAL_ID}/go-pi/`

---

## What /go-pi Must Do

1. Enforce worktree + branch preconditions (auto-create if on main)
2. Acquire a task from one of three input sources
3. Classify task complexity → select model via Bifrost (same classifier as /go)
4. Resolve classifier model name to pi CLI flag
5. Dispatch the worker via `pi --model <resolved>` into a worktree
6. Run verification commands from the task contract
7. Run `/simplify` if code changed
8. Run 7-pass review at the appropriate depth
9. Generate local PR artifacts
10. Emit the correct completion token

**What /go-pi Must NOT Do:**
- Use Claude Code's `Agent` tool for task execution (that's `/go`)
- Replace `/code` TDD workflow
- Replace `/refactor` cleanup logic
- Replace `/planning` task breakdown
- Auto-push or create remote PRs

---

## How /go-pi Differs from /go

| Aspect | /go | /go-pi |
|--------|-----|--------|
| Worker dispatch | `Agent` tool (Claude Code subagent) | `pi --model <resolved>` CLI |
| Model selection | Classifier output unused (Claude executes) | Classifier output consumed → pi flag |
| Worker identity | Claude subagent (same session) | External LLM via pi (subprocess) |
| File context | Subagent has repo access | pi `-p @file` for file context |
| Steps 3-7, PR artifacts | Same | Same |

---

## Model Resolution Map

The classifier outputs model aliases (`M27`, `GLM-5.1`). These map to pi CLI flags:

| Classifier Output | pi --model flag | Provider |
|---|---|---|
| `M27` | `minimax/MiniMax-M2.7` | MiniMax |
| `GLM-5.1` | `zai/glm-5.1` | Z.ai |

Override: `GO_MODEL_OVERRIDE` env var bypasses classification (same as /go). The resolver passes the raw value through as the pi model flag.

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
export GO_STATE_DIR=".claude/.artifacts/${TERMINAL_ID}/go-pi"
export GO_TASKS_FILE="${GO_TASKS_FILE:-.claude/tasks/tasks.json}"
export GO_PROMPT="${GO_PROMPT:-}"
export HANDOFF_TRANSCRIPT="${HANDOFF_TRANSCRIPT:-}"
export GO_PLAN_FILE="${GO_PLAN_FILE:-}"
export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY:-$(python -c "import json; d=json.load(open('$USERPROFILE/.pi/agent/auth.json')); print(d.get('nvidia',{}).get('key',''))")}"
mkdir -p "$GO_STATE_DIR"
```

---

## Task Input Sources

Same as `/go`. Priority: `GO_PROMPT` > `HANDOFF_TRANSCRIPT` > `GO_PLAN_FILE` > `GO_TASKS_FILE`

---

## STEP 0: Worktree Provisioning

`/go-pi` stays on `main`, creates a worktree for the worker under `P:/worktrees/`.

```bash
TS=$(date +%Y%m%d-%H%M%S)
WORKTREE="P:/worktrees/pi-task-$TS"
mkdir -p "P:/worktrees"
git worktree add -b "pi/pi-task-$TS" "$WORKTREE" HEAD
```

---

## STEP 1: Task Acquisition

Same as `/go`. Uses the shared `select-task.py` script.

```bash
python ".claude/skills/go/scripts/select-task.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.task-selected_$RUN_ID"
```

---

## STEP 1.5: Classify Complexity

Uses the shared classifier from `/go`.

```bash
python ".claude/skills/go/scripts/classify_complexity.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
```

Output: `model-selection_{RUN_ID}.json` with `{tier, model, confidence, signals}`.

---

## STEP 1.6: Resolve Model (NEW)

Resolve the classifier's model alias to a pi CLI flag.

```bash
python ".claude/skills/go_pi/scripts/resolve_model.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.model-resolved_$RUN_ID"
```

Output: `pi-model_{RUN_ID}.json` with `{classifier_model, tier, pi_model}`.

---

## STEP 2: Pi Dispatch (CHANGED from /go)

Read `pi-model_{RUN_ID}.json` and dispatch the worker via `pi`.

**Build the task prompt from the active task contract:**

```bash
PI_MODEL=$(python -c "import json; d=json.load(open('$GO_STATE_DIR/pi-model_${RUN_ID}.json')); print(d['pi_model'])")
TASK_FILE="$GO_STATE_DIR/active-task_${RUN_ID}.json"
TASK_PROMPT=$(python -c "
import json, sys
d = json.load(open('$TASK_FILE'))
t = d.get('task', d)
parts = [f\"Task: {t.get('title', '')}\", f\"Objective: {t.get('objective', '')}\"]
for c in t.get('acceptance_criteria', []):
    parts.append(f'- Accept: {c}')
for v in t.get('verification_commands', []):
    parts.append(f'- Verify: {v}')
for f in t.get('scope_in', []):
    parts.append(f'- Scope: {f}')
for f in t.get('forbidden_files', []):
    parts.append(f'- DO NOT modify: {f}')
print('\\n'.join(parts))
")
```

**Dispatch worker into the worktree:**

`pi` runs in the current working directory. Run it from inside the worktree:

```bash
mkdir -p "$GO_STATE_DIR/pi-sessions"
(cd "$WORKTREE" && pi --model "$PI_MODEL" --print \
  --session-dir "$GO_STATE_DIR/pi-sessions" \
  --no-context-files \
  --system-prompt "You are a coding agent. Complete the task. Use read/edit/write/bash tools. Run verification commands after writing code." \
  -p "@$TASK_FILE" \
  "$TASK_PROMPT")
```

Key flags:
- `--print` (`-p`): non-interactive mode — runs tool loop (read/edit/write/bash) then exits
- `--session-dir`: save session transcript to state dir for post-dispatch review
- `--no-context-files`: skip CLAUDE.md/AGENTS.md loading in worktree
- `--model <provider/model>`: target model from resolver (e.g. `minimax/MiniMax-M2.7`)
- `-p "@file"`: embed file contents as context
- `--system-prompt`: override default system prompt for task context

**Collect results:**

```bash
PI_EXIT=$?
if [ "$PI_EXIT" -ne 0 ]; then
  ATTEMPT_NEXT=$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
  [ "$ATTEMPT_NEXT" -ge "$MAX_ATTEMPTS" ] && touch "$GO_STATE_DIR/.blocked_$RUN_ID" && echo "<promise>BLOCKED</promise>" && exit 1
  exit 1
fi
touch "$GO_STATE_DIR/.dispatched_$RUN_ID"
```

---

## STEP 2.5: Transcript Review (NEW)

Review the pi session transcript for anti-patterns before proceeding to verification.

**Phase A — Mechanical summary (Python):**

```bash
python ".claude/skills/go_pi/scripts/review_transcript.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && echo "ERROR: transcript summarizer failed" && exit 1
```

Output: `pi-review_{RUN_ID}.json` with `{warnings, tool_summary, files_read, files_written, total_tool_calls, transcript_tail, transcript_path, total_lines}`.

The summarizer always exits 0 — it extracts structure, not gate decisions.

**Phase B — Subagent review (Agent tool):**

Dispatch a review subagent that reads the summary + transcript tail and reasons about quality. This is NOT task execution (prohibited for Agent) — it is quality review.

```
Agent(subagent_type="general-purpose", prompt="""
You are reviewing a pi agent harness transcript for quality. The mechanical summarizer has already extracted the structure.

Read the summary file: {GO_STATE_DIR}/pi-review_{RUN_ID}.json
Read the full transcript (if needed for context): use transcript_path from the summary.
Read the task contract: {GO_STATE_DIR}/active-task_{RUN_ID}.json

Evaluate these criteria and respond with a JSON verdict:

1. **Task completion**: Did the pi agent actually complete the task objective? Check if acceptance criteria are met.
2. **Anti-patterns**: Review the warnings from the summary. Are any critical?
   - BLIND_WRITE, FORBIDDEN_FILE, NO_FILES_WRITTEN are critical.
   - EXCESSIVE_CALLS, TOOL_ERRORS, SCOPE_UNTOUCHED are warnings — judge severity.
3. **Tool usage quality**: Did the agent read before writing? Did it retry on errors?
4. **Correctness signals**: Does the transcript tail show the agent claiming success? Does the evidence support that?

Respond with ONLY this JSON (no markdown):
{"verdict": "PASS" | "FAIL", "reason": "one sentence", "critical_issues": ["list of critical issues or empty"]}

If verdict is FAIL, list every critical issue. The orchestrator will block on FAIL.
""")
```

If the subagent returns `"verdict": "FAIL"`, treat as a failed attempt:

```bash
if [ "$VERDICT" = "FAIL" ]; then
  ATTEMPT_NEXT=$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_$RUN_ID" | wc -l | tr -d ' ')
  [ "$ATTEMPT_NEXT" -ge "$MAX_ATTEMPTS" ] && touch "$GO_STATE_DIR/.blocked_$RUN_ID" && echo "<promise>BLOCKED</promise>" && exit 1
  exit 1
fi
touch "$GO_STATE_DIR/.transcript-reviewed_$RUN_ID"
```

**Why subagent for review:** Transcripts can be messy, large, and contain nuances that fixed pattern matching misses. The mechanical summarizer handles the easy extraction; the subagent handles the reasoning about whether the work was actually done correctly.

---

## STEP 3: Verification

Same as `/go`. Run every command in `task.verification_commands`.

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

Same as `/go`. If docs-only diff, skip. Otherwise run `/simplify`.

---

## STEP 5: 7-Pass Review

Same as `/go`.

```bash
python ".claude/skills/go/scripts/review-passes.py"
STATUS=$?
[ "$STATUS" -ne 0 ] && exit 1
touch "$GO_STATE_DIR/.reviews-passed_$RUN_ID"
```

---

## STEP 6: Local PR Artifacts

Same as `/go`.

```bash
python ".claude/skills/go/scripts/pr-artifacts.py"
touch "$GO_STATE_DIR/.pr-ready_$RUN_ID"
echo "<promise>PR_READY</promise>"
```

---

## STEP 7: Loop Check

Same as `/go`.

```bash
python ".claude/skills/go/scripts/loop-check.py"
```

---

## Prohibited Actions

- Workers making direct changes on `main` or `master`
- Using `Agent` tool for task execution (use `pi` CLI)
- Proceeding without model resolution
- Ignoring failed verification commands
- Ignoring HIGH/CRITICAL simplify findings
- Auto-pushing or creating remote PRs
- Modifying `forbidden_files` listed in task contract
