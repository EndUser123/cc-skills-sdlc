---
name: tdd_v3.2
description: TDD skill with RED/GREEN cycle enforcement
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

**Evidence-first rule:** Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures, not from assumption or not having looked.

---

## Prohibited Behaviors

1. **Never run tests directly.** Always use `run_phase.py`.
2. **Never edit receipts or logs.**
3. **Never skip RED.**
4. **Never exceed 3 validation attempts.**
5. **If you claim refactor work, you must prove it.**

