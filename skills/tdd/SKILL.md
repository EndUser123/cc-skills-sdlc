---
name: tdd
description: TDD skill with RED/GREEN cycle enforcement, mutation gate, and test isolation mandate
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
6. **Never allow tests to scan `WORKSPACE_ROOT`.** Tests MUST NOT trigger recursive filesystem walks, live network calls, or unguarded subprocess invocations (e.g., `subprocess.run(["pytest", ...])`). Always mock these boundaries at the test boundary.
7. **Never define a function in a facade module that shadows an imported name.** If a function with the same name is already imported from a sub-module, the facade definition silently overrides it and breaks mutation testing. Use explicit aliasing or `del` the local definition.
8. **Never claim completion on a critical-path module without a mutation gate.** If the target module is listed in `quality_gates.json` under `critical`, invoke `/t --mode mutation` after GREEN passes. A mutation score below the module's target threshold MUST block completion.

## Performance Contract

- **Unit tests (GREEN):** Must complete in under 5 seconds. If exceeded, check for missing mocks or subprocess leaks.
- **Integration tests (GREEN):** Must complete in under 30 seconds.
- **Slow tests are evidence of a boundary leak**, not of thoroughness.

## Mutation Escalation Ladder

After GREEN passes and coverage of the new code exceeds 80%:

1. Check if the target module is declared in `P:/.claude/quality_gates.json` under `modules`.
2. If `tier: critical` → invoke `/t --mode mutation --target <file>`. Score must meet `target` (default 80%).
3. If `tier: standard` → mutation is recommended but advisory (default 60% target).
4. A failed critical-path mutation score MUST block evidence drafting. Do not write `evidence.json` until resolved.

