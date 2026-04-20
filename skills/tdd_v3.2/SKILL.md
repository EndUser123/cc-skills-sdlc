---
name: tdd
description: >
  Strict Test-Driven Development protocol. All test execution goes through
  run_phase.py which produces HMAC-signed receipts. The validator checks
  receipts, log integrity, temporal ordering, and output patterns. No
  pasted logs. Windows 11 optimized with O(1) active session tracking.
hooks:
  pre_prompt:
    - command: "python .claude/hooks/preflight_require_tdd.py"
  pre_response:
    - command: "python .claude/hooks/stop_if_tdd_unverified.py"

# Evidence-bound verification (anti-confabulation)
verification:
  commands:
    - description: "Confirm evidence.json exists for this run"
      tool: "Bash"
      args:
        command: "ls -la .claude-state/tdd/$RUN_ID/evidence.json 2>/dev/null || echo 'MISSING'"
    - description: "Confirm validated.json exists (validation passed)"
      tool: "Bash"
      args:
        command: "ls -la .claude-state/tdd/$RUN_ID/validated.json 2>/dev/null || echo 'NOT VALIDATED'"
    - description: "Show test files modified"
      tool: "Bash"
      args:
        command: "python -c \"import json; e=json.load(open('.claude-state/tdd/$RUN_ID/evidence.json')); print('test_files:', e.get('test_files_modified',[])); print('impl_files:', e.get('impl_files_modified',[]))\" 2>/dev/null || echo 'CANNOT READ'"
    - description: "Verify RED receipt exists and GREEN receipt exists"
      tool: "Bash"
      args:
        command: "ls .claude-state/tdd/$RUN_ID/red_receipt.json .claude-state/tdd/$RUN_ID/green_receipt.json 2>/dev/null || echo 'RECEIPTS MISSING'"
  summary_mode: evidence_only
  expected_artifacts:
    - ".claude-state/tdd/{RUN_ID}/evidence.json"
    - ".claude-state/tdd/{RUN_ID}/validated.json"
    - ".claude-state/tdd/{RUN_ID}/red_receipt.json"
    - ".claude-state/tdd/{RUN_ID}/green_receipt.json"
---

# /tdd Protocol (NTP v3.2)

You are operating under a **Wrapper-Only Native Tool-Gated TDD Protocol**.

Every code change MUST pass through RED → GREEN → VALIDATE before you respond.

You NEVER run the test command directly — you ALWAYS use `run_phase.py`.

---

## Invocation

```bash
/tdd [mode] "description"
```

**Modes:** `feature` | `bugfix` | `refactor`

---

## Execution — Follow Exactly

### Step 0: Initialize Session

```bash
python .claude/skills/tdd/generate_context.py "[mode]" "<description>"
```

This prints:

- a **run ID**
- a **detected test command**
- a **Standard Operating Procedure (SOP)**

and creates `.claude-state/tdd/<RUN_ID>/session.json`.

---

### Step 1: RED — Write Failing Tests

1. Write tests that define the expected behavior.
2. Execute tests via wrapper:

```bash
python .claude/skills/tdd/run_phase.py --run-id "<RUN_ID>" --phase red
# Optional (narrow scope):
# python .claude/skills/tdd/run_phase.py --run-id "<RUN_ID>" --phase red --override-cmd "pytest tests/foo_test.py"
```

The wrapper:

- runs the test command,
- captures stdout/stderr and exit code,
- writes `red.stdout.log` / `red.stderr.log`,
- writes `red_receipt.json` with an HMAC signature.

RED MUST FAIL.

---

### Step 2: GREEN — Minimal Implementation

1. Implement the minimum code to make tests pass.
2. Execute GREEN via wrapper:

```bash
python .claude/skills/tdd/run_phase.py --run-id "<RUN_ID>" --phase green
```

GREEN MUST PASS.

---

### Step 3: REFACTOR (optional but enforced when claimed)

If you refactor any files, you MUST:

```bash
python .claude/skills/tdd/run_phase.py --run-id "<RUN_ID>" --phase refactor
```

REFACTOR MUST PASS and have a distinct stdout from GREEN.

---

### Step 4: Draft Evidence

Create:

```text
.claude-state/tdd/<RUN_ID>/evidence.json
```

matching `TddEvidence` in `session_models.py`.

You **reference** receipts — you do NOT embed raw logs.

Required fields:

- `metadata.run_id`, `metadata.mode`, `metadata.task`, `metadata.cwd`,
  `metadata.test_command`, `metadata.started_at`
- `target_component`, `expected_behavior`
- `test_files_modified`, `impl_files_modified`
- `red.receipt_path` → `"red_receipt.json"`
- `green.receipt_path` → `"green_receipt.json"`

Optional:

- `refactor.receipt_path`
- `files_refactored`
- `failure_summary` (human-readable notes)

---

### Step 5: Validate

```bash
python .claude/skills/tdd/validate_tdd.py "<RUN_ID>"
```

The validator will:

- load `session.json` and `evidence.json`,
- verify HMAC-signed receipts and log hashes,
- check RED fails and GREEN passes,
- enforce ordering (GREEN after RED),
- enforce refactor semantics if present.

On SUCCESS:

- it writes `validated.json` under `.claude-state/tdd/<RUN_ID>/`,
- updates `session.phase` to `validated`,
- clears `.active_run` so the post-response hook will allow your reply.

On FAILURE:

- it increments `session.retries`,
- prints detailed errors,
- stops after **3 attempts**. On 3rd failure, you MUST ask the user for guidance.

---

### Step 6: Evidence-Bound Verification (MANDATORY)

You MUST complete this step before stopping. No exceptions.

Do NOT write a freeform summary. Instead:

1. Run each command from the `verification.commands` frontmatter
2. Write results to artifact: `P:/.claude/.artifacts/{terminal_id}/tdd/verification.json`
3. Paste each tool's output verbatim
4. For each command: PASS or FAIL with one sentence

**Prohibited in summaries:**
- Line numbers not shown in this turn's tool output
- File contents not read in this turn
- Claims about test results not from this turn's run_phase.py output
- "All tests pass" without showing actual pytest output from this turn

**Format:**
```
## Verification Results

### [command description]
[verbatim tool output]
Status: PASS/FAIL — [one sentence]
```

1. **Never run tests directly.** Always use `run_phase.py` for RED/GREEN/REFACTOR.
2. **Never edit receipts or logs.** You MUST NOT modify `*_receipt.json`, `*.stdout.log`, `*.stderr.log`, `session.json`, or `validated.json`.
3. **Never skip RED.** Wrapper and validator assume RED happened before GREEN.
4. **Never exceed 3 validation attempts.** After 3 failures, STOP and ask for help.
5. **If you claim refactor work, you must prove it.** Any non-empty `files_refactored`
   requires a passing REFACTOR phase and distinct stdout from GREEN.

---

## Multi-Terminal Isolation

- Each TDD session is partitioned by `run_id` under `.claude-state/tdd/`
- Active session pointer is `.active_run` file (O(1) check, not directory scan)
- Stale pointer cleanup: if run_dir missing, pointer is cleaned automatically
- Validation includes `run_id` cross-check to prevent session confusion
- Localized `SessionState.retries` avoids global locking (Windows-compatible)
