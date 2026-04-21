---
name: go_2.0
version: 2.0.0
description: Local-only PR-ready execution loop with terminal-scoped artifact state, structured task contract, mandatory verification, simplify gate, review passes, and local PR artifacts.
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
  - task_contract
  - verify_end_to_end
  - simplify_code
  - seven_pass_review
  - local_pr_artifacts
  - loop_check
suggest: []
---

# /go_2.0 — Verify, Simplify, Ship

**MANDATORY SEQUENCE:** Worktree Check → Task Selection → Contract → `/t`+`/gap` → TDD → Verify → Simplify → 7-Pass Review → PR Artifacts → Loop Check

**Canonical state root:** `.claude/.artifacts/{TERMINAL_ID}/go/`

**Canonical design rules:**
- `/go` executes **exactly one selected task** per run.
- `/go` uses **artifact files as the canonical state**, not transcript memory.
- `/go` reads **structured task JSON**, not `plan.md`, as the scheduling source of truth.
- `/go` writes machine-readable outputs for every major step.
- `/go` creates **local-only** PR artifacts; no push, no remote PR creation.
- `/go` must be safe for multi-terminal use.

---

## Completion promises

- `<promise>PR_READY</promise>` — task completed, all gates passed, PR artifacts produced.
- `<promise>BLOCKED</promise>` — task cannot proceed or max attempts reached.
- `<promise>MORE_TASKS_IN_PLAN</promise>` — current task done, remaining queued tasks exist.
- `<promise>ALL_TASKS_COMPLETE</promise>` — no remaining actionable tasks.

---

## Canonical artifact layout

```text
.claude/.artifacts/{TERMINAL_ID}/go/
  active-task_{RUN_ID}.json
  task-result_{RUN_ID}.json
  diff-summary_{RUN_ID}.json
  test-discovery_{RUN_ID}.md
  test-gaps_{RUN_ID}.json
  tdd-receipt_{RUN_ID}.json
  verification-results_{RUN_ID}.txt
  verification-summary_{RUN_ID}.json
  simplify-status_{RUN_ID}.md
  simplify-summary_{RUN_ID}.json
  review-pass-correctness_{RUN_ID}.md
  review-pass-scope_{RUN_ID}.md
  review-pass-tests_{RUN_ID}.md
  review-pass-simplicity_{RUN_ID}.md
  review-pass-regressions_{RUN_ID}.md
  review-pass-maintainability_{RUN_ID}.md
  review-pass-pr-ready_{RUN_ID}.md
  review-summary_{RUN_ID}.json
  commit-message_{RUN_ID}.txt
  pr-title_{RUN_ID}.txt
  pr-body_{RUN_ID}.md
  pr-ready_{RUN_ID}.md
  .worktree-ready_{RUN_ID}
  .task-selected_{RUN_ID}
  .task-defined_{RUN_ID}
  .verified_{RUN_ID}
  .simplified_{RUN_ID}
  .reviews-passed_{RUN_ID}
  .pr-ready_{RUN_ID}
  .blocked_{RUN_ID}
  .attempt_1_{RUN_ID}
  .attempt_2_{RUN_ID}
  .attempt_3_{RUN_ID}
```

---

## Required environment

Before invoking `/go`, these variables must exist:

```bash
export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${RUN_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export GO_STATE_DIR=".claude/.artifacts/${TERMINAL_ID}/go"
mkdir -p "$GO_STATE_DIR"
```

Optional variables:

```bash
export GO_TASKS_FILE="${GO_TASKS_FILE:-.claude/tasks/tasks.json}"
export GO_RALPH_MODE="${GO_RALPH_MODE:-auto}"
```

---

## Task source-of-truth contract

`$GO_TASKS_FILE` must be valid JSON shaped like:

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
      "acceptance_criteria": [
        "Criterion 1",
        "Criterion 2"
      ],
      "verification_commands": [
        "pytest -q",
        "npm test -- --runInBand"
      ],
      "notes": "Optional operator notes"
    }
  ]
}
```

**Allowed `status` values for selection:** `ready`, `queued`, `approved`

**Selection rule:** `/go` must select the **first actionable task** in priority order already present in the tasks file. `/go` must not invent or reorder tasks during execution.

---

## STEP 0: WORKTREE ENFORCEMENT

**Creates flag:** `.worktree-ready_{RUN_ID}`

### Gate
Fail immediately if:
- not inside a git repository,
- current branch is `main` or `master`,
- current path is not an active git worktree.

### Commands

```bash
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "ERROR: not in git repo"; touch "$GO_STATE_DIR/.blocked_$RUN_ID"; echo "<promise>BLOCKED</promise>"; exit 1; }

CURRENT_BRANCH="$(git branch --show-current)"
[ -n "$CURRENT_BRANCH" ] || { echo "ERROR: detached HEAD"; touch "$GO_STATE_DIR/.blocked_$RUN_ID"; echo "<promise>BLOCKED</promise>"; exit 1; }

case "$CURRENT_BRANCH" in
  main|master)
    echo "ERROR: /go cannot run on $CURRENT_BRANCH"
    touch "$GO_STATE_DIR/.blocked_$RUN_ID"
    echo "<promise>BLOCKED</promise>"
    exit 1
    ;;
esac

git worktree list --porcelain | grep -F "worktree $(pwd)" >/dev/null 2>&1 || {
  echo "ERROR: current directory is not a registered git worktree"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
}

touch "$GO_STATE_DIR/.worktree-ready_$RUN_ID"
echo "✓ Worktree check passed"
```

---

## STEP 1: TASK SELECTION

**Requires flag:** `.worktree-ready_{RUN_ID}`
**Creates file:** `active-task_{RUN_ID}.json`
**Creates flag:** `.task-selected_{RUN_ID}`

### Gate
- `$GO_TASKS_FILE` must exist.
- It must contain at least one actionable task.
- `/go` selects exactly one task for this run.

### Selection behavior

Select the first task whose `status` is one of:
- `ready`
- `queued`
- `approved`

Prefer lower priority number if your scheduler pre-sorts priorities externally. If not, select first listed actionable task.

### Required output file

Write `active-task_{RUN_ID}.json` with exactly one selected task plus execution metadata:

```json
{
  "run_id": "RUN_ID",
  "terminal_id": "TERMINAL_ID",
  "selected_at": "ISO-8601",
  "task": {
    "id": "TASK-001",
    "title": "Short title",
    "objective": "One-sentence objective",
    "status": "ready",
    "priority": "P1",
    "scope_in": [],
    "scope_out": [],
    "forbidden_files": [],
    "acceptance_criteria": [],
    "verification_commands": []
  }
}
```

### Example shell snippet

```bash
if [ ! -f "$GO_TASKS_FILE" ]; then
  echo "ERROR: tasks file not found at $GO_TASKS_FILE"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
fi

python - <<'PY'
import json, os, sys, datetime, pathlib

tasks_file = pathlib.Path(os.environ["GO_TASKS_FILE"])
state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
allowed = {"ready", "queued", "approved"}

selected = None
for task in tasks:
    if task.get("status") in allowed:
        selected = task
        break

if not selected:
    print("ERROR: no actionable task found", file=sys.stderr)
    sys.exit(2)

payload = {
    "run_id": run_id,
    "terminal_id": terminal_id,
    "selected_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "task": selected,
}
out = state_dir / f"active-task_{run_id}.json"
tmp = out.with_suffix(".json.tmp")
tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp.replace(out)
PY

STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  echo "ERROR: failed to select task"
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
fi

touch "$GO_STATE_DIR/.task-selected_$RUN_ID"
echo "✓ Task selected"

# Initialize run-status
python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

active = json.loads((state_dir / f"active-task_{run_id}.json").read_text(encoding="utf-8"))
task_id = active.get("task", {}).get("id", "UNKNOWN")

data = {
    "schema_version": "go.run-status.v1",
    "go_run_id": run_id,
    "terminal_id": terminal_id,
    "skill_version": "2.0.0",
    "status": "task-selected",
    "current_step": "task_selection",
    "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "updated_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "selected_task_id": task_id,
    "retry_count": 0,
    "max_retries": int(os.environ.get("MAX_ATTEMPTS", "3")),
    "recommendations": [],
    "dispatch_results": [],
    "final_promise": None,
    "blocking_reason": None,
    "verification_result_path": None,
    "block_state_path": None,
    "artifact_dir": str(state_dir)
}
path = state_dir / f"run-status_{run_id}.json"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
```

---

## STEP 2: TASK CONTRACT + DIFF ANALYSIS

**Requires flag:** `.task-selected_{RUN_ID}`
**Creates flag:** `.task-defined_{RUN_ID}`
**Uses file:** `active-task_{RUN_ID}.json`

### Contract rule

`active-task_{RUN_ID}.json` is the canonical task contract for the run. Do not create a separate prose-only contract as the primary source of truth.

### Diff classification

Classify staged or working-tree diff for review depth and code change type:

```bash
CHANGED_FILES="$(git diff --name-only HEAD)"
FILE_COUNT="$(printf '%s\n' "$CHANGED_FILES" | sed '/^$/d' | wc -l | tr -d ' ')"
LINE_COUNT="$(git diff --shortstat HEAD | sed -E 's/.* ([0-9]+) insertions?\(\+\).*/\1/' | tr -d '\n')"
LINE_COUNT="${LINE_COUNT:-0}"

CODE_FILE_COUNT="$(printf '%s\n' "$CHANGED_FILES" | grep -E '\.(py|ts|tsx|js|jsx|sh|go|rs|java|c|cc|cpp|h|hpp)$' | wc -l | tr -d ' ')"
DOCS_ONLY="false"
[ "${CODE_FILE_COUNT:-0}" -eq 0 ] && DOCS_ONLY="true"

REVIEW_DEPTH="full"
if [ "${FILE_COUNT:-0}" -le 2 ] && [ "${LINE_COUNT:-0}" -lt 50 ]; then
  REVIEW_DEPTH="quick"
elif [ "${FILE_COUNT:-0}" -le 10 ] && [ "${LINE_COUNT:-0}" -lt 300 ]; then
  REVIEW_DEPTH="standard"
fi
```

Persist diff metadata to `diff-summary_{RUN_ID}.json`:

```bash
python - <<'PY'
import json, os, subprocess, pathlib

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True).stdout.strip()
shortstat = subprocess.run(["git", "diff", "--shortstat", "HEAD"], capture_output=True, text=True).stdout.strip()

code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".sh", ".go", ".rs", ".java", ".c", ".cc", ".cpp", ".h", ".hpp"}
files = [f for f in changed.splitlines() if f.strip()]
code_files = [f for f in files if any(f.endswith(e) for e in code_exts)]
docs_only = len(code_files) == 0

meta = {
    "run_id": run_id,
    "changed_files": files,
    "code_files": code_files,
    "docs_only": docs_only,
    "review_depth": os.environ.get("REVIEW_DEPTH", "full"),
    "shortstat": shortstat
}
(state_dir / f"diff-summary_{run_id}.json").write_text(json.dumps(meta, indent=2) + "\n")
PY
```

### Diff → Auto-invoke decision table

| Diff type | Action |
|-----------|--------|
| No changes | Skip TDD/simplify; direct to reviews |
| Tests only | Auto `/t` (RED/GREEN only) |
| Implementation | Auto `/t` + `/gap` → `/tdd` full cycle → simplify → reviews |
| Config/Infra | Auto verification; recommend architecture spike |

### STEP 1B: TEST DISCOVERY + GAP DETECTION

**Auto-invokes:** `/t` and `/gap` unconditionally before any coding

After diff classification, invoke test discovery to populate `test-gaps_{RUN_ID}.json`:

```bash
echo "Running test discovery..."
/t --task-file "$GO_STATE_DIR/active-task_$RUN_ID.json" --output "$GO_STATE_DIR/test-discovery_$RUN_ID.md" 2>&1 || true

# Load gaps if /t produced gap evidence
if [ -f "$GO_STATE_DIR/test-discovery_$RUN_ID.md" ]; then
  /gap --task-file "$GO_STATE_DIR/active-task_$RUN_ID.json" --source "$GO_STATE_DIR/test-discovery_$RUN_ID.md" --output "$GO_STATE_DIR/test-gaps_$RUN_ID.json" 2>&1 || true
fi

echo "✓ Test discovery complete"
```

**Artifact produced:** `test-gaps_{RUN_ID}.json` (consumed by `/tdd` if invoked)

### Pre-mortem recommendation

If test gaps were found, recommend pre-mortem before proceeding:

```bash
python - <<'PY'
import json, os, pathlib, datetime, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]
gaps_file = state_dir / f"test-gaps_{run_id}.json"

status_path = state_dir / f"run-status_{run_id}.json"
data = {}
if status_path.exists():
    data = json.loads(status_path.read_text(encoding="utf-8"))

if gaps_file.exists() and gaps_file.stat().st_size > 0:
    rec = {
        "type": "pre-mortem",
        "evidence": "test gaps found",
        "prompt": "Test gaps found. Run pre-mortem? [yes/skip]",
        "resolved": False,
        "resolved_at": None
    }
    data.setdefault("recommendations", []).append(rec)
    status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("")
    print("=== /go RECOMMENDATION ===")
    print("[pre-mortem] Test gaps found — consider running pre-mortem?")
    print("Proceed? [yes/skip]")
    print("=========================")
    choice = input().strip().lower()
    rec["resolved"] = True
    rec["resolved_at"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    if choice in ("skip", "no", ""):
        rec["prompt"] = rec["prompt"] + " [SKIPPED]"
    else:
        rec["prompt"] = rec["prompt"] + " [ACCEPTED]"
    data["recommendations"] = [r for r in data.get("recommendations", []) if r.get("type") != "pre-mortem"]
    data["recommendations"].append(rec)
    status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
```

### STEP 1C: TDD DECISION

**Conditional auto-invoke:** Run `/tdd` if `CODE_FILE_COUNT > 0` and `DOCS_ONLY = false`

```bash
if [ "$DOCS_ONLY" = "false" ] && [ "${CODE_FILE_COUNT:-0}" -gt 0 ]; then
  echo "Code changes detected — invoking /tdd..."
  /tdd --task-file "$GO_STATE_DIR/active-task_$RUN_ID.json" \
       --gaps-file "$GO_STATE_DIR/test-gaps_$RUN_ID.json" \
       --output "$GO_STATE_DIR/tdd-receipt_$RUN_ID.json" \
       2>&1 || {
    echo "ERROR: TDD cycle failed"
    exit 1
  }
  echo "✓ TDD cycle complete"

  # Consume TDD receipt — block if RED phase never passed
  python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

receipt_path = state_dir / f"tdd-receipt_{run_id}.json"
if not receipt_path.exists():
    # TDD did not produce a receipt — block
    block = {
        "schema_version": "go.block-state.v1",
        "run_id": run_id,
        "terminal_id": terminal_id,
        "status": "blocked",
        "reason_code": "tdd_validation_failed",
        "reason_summary": "TDD did not produce a validation receipt",
        "origin_step": "task_contract",
        "can_retry": False,
        "requires_user_input": True,
        "waiver_allowed": True,
        "opened_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "evidence_paths": [str(receipt_path)]
    }
    path = state_dir / f"block-state_{run_id}.json"
    path.write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
    print("ERROR: TDD receipt missing — blocked")
    raise SystemExit(1)

receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
validated = receipt.get("validated", False)
phase = receipt.get("phase_state", "none")

if not validated:
    block = {
        "schema_version": "go.block-state.v1",
        "run_id": run_id,
        "terminal_id": terminal_id,
        "status": "blocked",
        "reason_code": "tdd_validation_failed",
        "reason_summary": f"TDD phase={phase} but validated={validated}",
        "origin_step": "task_contract",
        "can_retry": True,
        "requires_user_input": False,
        "waiver_allowed": True,
        "opened_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "evidence_paths": [str(receipt_path)]
    }
    path = state_dir / f"block-state_{run_id}.json"
    path.write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
    print("ERROR: TDD not validated — blocked")
    raise SystemExit(1)

print(f"TDD validated: phase={phase}")
PY
else
  echo "Skipping TDD (docs-only or no code changes)"
fi
```

On success:

```bash
touch "$GO_STATE_DIR/.task-defined_$RUN_ID"
echo "✓ Task contract ready"
```

---

## STEP 3: VERIFICATION

**Requires flag:** `.task-defined_{RUN_ID}`
**Creates file:** `verification-results_{RUN_ID}.txt`
**Creates file:** `verification-summary_{RUN_ID}.json`
**Creates flag:** `.verified_{RUN_ID}` on success
**Creates flag:** `.attempt_{N}_{RUN_ID}` on failure
**Creates flag:** `.blocked_{RUN_ID}` if attempts exhausted

### Attempt gate

```bash
ATTEMPT_COUNT="$(find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_${RUN_ID}" | wc -l | tr -d ' ')"
if [ "${ATTEMPT_COUNT:-0}" -ge "${MAX_ATTEMPTS:-3}" ]; then
  echo "ERROR: max attempts reached"
  python - <<'PY'
import json, os, pathlib, datetime, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

block = {
    "schema_version": "go.block-state.v1",
    "run_id": run_id,
    "terminal_id": terminal_id,
    "status": "blocked",
    "reason_code": "max_attempts_reached",
    "reason_summary": f"verification failed after {os.environ.get('MAX_ATTEMPTS','3')} attempts",
    "origin_step": "verify_end_to_end",
    "can_retry": False,
    "requires_user_input": True,
    "waiver_allowed": False,
    "opened_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "evidence_paths": [str(state_dir / f"verification-results_{run_id}.txt")]
}
path = state_dir / f"block-state_{run_id}.json"
path.write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
PY
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
fi
```

### Verification rule

Run every command from `task.verification_commands` literally and capture complete output.

### Execution snippet

```bash
python - <<'PY'
import json, os, subprocess, pathlib, datetime, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
task_path = state_dir / f"active-task_{run_id}.json"
payload = json.loads(task_path.read_text(encoding="utf-8"))
commands = payload["task"].get("verification_commands", [])

results_path = state_dir / f"verification-results_{run_id}.txt"
summary_path = state_dir / f"verification-summary_{run_id}.json"

if not commands:
    results_path.write_text("No verification commands supplied.\n", encoding="utf-8")
    summary = {
        "run_id": run_id,
        "verified": False,
        "reason": "missing_verification_commands",
        "commands": []
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    sys.exit(3)

all_ok = True
command_results = []

with results_path.open("w", encoding="utf-8") as f:
    for cmd in commands:
        f.write(f"$ {cmd}\n")
        f.write("=" * 80 + "\n")
        proc = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        f.write(proc.stdout or "")
        if proc.stderr:
            f.write("\n[stderr]\n")
            f.write(proc.stderr)
        f.write(f"\n[exit_code] {proc.returncode}\n\n")
        if proc.returncode != 0:
            all_ok = False
        command_results.append({
            "command": cmd,
            "exit_code": proc.returncode,
            "passed": proc.returncode == 0
        })

summary = {
    "run_id": run_id,
    "verified": all_ok,
    "verified_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "commands": command_results
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

sys.exit(0 if all_ok else 4)
PY

STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  NEXT_ATTEMPT=$((ATTEMPT_COUNT + 1))
  touch "$GO_STATE_DIR/.attempt_${NEXT_ATTEMPT}_$RUN_ID"
  if [ "$NEXT_ATTEMPT" -ge "${MAX_ATTEMPTS:-3}" ]; then
    python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

block = {
    "schema_version": "go.block-state.v1",
    "run_id": run_id,
    "terminal_id": terminal_id,
    "status": "blocked",
    "reason_code": "verification_failed",
    "reason_summary": "verification commands did not all pass",
    "origin_step": "verify_end_to_end",
    "retry_count": int(os.environ.get("ATTEMPT_COUNT", "0")),
    "can_retry": False,
    "requires_user_input": True,
    "waiver_allowed": False,
    "opened_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "evidence_paths": [str(state_dir / f"verification-results_{run_id}.txt")]
}
path = state_dir / f"block-state_{run_id}.json"
path.write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
PY
    touch "$GO_STATE_DIR/.blocked_$RUN_ID"
    echo "<promise>BLOCKED</promise>"
    exit 1
  fi
  echo "ERROR: verification failed"
  exit 1
fi

touch "$GO_STATE_DIR/.verified_$RUN_ID"
echo "✓ Verification passed"

# Update run-status
python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

status_path = state_dir / f"run-status_{run_id}.json"
data = {}
if status_path.exists():
    data = json.loads(status_path.read_text(encoding="utf-8"))

data.update({
    "schema_version": "go.run-status.v1",
    "go_run_id": run_id,
    "terminal_id": terminal_id,
    "skill_version": "2.0.0",
    "status": "verified",
    "current_step": "verify_end_to_end",
    "updated_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "verification_result_path": str(state_dir / f"verification-summary_{run_id}.json")
})

status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

### Recommendation block

After verification, emit recommendations only if evidence warrants user input:

```bash
python - <<'PY'
import json, os, pathlib

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

simplify_path = state_dir / f"simplify-summary_{run_id}.json"
simplify_status = "passed"
if simplify_path.exists():
    simp = json.loads(simplify_path.read_text())
    simplify_status = simp.get("status", "passed")

recommendations = []

# HIGH/CRITICAL from simplify
if simplify_status == "failed":
    recommendations.append({
        "type": "external-review",
        "evidence": "simplify HIGH/CRITICAL findings",
        "prompt": "Simplify found critical issues. Proceed? [yes/no/waive]"
    })

# TDD not validated
tdd_path = state_dir / f"tdd-receipt_{run_id}.json"
if tdd_path.exists():
    tdd = json.loads(tdd_path.read_text())
    if tdd.get("required") and not tdd.get("validated"):
        recommendations.append({
            "type": "tdd-debug",
            "evidence": "TDD required but not validated",
            "prompt": "TDD not fully validated. Proceed? [yes/no]"
        })

# Surface recommendations
if recommendations:
    print("\n=== /go RECOMMENDATIONS ===")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. [{rec['type']}] {rec['evidence']}")
        print(f"   {rec['prompt']}")
    print("=========================\n")
PY
```

---

## STEP 4: SIMPLIFY

**Requires flag:** `.verified_{RUN_ID}`
**Creates file:** `simplify-status_{RUN_ID}.md`
**Creates file:** `simplify-summary_{RUN_ID}.json`
**Creates flag:** `.simplified_{RUN_ID}` on success

### Rule

- If docs-only diff: skip simplify but record structured skip.
- If code changes exist: run `/simplify`.
- If simplify reports `HIGH` or `CRITICAL`, fail this run.

### Example implementation

```bash
SIMPLIFY_MD="$GO_STATE_DIR/simplify-status_$RUN_ID.md"
SIMPLIFY_JSON="$GO_STATE_DIR/simplify-summary_$RUN_ID.json"

if [ "$DOCS_ONLY" = "true" ]; then
  cat > "$SIMPLIFY_MD" <<EOF
# Simplify Status

Status: SKIPPED
Reason: docs-only diff
EOF

  cat > "$SIMPLIFY_JSON" <<EOF
{
  "run_id": "$RUN_ID",
  "status": "skipped",
  "reason": "docs_only"
}
EOF
else
  /simplify > "$SIMPLIFY_MD" 2>&1 || true

  if grep -Eiq 'CRITICAL|HIGH' "$SIMPLIFY_MD"; then
    python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

block = {
    "schema_version": "go.block-state.v1",
    "run_id": run_id,
    "terminal_id": terminal_id,
    "status": "blocked",
    "reason_code": "simplify_failed",
    "reason_summary": "simplify produced HIGH or CRITICAL findings",
    "origin_step": "simplify_code",
    "can_retry": False,
    "requires_user_input": True,
    "waiver_allowed": True,
    "opened_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "evidence_paths": [str(state_dir / f"simplify-status_{run_id}.md")]
}
path = state_dir / f"block-state_{run_id}.json"
path.write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
PY
    touch "$GO_STATE_DIR/.blocked_$RUN_ID"
    echo "<promise>BLOCKED</promise>"
    exit 1
  fi

  cat > "$SIMPLIFY_JSON" <<EOF
{
  "run_id": "$RUN_ID",
  "status": "passed"
}
EOF
fi

touch "$GO_STATE_DIR/.simplified_$RUN_ID"
echo "✓ Simplify gate passed"
```

---

## STEP 5: 7-PASS REVIEW

**Requires flag:** `.simplified_{RUN_ID}`
**Creates files:** review pass markdown files
**Creates file:** `review-summary_{RUN_ID}.json`
**Creates flag:** `.reviews-passed_{RUN_ID}`

### Pass names

1. correctness
2. scope
3. tests
4. simplicity
5. regressions
6. maintainability
7. pr-ready

### Depth rules

- `quick`: correctness, pr-ready
- `standard`: correctness, scope, tests, regressions, pr-ready
- `full`: all seven passes

### Pass file format

Each pass file must contain:
- pass name
- checklist
- findings
- status: `PASS` or `REVIEW_REQUIRED`

### Minimal generation pattern

```bash
run_pass() {
  local pass_name="$1"
  local pass_file="$GO_STATE_DIR/review-pass-${pass_name}_$RUN_ID.md"

  cat > "$pass_file" <<EOF
# Review Pass: ${pass_name}

Status: PASS

## Checklist
- Reviewed relevant changes
- Checked task alignment
- Checked for obvious blockers

## Findings
- No blocking findings recorded
EOF
}

PASSES=""
case "$REVIEW_DEPTH" in
  quick)
    PASSES="correctness pr-ready"
    ;;
  standard)
    PASSES="correctness scope tests regressions pr-ready"
    ;;
  *)
    PASSES="correctness scope tests simplicity regressions maintainability pr-ready"
    ;;
esac

FAILED_REVIEW="false"
for pass in $PASSES; do
  run_pass "$pass"
  if grep -Eq 'Status:\s*REVIEW_REQUIRED' "$GO_STATE_DIR/review-pass-${pass}_$RUN_ID.md"; then
    FAILED_REVIEW="true"
  fi
done

cat > "$GO_STATE_DIR/review-summary_$RUN_ID.json" <<EOF
{
  "run_id": "$RUN_ID",
  "review_depth": "$REVIEW_DEPTH",
  "failed": $([ "$FAILED_REVIEW" = "true" ] && echo "true" || echo "false")
}
EOF

if [ "$FAILED_REVIEW" = "true" ]; then
  python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

failed_passes = []
review_dir = state_dir
for md_file in review_dir.glob(f"review-pass-*_{run_id}.md"):
    content = md_file.read_text(encoding="utf-8")
    if "Status:\s*REVIEW_REQUIRED" in content or "REVIEW_REQUIRED" in content:
        failed_passes.append(md_file.name)

block = {
    "schema_version": "go.block-state.v1",
    "run_id": run_id,
    "terminal_id": terminal_id,
    "status": "blocked",
    "reason_code": "review_failed",
    "reason_summary": f"Review passes failed: {', '.join(failed_passes)}",
    "origin_step": "seven_pass_review",
    "can_retry": True,
    "requires_user_input": False,
    "waiver_allowed": True,
    "opened_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "evidence_paths": [str(p) for p in review_dir.glob(f"review-pass-*_{run_id}.md")]
}
path = state_dir / f"block-state_{run_id}.json"
path.write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
PY
  touch "$GO_STATE_DIR/.blocked_$RUN_ID"
  echo "<promise>BLOCKED</promise>"
  exit 1
fi

touch "$GO_STATE_DIR/.reviews-passed_$RUN_ID"
echo "✓ Review passes complete"
```

### Pre-PR stakeholder sync recommendation

If task contract marks `requires_approval: true` or review depth is `full`:

```bash
python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]
task_path = state_dir / f"active-task_{run_id}.json"
status_path = state_dir / f"run-status_{run_id}.json"

task = json.loads(task_path.read_text())["task"]
requires_approval = task.get("requires_approval", False)
review_depth = os.environ.get("REVIEW_DEPTH", "standard")

data = {}
if status_path.exists():
    data = json.loads(status_path.read_text(encoding="utf-8"))

if requires_approval or review_depth == "full":
    rec = {
        "type": "stakeholder-sync",
        "evidence": f"requires_approval={requires_approval}, review_depth={review_depth}",
        "prompt": "PR ready. Notify stakeholder? [yes/notify/skip]",
        "resolved": False,
        "resolved_at": None
    }
    data.setdefault("recommendations", []).append(rec)
    status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("\n=== /go RECOMMENDATION ===")
    print("[stakeholder-sync] PR ready — notify stakeholder?")
    print("Proceed? [yes/notify/skip]")
    print("=========================\n")
    choice = input().strip().lower()
    rec["resolved"] = True
    rec["resolved_at"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    if choice == "skip" or choice == "no" or choice == "":
        rec["prompt"] += " [SKIPPED]"
    elif choice == "notify":
        rec["prompt"] += " [NOTIFYING]"
    else:
        rec["prompt"] += " [ACCEPTED]"
    data["recommendations"] = [r for r in data.get("recommendations", []) if r.get("type") != "stakeholder-sync"]
    data["recommendations"].append(rec)
    status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
```

---

## STEP 6: LOCAL PR ARTIFACTS

**Requires flag:** `.reviews-passed_{RUN_ID}`
**Creates files:** commit message, PR title, PR body, PR-ready report
**Creates file:** `task-result_{RUN_ID}.json`
**Creates flag:** `.pr-ready_{RUN_ID}`

### Artifact generation

Use the selected task from `active-task_{RUN_ID}.json` and generate:

- `commit-message_{RUN_ID}.txt`
- `pr-title_{RUN_ID}.txt`
- `pr-body_{RUN_ID}.md`
- `pr-ready_{RUN_ID}.md`
- `task-result_{RUN_ID}.json`

### Example snippet

```bash
python - <<'PY'
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
task_data = json.loads((state_dir / f"active-task_{run_id}.json").read_text(encoding="utf-8"))
task = task_data["task"]

task_id = task.get("id", "TASK")
title = task.get("title", "Untitled task")
objective = task.get("objective", "")
review_depth = os.environ.get("REVIEW_DEPTH", "full")

commit_msg = f"""feat: complete {task_id.lower()} {title.lower()}

VERIFIED: PASS
SIMPLIFIED: PASS
REVIEWED: {review_depth.upper()}

RUN_ID: {run_id}
TASK_ID: {task_id}
"""

pr_title = f"{task_id}: {title}"

pr_body = f"""## Summary

- Completed {task_id}: {title}
- Objective: {objective}

## Verification

See `verification-results_{run_id}.txt`.

## Quality gates

- Verification: PASS
- Simplify: PASS
- Review depth: {review_depth}

## Notes

- Local PR artifacts generated only
- No remote push performed
"""

pr_ready = f"""# PR Ready

Task: {task_id}
Title: {title}
Run: {run_id}

Status:
- Verification: PASS
- Simplify: PASS
- Reviews: PASS

Next steps:
1. Review local artifacts
2. Commit using generated commit message
3. Open PR manually if desired

<promise>PR_READY</promise>
"""

result = {
    "run_id": run_id,
    "task_id": task_id,
    "status": "pr_ready",
    "completed_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
}

(state_dir / f"commit-message_{run_id}.txt").write_text(commit_msg, encoding="utf-8")
(state_dir / f"pr-title_{run_id}.txt").write_text(pr_title + "\n", encoding="utf-8")
(state_dir / f"pr-body_{run_id}.md").write_text(pr_body + "\n", encoding="utf-8")
(state_dir / f"pr-ready_{run_id}.md").write_text(pr_ready + "\n", encoding="utf-8")
(state_dir / f"task-result_{run_id}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
PY

touch "$GO_STATE_DIR/.pr-ready_$RUN_ID"
echo "<promise>PR_READY</promise>"
```

---

## STEP 7: LOOP CHECK

Loop check must use the structured tasks file, not `plan.md`.

### Rule

After PR-ready for the current task:
- If more actionable tasks remain after the selected task, emit `<promise>MORE_TASKS_IN_PLAN</promise>`.
- Otherwise emit `<promise>ALL_TASKS_COMPLETE</promise>`.

### Example snippet

```bash
python - <<'PY'
import json, os, pathlib, sys

tasks_file = pathlib.Path(os.environ["GO_TASKS_FILE"])
state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

selected = json.loads((state_dir / f"active-task_{run_id}.json").read_text(encoding="utf-8"))["task"]
selected_id = selected.get("id")
data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
allowed = {"ready", "queued", "approved"}

seen_selected = False
remaining = False

for task in tasks:
    if task.get("id") == selected_id:
        seen_selected = True
        continue
    if seen_selected and task.get("status") in allowed:
        remaining = True
        break

print("<promise>MORE_TASKS_IN_PLAN</promise>" if remaining else "<promise>ALL_TASKS_COMPLETE</promise>")
PY
```

---

## Prohibited actions

- Running on `main` or `master`
- Using `plan.md` as scheduler source of truth
- Proceeding without required prior flag
- Ignoring failed verification commands
- Ignoring HIGH or CRITICAL simplify findings
- Skipping required review passes for the selected review depth
- Auto-pushing or creating remote PRs
- Modifying forbidden files listed in the selected task contract

---

## Minimal operator notes

Recommended manual commit step after success:

```bash
git commit -F "$GO_STATE_DIR/commit-message_$RUN_ID.txt"
```

Optional manual PR creation:

```bash
gh pr create --title "$(cat "$GO_STATE_DIR/pr-title_$RUN_ID.txt")" --body-file "$GO_STATE_DIR/pr-body_$RUN_ID.md"
```
