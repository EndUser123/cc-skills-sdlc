---
name: code
description: "Feature Development Mission Control. Adapts to context: --task-file → single-task TDD engine under /go; standalone → full 11-phase mission control with autonomous loop."
---
# /code — Feature Development Mission Control

## Purpose

Adaptive development engine that selects the right workflow based on invocation context:

| Context | Mode | Behavior |
|---------|------|----------|
| `--task-file` present | **Task Engine** | Single-task TDD under `/go`. No loop, no review, no planning. |
| No `--task-file` | **Mission Control** | Full 11-phase workflow with autonomous loop, phase gates, GoT/ToT. |

## Quick Start

```bash
# Task from /go (Task Engine mode)
/code --task-file "active-task_{RUN_ID}.json"

# Full feature development (Mission Control mode)
/code plan.md

# Single task, no loop
/code "Add user authentication" --no-loop

# Fast route (either mode)
/code "fix typo" --fast --no-checklist

# Stats mode
/code stats
```

---

## Mode 1: Task Engine (`--task-file` present)

Under `/go` as the outer delivery loop, `/code` is the inner implementation engine: **receive task → TDD → smoke-validate → produce result → done**.

`/go` owns all orchestration: worktree enforcement, task selection, loop control, simplify gating, 7-pass review, and PR artifact generation. `/code` runs ONE task to completion.

### Input Contract

```
/code --task-file "active-task_{RUN_ID}.json"
```

Task file is JSON with schema `go.selected-task.v1`:
- `task_id`, `title`, `objective`
- `task_type`: implementation, refactor, design, planning
- `scope_in`, `scope_out`, `forbidden_files`
- `acceptance_criteria`, `verification_hint`
- `candidate_routes`: hint for routing decision

If `--task-file` is not provided, falls back to direct argument or session context.

### Output Contract

Produces `task-result_{RUN_ID}.json`:

```json
{
  "schema_version": "go.task-result.v1",
  "go_run_id": "...",
  "task_id": "...",
  "route": "code",
  "status": "completed|blocked|failed",
  "tdd_phases": { "red": true, "green": true, "refactor": true },
  "smoke_validated": true,
  "verification_results": [...],
  "artifacts_produced": [...],
  "blocked_by": [...],
  "completed_at": "ISO8601"
}
```

### Task Engine Workflow

1. **Read task** — load `--task-file` or argument, parse objective and scope
2. **Pre-execution checklist** — verify intent clarity, context readiness
3. **Explore** — understand codebase relevant to task
4. **Design** — solution approach (minimal, no pre-mortem, no GoT)
5. **TDD RED** — write failing test for acceptance criteria
6. **TDD GREEN** — implement minimal code to pass test
7. **TDD REFACTOR** — clean up without changing behavior
8. **Smoke validation** — prove implementation works
9. **Done** — write `task-result_{RUN_ID}.json` and emit completion token

**No loop. No review. No planning inside.** If task is ambiguous, route back to `/planning` — don't guess.

### What /go delegates to /code

| Delegation | What /code does |
|-----------|----------------|
| Route: `implementation` | Run TDD RED → GREEN → REFACTOR |
| Route: `refactor` | Behavior-preserving cleanup via TDD |

### What /code does NOT do (belongs to /go)

- Worktree enforcement, task selection, loop control
- Simplify gating, 7-pass review, PR artifact generation
- GoT/ToT planning, multi-task plan parsing

---

## Mode 2: Mission Control (no `--task-file`)

Systematic workflow to transform an idea into a production-ready feature: **REQUIREMENTS → PRE-FLIGHT → EXPLORE → PLAN → CONTRACT PRECHECK → TDD → TEST → AUDIT → TRACE → PRODUCER/CONSUMER TRACE → DONE**.

### Key Flags (Mission Control only)

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

### Phase Gate Enforcement

The Stop hook enforces phase gates via the shared `enforce/` library. Missing hard gates cause exit 2 (blocking). Missing advisory gates cause exit 1 (warning). Cold start (no ledger yet) returns exit 0.

```
Ledger path: ~/.claude/.state/enforce/code/{TERMINAL_ID}/phase-ledger.json
Evidence: phase ledger entries written by PreToolUse + PostToolUse hooks
```

Hard gates (blocking): `consumer_contract_precheck`, `smoke_validation`, `full_test_suite`, `audit_quality_checks`
Advisory gates (warning): `producer_consumer_trace_verification`, `trace_manual_verification`

### Autonomous Loop Mode (Default)

Mission Control **runs in autonomous loop mode by default** for multi-task plans:
- Parses plan.md for tasks (checkbox format `- [ ] TASK-001`)
- For each incomplete task, runs full workflow
- Exits when all tasks complete or genuine blocker hit
- Ralph Loop auto-detection: implementation keywords enable it, research keywords disable it

### Continuous Execution Mode (Default)

Continuous mode is **ON by default**. `/code` runs through all phases without stopping:
- Phase boundaries are NOT stopping points
- Only stops for genuine blockers (ambiguous requirements, errors, missing info)
- Opt-out: `--interactive`, `--step-by-step`, `-i`

### Core Workflow Phases

| Phase | Goal | Key Tools |
|-------|------|-----------|
| **1. REQUIREMENTS** | Clarity Check | Restate requirements, identify gaps |
| **2. PRE-FLIGHT** | Context Validation | health check, checkpoint, dependency check |
| **3. EXPLORE** | Understand Codebase | subagent discovery, modernization detection |
| **4. PLAN** | Design Solution | pre-mortem, GoT enhancement, execution path verification |
| **5. CONTRACT PRECHECK** | Confirm consumers exist | Schema/field expectations, freshness, invalidation |
| **6. TDD** | RED → GREEN → REFACTOR | test-first implementation via subagents |
| **7. TEST** | Full Test Suite | pytest, integration tests, regression tests |
| **8. AUDIT** | Quality Checks | ruff, mypy, pylint, eslint, tsc, code-reviewer |
| **8.5. FIX VERIFICATION** | Confirm fixes + edge cases | per-fix verification, adversarial-failure-modes agent |
| **9. TRACE** | Verify Logic | manual code trace-through, ToT enhancement |
| **10. PRODUCER/CONSUMER TRACE** | Verify actual handoff path | Consumer handshake, field presence, boundary proof |
| **11. DONE** | Final Certification | build verification, done checklist, deployment guidance |

Workflow override with `--fast`: REQUIREMENTS → PLAN STATE → CONTRACT PRECHECK → TDD → TEST → AUDIT → TRACE → PRODUCER/CONSUMER TRACE → DONE

**TRACE is mandatory in all modes.** PRODUCER/CONSUMER TRACE is mandatory for stateful, resumable, hook, artifact, or integration work.

### Mission Control Workflow

0. **SEARCH FIRST** — Check existing context before starting
1. **REQUIREMENTS (Phase 1)** — Clarity check
2. **PRE-FLIGHT (Phase 2)** — Context validation
3. **EXPLORE (Phase 3)** — Subagent discovery → curated context
4. **PLAN (Phase 4)** — Design solution with pre-mortem
5. **CONTRACT PRECHECK (Phase 5)** — Verify downstream consumers
6. **TDD (Phase 6)** — RED → GREEN → REFACTOR loop
7. **TEST (Phase 7)** — Full test suite
8. **AUDIT (Phase 8)** — Quality checks (can run parallel with TEST)
8.5. **FIX VERIFICATION (Phase 8.5)** — Confirm fixes + edge case analysis
9. **TRACE (Phase 9)** — Manual code trace-through
10. **PRODUCER/CONSUMER TRACE (Phase 10)** — Verify handoff path end-to-end
11. **DONE (Phase 11)** — Final certification

### Consumer Contract Precheck (Between PLAN and TDD)

Before implementation begins, verify that every downstream consumer expected to use the new output actually exists and has explicit expectations.

If the work is contract-sensitive, load the latest `Contract Authority Packet` from `/design` first and treat it as authoritative for boundary semantics during implementation.

**Principle: Enforcement lives with the consumer, not the producer.**

### Routing Behavior

`/code` may suggest or stop-and-route to lower skills when required:

- route to `/planning` if execution shape, acceptance criteria, or contract matrix is missing
- route to `/design` if identity, ordering, dedupe, invalidation, or contract packet semantics are unclear
- suggest `/critique` and `/verify` as downstream proof steps

### TDD Fix Plan Protocol (TDD Phase)

For bug fixes specifically:

1. **Describe** — State the exact symptom and expected behavior
2. **Reproduce** — Write a failing test that demonstrates the bug
3. **Diagnose** — Minimal investigation to identify root cause
4. **Implement** — Smallest change that makes the test pass
5. **Verify** — Run full test suite to catch regressions

### Regression Check (TEST Phase)

After any fix, before declaring tests pass:

1. **Search git history** for prior fixes to the same file: `git log --oneline -- {file}`
2. **If a previous fix exists for a similar symptom**: verify the new change doesn't revert the prior fix
3. **Flag**: `"REGRESSION CHECK: {file} was previously fixed in {commit}. New change at line {N} does not conflict with prior fix at line {M}."`

### Execution Model Selection

| Scope | Model |
|-------|-------|
| Any task (baseline) | **Subagents** |
| > 5 files / > 2 modules | **Agent team** |
| > 8 files / high verification | **Hybrid** |

### Quality Gate

After `/code` completes all phases:

```python
Agent(
  subagent_type="general-purpose",
  prompt="""Run quality gate on completed code:
1. /qr --refine-only: Check for omissions, plan validation, improvements
2. If /qr returns findings with severity HIGH or CRITICAL → present to user for decision
3. If /qr returns Sound/Concerning with only MEDIUM/LOW → proceed to /sqa
4. /sqa: Run 8-layer code quality pipeline on the implemented code"""
)
```

---

## Shared Rules (Both Modes)

### Evidence-First Rule

Before claiming that code does not exist, that a file is unchanged, that an implementation is missing, or that a behavior is absent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures, not from assumption or not having looked.

### Pre-Execution Checklist

Before starting, answer 5 questions:
1. Do I understand what "done" looks like?
2. Do I know where the relevant code lives?
3. Is the scope clear and bounded?
4. Do I need `/search` or `/explore` first?
5. Are there existing tests that cover this area?

**Opt-out:** `--no-checklist` (for `--fast` or continued work).

### Validation Rules

- **Plan handling is mandatory**: If `plan.md` exists, continue remaining tasks. If missing, create plan before TDD.
- **Execution model must be explicit** (Mission Control): state whether using subagents, team, or hybrid.
- **Task completion proof required**: RED fail + GREEN pass + REFACTOR pass + verifier PASS.
- **TDD compliance**: All code changes must have tests first.
- **TRACE mandatory**: No exemptions for code changes (docs-only exempted).
- **Consumer contract precheck required**: Stateful or integration work must verify downstream consumers.

### Prohibited Actions

- Skipping TDD workflow
- Proceeding without completing current phase
- Declaring done without explicit completion evidence
- Returning subagent output inline (must use Result Envelope)
- Inventing missing downstream contract details during implementation
- Claiming success based only on producer-side output without tracing the consumer handshake

### Project Context

- **State dir**: `.claude/.artifacts/{TERMINAL_ID}/go/`
- **Solo-dev constraints apply** (CLAUDE.md)
- **TDD mandatory**: All code changes follow RED → GREEN → REFACTOR

### Key Flags (Both Modes)

| Flag | Effect |
|------|--------|
| `--fast` | Skip ceremony, minimum viable route |
| `--no-checklist` | Skip pre-execution checklist |
| `--task-file` | Path to task JSON from `/go` (activates Task Engine mode) |

### Success Criteria

- [ ] TSK session created and active
- [ ] All tasks in plan marked complete (Mission Control)
- [ ] Tests pass
- [ ] Knowledge updated
