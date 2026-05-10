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

and creates `.claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/<RUN_ID>/session.json`.

---

### Step 1: RED — Write Failing Tests

1. Write tests that define the expected behavior.
2. Execute tests via wrapper:

```bash
python .claude/skills/tdd/run_phase.py --run-id "<RUN_ID>" --phase red
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

Create: `.claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/<RUN_ID>/evidence.json` matching `TddEvidence` in `session_models.py`.

You **reference** receipts — you do NOT embed raw logs.

Required fields:
- `metadata.run_id`, `metadata.mode`, `metadata.task`, `metadata.cwd`, `metadata.test_command`, `metadata.started_at`
- `target_component`, `expected_behavior`
- `test_files_modified`, `impl_files_modified`
- `red.receipt_path` → `"red_receipt.json"`
- `green.receipt_path` → `"green_receipt.json"`

---

### Step 5: Validate

```bash
python .claude/skills/tdd/validate_tdd.py "<RUN_ID>"
```

On SUCCESS:
- it writes `validated.json` under `.claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/<RUN_ID>/`,
- updates `session.phase` to `validated`,
- clears `.active_run`.

---

### Step 6: Evidence-Bound Verification (MANDATORY)

You MUST complete this step before stopping. No exceptions.

1. Run each command from the `verification.commands` frontmatter.
2. Write results to artifact: `P:\\\\\\.claude/.artifacts/{terminal_id}/tdd/verification.json`.
3. Paste each tool's output verbatim.
4. For each command: PASS or FAIL with one sentence.

---

## Prohibited Behaviors

1. **Never run tests directly.** Always use `run_phase.py`.
2. **Never edit receipts or logs.**
3. **Never skip RED.** Wrapper and validator assume RED happened before GREEN.
4. **Never exceed 3 validation attempts.** After 3 failures, STOP and ask for help.
5. **If you claim refactor work, you must prove it.** Distinct stdout from GREEN required.
