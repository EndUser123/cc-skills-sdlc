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
        command: "ls -la .claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/$RUN_ID/evidence.json 2>/dev/null || echo 'MISSING'"
    - description: "Confirm validated.json exists (validation passed)"
      tool: "Bash"
      args:
        command: "ls -la .claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/$RUN_ID/validated.json 2>/dev/null || echo 'NOT VALIDATED'"
    - description: "Show test files modified"
      tool: "Bash"
      args:
        command: "python -c \"import json; e=json.load(open('.claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/$RUN_ID/evidence.json')); print('test_files:', e.get('test_files_modified',[])); print('impl_files:', e.get('impl_files_modified',[]))\" 2>/dev/null || echo 'CANNOT READ'"
    - description: "Verify RED receipt exists and GREEN receipt exists"
      tool: "Bash"
      args:
        command: "ls .claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/$RUN_ID/red_receipt.json .claude/.artifacts/$CLAUDE_TERMINAL_ID/tdd/$RUN_ID/green_receipt.json 2>/dev/null || echo 'RECEIPTS MISSING'"
  summary_mode: evidence_only
  expected_artifacts:
    - ".claude/.artifacts/{TERMINAL_ID}/tdd/{RUN_ID}/evidence.json"
    - ".claude/.artifacts/{TERMINAL_ID}/tdd/{RUN_ID}/validated.json"
    - ".claude/.artifacts/{TERMINAL_ID}/tdd/{RUN_ID}/red_receipt.json"
    - ".claude/.artifacts/{TERMINAL_ID}/tdd/{RUN_ID}/green_receipt.json"
---

# /tdd Protocol (NTP v3.2)

You are operating under a **Wrapper-Only Native Tool-Gated TDD Protocol**.

**Mandatory Protocol:** See `__lib/tdd_protocol.md` for the RED → GREEN → VALIDATE workflow.

## Invocation

```bash
/tdd [mode] "description"
```

**Modes:** `feature` | `bugfix` | `refactor`

## Summary of Phases

1. **Step 0: Initialize** - `generate_context.py` to create `session.json`.
2. **Step 1: RED** - `run_phase.py --phase red` (Must fail).
3. **Step 2: GREEN** - `run_phase.py --phase green` (Must pass).
4. **Step 3: REFACTOR** - (Optional) `run_phase.py --phase refactor`.
5. **Step 4: Evidence** - Create `evidence.json`.
6. **Step 5: Validate** - `validate_tdd.py` (Must pass).

## Evidence-Bound Verification (MANDATORY)

You MUST complete this step before stopping. See `__lib/tdd_protocol.md` for formatting rules.

---

## Prohibited Behaviors

1. **Never run tests directly.** Always use `run_phase.py`.
2. **Never edit receipts or logs.**
3. **Never skip RED.**
4. **Never exceed 3 validation attempts.**
5. **If you claim refactor work, you must prove it.**

