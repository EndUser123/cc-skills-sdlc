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

## Hard Rules

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
