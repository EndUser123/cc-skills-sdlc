---
name: code
version: 4.0.0
description: AI-assisted feature development workflow (Idea to PR) with mandatory consumer handshake proof and Contract Authority Packet consumption for contract-sensitive work. Uses the shared enforce layer for phase gate tracking.
category: development
enforcement: strict
domain: development
depends_on:
  - sdlc: ">=0.1.0"
triggers:
  - 'code feature'
  - 'build feature'
  - 'new feature'
  - 'implement feature'
  - 'start development'
argument-hint: <feature_description|stats|continue> [--fast|--full] [--no-loop] [--no-ralph-loop] [--ralph-enable] [--ralph-disable] [--no-got] [--no-tot] [--no-checklist]
context: main
user-invocable: true
status: stable
depends_on_skills: ['/search']
requires_tools: ['python', 'git', 'pytest']
aliases:
  - '/code'
hooks:
  UserPromptSubmit:
    - matcher: "^/code"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PLUGIN_ROOT\"/hooks/detect_continuous_mode.py"
  PreToolUse:
    - matcher: "Edit|Write|MultiEdit"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PLUGIN_ROOT\"/skills/code_v4.0/hooks/PreToolUse_plan_consumer_gate.py"
  PostToolUse:
    - matcher: ".*"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PLUGIN_ROOT\"/skills/code_v4.0/hooks/PostToolUse_breadcrumb_tracker.py"
  Stop:
    - matcher: ".*"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PLUGIN_ROOT\"/skills/code_v4.0/hooks/Stop_enforce_gate.py"
          description: "Verify all gateable phases passed before DONE (shared enforce layer)"
workflow_steps:
  - pre_execution_checklist
  - analyze_query_intent
  - select_execution_model
  - resolve_plan_state
  - initialize_resume_ledger
  - requirements_clarity_check
  - preflight_context_validation
  - explore_codebase
  - design_solution
  - consumer_contract_precheck
  - tdd_implementation
  - smoke_validation
  - full_test_suite
  - id: tier0_checklist_verification
    kind: verification
  - id: audit_quality_checks
    kind: verification
  - id: critique_agent_review
    kind: verification
  - id: trace_manual_verification
    kind: verification
  - id: producer_consumer_trace_verification
    kind: verification
  - id: done_final_certification
    kind: verification
---

# /code v4.0 -- Feature Development Mission Control

## What changed from v3.0

v4.0 uses the **shared enforce layer** (`enforce/phase_ledger.py` + `enforce/stop_gate.py`) for phase gate tracking instead of the skill-local `code_phase_ledger.py`. The enforcement logic, exit codes, and phase definitions are identical to v3.0 — only the infrastructure moved to a reusable shared library.

Phase gates:
- HARD (blocking if missing): `consumer_contract_precheck`, `smoke_validation`, `full_test_suite`, `audit_quality_checks`
- ADVISORY (warning only): `producer_consumer_trace_verification`, `trace_manual_verification`

All other behavior is identical to `/code` v3.0.

---

# /code -- Feature Development Mission Control (full reference)

## Purpose

Systematic workflow to transform an idea into a production-ready feature: **REQUIREMENTS -> PRE-FLIGHT -> EXPLORE -> PLAN -> CONTRACT PRECHECK -> TDD -> TEST -> AUDIT -> TRACE -> PRODUCER/CONSUMER TRACE -> DONE**.

`/code` is an end-to-end workflow across all phases. `/tdd` may be used during TDD when useful, but `/code` is not coupled to `/tdd`.

## Quick Start

```bash
# Multi-task plan with autonomous loop (default)
/code plan.md

# Single task (opt-out of loop)
/code "Add user authentication" --no-loop

# Fast route (skip ceremony)
/code "fix typo" --fast --no-checklist

# Stats mode (no build execution)
/code stats
```

## Key Flags

| Flag | Effect |
|------|--------|
| `--fast` | Skip ceremony, minimum viable route (also skips full_test_suite gate) |
| `--full` | Full ceremony route |
| `--no-loop` | Single-task mode (no autonomous iteration) |
| `--ralph-enable` | Force enable Ralph Loop |
| `--ralph-disable` | Force disable Ralph Loop |
| `--no-got` | Disable Graph-of-Thought planning |
| `--no-tot` | Disable Tree-of-Thought tracing |
| `--no-checklist` | Skip pre-execution checklist |
| `--interactive`, `-i` | Step-by-step mode (pause at phase boundaries) |

## Phase Gate Enforcement (v4.0)

The Stop hook enforces phase gates via the shared `enforce/` library. Missing hard gates cause exit 2 (blocking). Missing advisory gates cause exit 1 (warning). Cold start (no ledger yet) returns exit 0.

```
Ledger path: ~/.claude/.state/enforce/code_v4.0/{TERMINAL_ID}/phase-ledger.json
Evidence: phase ledger entries written by PreToolUse + PostToolUse hooks
```

## Autonomous Loop Mode (Default)

`/code` **runs in autonomous loop mode by default** for multi-task plans:
- Parses plan.md for tasks (checkbox format `- [ ] TASK-001`)
- For each incomplete task, runs full workflow (REQUIREMENTS -> TDD -> TEST -> AUDIT -> TRACE -> DONE)
- Exits when all tasks complete or genuine blocker hit
- Ralph Loop auto-detection: implementation keywords enable it, research keywords disable it
- See `references/ralph-loop-guide.md` for full details including override flags

## Continuous Execution Mode (Default)

Continuous mode is **ON by default** (v2.24.0+). `/code` runs through all phases without stopping:
- Phase boundaries are NOT stopping points
- Only stops for genuine blockers (ambiguous requirements, errors, missing info)
- Opt-out: `--interactive`, `--step-by-step`, `-i`
- See `references/continuous-mode-implementation.md` for implementation details

## Core Workflow Phases

| Phase | Goal | Key Tools | Reference |
|-------|------|-----------|-----------|
| **1. REQUIREMENTS** | Clarity Check | Restate requirements, identify gaps | `references/plan-phase-details.md` |
| **2. PRE-FLIGHT** | Context Validation | health check, checkpoint, dependency check | `references/plan-phase-details.md` |
| **3. EXPLORE** | Understand Codebase | `/search`, subagent discovery, modernization detection | `references/plan-phase-details.md` |
| **4. PLAN** | Design Solution | Manual planning, pre-mortem, GoT enhancement, execution path verification | `references/plan-phase-details.md` |
| **5. CONTRACT PRECHECK** | Confirm consumers exist | Schema/field expectations, freshness, invalidation, failure behavior | `references/plan-phase-details.md` |
| **6. TDD** | RED -> GREEN -> REFACTOR | test-first implementation via subagents | `references/tdd-phase-details.md` |
| **7. TEST** | Full Test Suite | pytest, integration tests, regression tests | `references/test-phase-details.md` |
| **8. AUDIT** | Quality Checks | ruff, mypy, pylint, eslint, tsc, code-reviewer | `references/audit-phase-details.md` |
| **8.5. FIX VERIFICATION** | Confirm fixes + edge cases | per-fix verification, adversarial-failure-modes agent | `references/audit-phase-details.md` |
| **9. TRACE** | Verify Logic | `/trace` manual code trace-through, ToT enhancement | `references/trace-phase-details.md` |
| **10. PRODUCER/CONSUMER TRACE** | Verify actual handoff path | Consumer handshake, field presence, end-to-end boundary proof | `references/trace-phase-details.md` |
| **11. DONE** | Final Certification | build verification, done checklist, deployment guidance | `references/done-phase-details.md` |

## Your Workflow

0. **SEARCH FIRST** -- Check existing context before starting
   ```bash
   /search "{feature_description}" --backend chs,cks,code
   ```
1. **REQUIREMENTS (Phase 1)** -- Clarity check
2. **PRE-FLIGHT (Phase 2)** -- Context validation
3. **EXPLORE (Phase 3)** -- Subagent discovery -> curated context
4. **PLAN (Phase 4)** -- Design solution with pre-mortem
5. **CONTRACT PRECHECK (Phase 5)** -- Verify downstream consumers and expected fields
6. **TDD (Phase 6)** -- RED -> GREEN -> REFACTOR loop
7. **TEST (Phase 7)** -- Full test suite
8. **AUDIT (Phase 8)** -- Quality checks (can run parallel with TEST)
8.5. **FIX VERIFICATION (Phase 8.5)** -- Confirm fixes applied + edge case analysis
9. **TRACE (Phase 9)** -- Manual code trace-through
10. **PRODUCER/CONSUMER TRACE (Phase 10)** -- Verify actual handoff path end-to-end
11. **DONE (Phase 11)** -- Final certification

Workflow override:
- `--fast`: REQUIREMENTS -> PLAN STATE -> CONTRACT PRECHECK -> TDD -> TEST -> AUDIT -> TRACE -> PRODUCER/CONSUMER TRACE -> DONE
- **TRACE is mandatory in all modes** -- no exemptions for speed
- **PRODUCER/CONSUMER TRACE is mandatory** for stateful, resumable, hook, artifact, or integration work

## Consumer Contract Precheck (Between PLAN and TDD)

Before implementation begins, verify that every downstream consumer expected to use the new output actually exists and has explicit expectations.

If the work is contract-sensitive, load the latest `Contract Authority Packet` from `/arch` first and treat it as authoritative for boundary semantics during implementation.

**Principle: Enforcement lives with the consumer, not the producer.**

`/code` must refuse to consume a plan artifact that fails its contract, rather than relying on a global hook to catch all bad writes. Write-time validation prevents bad artifacts from being created; consume-time validation ensures contract drift between creation and consumption is caught at the point of use.

## Routing Behavior

`/code` may suggest or stop-and-route to lower skills when required:

- route to `/planning` if execution shape, acceptance criteria, contract matrix, or required contract authority reference is missing
- route to `/planning` if the shared plan consumer gate rejects the plan artifact
- route to `/arch` if identity, ordering, dedupe, invalidation, source-of-truth, or contract packet semantics are unclear, stale, or absent
- suggest `/critique` and `/verify` as downstream proof steps

## TDD Fix Plan Protocol (TDD Phase)

For bug fixes specifically, follow this structured sequence:

1. **Describe** — State the exact symptom and expected behavior
2. **Reproduce** — Write a failing test that demonstrates the bug
3. **Diagnose** — Minimal investigation to identify root cause
4. **Implement** — Smallest change that makes the test pass
5. **Verify** — Run full test suite to catch regressions

## Regression Check (TEST Phase)

After any fix, before declaring tests pass:

1. **Search git history** for prior fixes to the same file: `git log --oneline -- {file}`
2. **If a previous fix exists for a similar symptom**: verify the new change doesn't revert the prior fix
3. **Flag**: `"REGRESSION CHECK: {file} was previously fixed in {commit}. New change at line {N} does not conflict with prior fix at line {M}."`

Skip only for new features (no prior fixes in the file's history).

## Execution Model Selection

Subagents are the baseline for ALL tasks. See `references/execution-model-selection.md` for full routing table and triggers.

| Scope | Model |
|-------|-------|
| Any task (baseline) | **Subagents** |
| > 5 files / > 2 modules | **Agent team** |
| > 8 files / high verification | **Hybrid** |

## Validation Rules

- **Plan handling is mandatory**: If `plan.md` exists, continue remaining tasks. If missing, create plan before TDD.
- **Execution model must be explicit**: state whether using subagents, team, or hybrid.
- **Task completion proof required**: RED fail + GREEN pass + REFACTOR pass + verifier PASS.
- **TDD compliance**: All code changes must have tests first.
- **Resume ledger required**: Per-run ledger with task state, evidence pointers, blockers.
- **TRACE mandatory**: No exemptions for any code changes (docs-only exempted).
- **Consumer contract precheck required**: Stateful or integration work must verify downstream consumers before implementation.
- **Producer/consumer trace proof required**: Handoff/artifact work must prove the produced output reaches the real consumer path.

### Prohibited Actions
- Skipping TDD workflow
- Proceeding without completing current phase
- Declaring done without explicit completion evidence
- Returning subagent output inline (must use Result Envelope)
- Running high-output tasks in parallel
- Inventing missing downstream contract details during implementation
- Overriding or weakening active `Contract Authority Packet` semantics without routing back to `/arch`
- Claiming success based only on producer-side output without tracing the consumer handshake

## Quality Gate

After `/code` completes (all phases done, tasks verified), automatically invoke quality checks:

```python
Agent(
  subagent_type="general-purpose",
  prompt=f"""Run quality gate on completed code:
1. /qr --refine-only: Check for omissions, plan validation, improvements
2. If /qr returns findings with severity HIGH or CRITICAL → present to user for decision
3. If /qr returns Sound/Concerning with only MEDIUM/LOW → proceed to /sqa
4. /sqa: Run 8-layer code quality pipeline on the implemented code
Output: /rns-formatted findings from both /qr and /sqa."""
)
```

## Success Criteria

- [ ] TSK session created and active
- [ ] All tasks in `plan.md` marked complete
- [ ] Tests pass
- [ ] Knowledge updated

## Reference Files Index

| File | Contents |
|------|----------|
| `references/ralph-loop-guide.md` | Ralph Loop auto-detection, manual overrides, decision tree |
| `references/code-quality-standards.md` | Naming, function design, anti-patterns, pre-edit safety |
| `references/pre-execution-checklist.md` | 5-question pre-build checklist |
| `references/core-plan-v1-integration.md` | Evidence tracking, checklist validation, task detection |
| `references/execution-model-selection.md` | Routing table, triggers, phase routing defaults |
| `references/continuous-mode-implementation.md` | Continuous mode detection, phase boundary behavior |
| `references/validation-rules.md` | Complete validation rules and prohibited actions |
| `references/subagent-output-routing.md` | Result Envelope spec, routing rules |
| `references/aid-integration.md` | AID codebase discovery during EXPLORE |
| `references/explore-modernization-detection.md` | Modernization detection workflow, Context7 integration |
| `references/plan-phase-details.md` | Phases 1-4: REQUIREMENTS, PRE-FLIGHT, EXPLORE, PLAN |
| `references/tdd-phase-details.md` | Phase 5: TDD cycle, dispatch rules, retry protocol |
| `references/test-phase-details.md` | Phase 6: Full test suite, coverage analysis |
| `references/audit-phase-details.md` | Phase 7: Static analysis, code quality review |
| `references/trace-phase-details.md` | Phase 8: TRACE protocol, ToT enhancement |
| `references/done-phase-details.md` | Phase 9: Pre-Done checklist, build verification, deployment |
| `references/tsr-calculation.md` | Task Success Rate metric and evidence ledger |
| `references/changelog.md` | Version history and release notes |

---

**Version:** 4.0.0 | Uses shared enforce layer (`enforce/`). Phase definitions identical to v3.0.