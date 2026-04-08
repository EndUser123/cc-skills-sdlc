---
name: code
version: 2.29.0
description: AI-assisted feature development workflow (Idea to PR) with mandatory consumer handshake proof and Contract Authority Packet consumption for contract-sensitive work.
category: development
enforcement: advisory
domain: development
depends_on:
  - sdlc: ">=0.1.0"
triggers:
  - 'code feature'
  - 'build feature'
  - 'new feature'
  - 'implement feature'
  - 'start development'
argument-hint: <feature_description|stats> [--fast|--full] [--no-loop] [--no-ralph-loop] [--ralph-enable] [--ralph-disable] [--no-got] [--no-tot] [--no-checklist]
context: main
user-invocable: True
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
          command: "python \"$CLAUDE_PROJECT_DIR\"/.claude/skills/code/hooks/PreToolUse_plan_consumer_gate.py"
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
suggest:
  - /search (integrated - pre-implementation context discovery)
  - /qa
  - /test
  - /comply
  - /`ruff` (automatic) + `/p`
---


# /code -- Feature Development Mission Control

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
| `--fast` | Skip ceremony, minimum viable route |
| `--full` | Full ceremony route |
| `--no-loop` | Single-task mode (no autonomous iteration) |
| `--ralph-enable` | Force enable Ralph Loop |
| `--ralph-disable` | Force disable Ralph Loop |
| `--no-got` | Disable Graph-of-Thought planning |
| `--no-tot` | Disable Tree-of-Thought tracing |
| `--no-checklist` | Skip pre-execution checklist |
| `--interactive`, `-i` | Step-by-step mode (pause at phase boundaries) |

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

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **TDD mandatory**: All code changes follow RED -> GREEN -> REFACTOR
- **Evidence-based**: Verify each phase before proceeding
- **Isolation**: Git worktree is available via `/git worktree` but not prompted during build

### Technical Context
- **Core flow**: REQUIREMENTS -> PRE-FLIGHT -> EXPLORE -> PLAN -> CONTRACT PRECHECK -> TDD -> TEST -> AUDIT -> TRACE -> PRODUCER/CONSUMER TRACE -> DONE
- **Flow spec**: flows/feature.md
- **Scripts**: `scripts/*.py` for runtime fingerprinting, ledger state, and completion validation
- **References**: `references/*.md` for checklists, troubleshooting, and runbook examples
- **Success criteria**: plan.md complete, tests pass, knowledge updated

### Code Quality Standards
See `references/code-quality-standards.md` for full details including naming conventions, function design, anti-patterns, and pre-edit safety checks.

## Pre-Execution Checklist

**Before starting any development work**, answer 5 questions. See `references/pre-execution-checklist.md` for details.

**Opt-out:** `--no-checklist` flag (for trivial changes or continued work).

## Core Workflow Phases

| Phase | Goal | Key Tools | Reference |
|-------|------|-----------|-----------|
| **1. REQUIREMENTS** | Clarity Check | Restate requirements, identify gaps | `references/plan-phase-details.md` |
| **2. PRE-FLIGHT** | Context Validation | health check, checkpoint, dependency check | `references/plan-phase-details.md` |
| **3. EXPLORE** | Understand Codebase | `/search`, subagent discovery, modernization detection | `references/explore-modernization-detection.md` |
| **4. PLAN** | Design Solution | Manual planning, pre-mortem, GoT enhancement, execution path verification | `references/plan-phase-details.md` |
| **5. CONTRACT PRECHECK** | Confirm consumers exist | Schema/field expectations, freshness, invalidation, failure behavior | `references/plan-phase-details.md` |
| **6. TDD** | RED -> GREEN -> REFACTOR | test-first implementation via subagents | `references/tdd-phase-details.md` |
| **7. TEST** | Full Test Suite | pytest, integration tests, regression tests | `references/test-phase-details.md` |
| **8. AUDIT** | Quality Checks | ruff, mypy, pylint, eslint, tsc, code-reviewer | `references/audit-phase-details.md` |
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
9. **TRACE (Phase 9)** -- Manual code trace-through
10. **PRODUCER/CONSUMER TRACE (Phase 10)** -- Verify actual handoff path end-to-end
11. **DONE (Phase 11)** -- Final certification

Workflow override:
- `--fast`: REQUIREMENTS -> PLAN STATE -> CONTRACT PRECHECK -> TDD -> TEST -> AUDIT -> TRACE -> PRODUCER/CONSUMER TRACE -> DONE
- **TRACE is mandatory in all modes** -- no exemptions for speed
- **PRODUCER/CONSUMER TRACE is mandatory** for stateful, resumable, hook, artifact, or integration work

## Local Maximum Trap Detection (PLAN Phase)

**Value Assessment Principle:** Before adding guidance, patterns, or new capabilities — identify the UNIQUE contribution. If existing skills cover ~70%+ with equivalent rigor, the marginal value is low. Greenfield proposals without a search pass are prohibited.

Before committing to an implementation approach, check:

| Warning Sign | What It Means |
|-------------|---------------|
| First solution is the only solution considered | Didn't explore alternatives |
| Explaining why alternatives won't work before trying them | Defending, not evaluating |
| Implementation details discussed before approaches compared | Skipped exploration |

**Required check during PLAN phase:** Generate at least 2 implementation approaches before coding. If the first approach scores significantly higher, proceed. If approaches are close, document why the chosen one wins.

## Implementation-Risk Prompts

Before writing or editing code, `/code` should run a short internal implementation-risk check:

- What requirement or contract am I about to guess instead of read?
- What existing behavior am I assuming without verifying in code or tests?
- What file, API, schema, or hook boundary am I changing implicitly?
- What part of this change could break because a plan, ADR, or test target is stale?
- What should fail closed here if my assumption is wrong?
- What is the smallest implementation that satisfies the current contract?
- What regression would recur unless I add or update a test now?
- Am I about to encode policy in code that belongs in a validator, hook, or skill contract?
- What part of the requested behavior is still ambiguous enough that `/planning` or `/arch` should have closed it first?
- What would make this patch locally correct but systemically wrong?

These are internal self-check prompts. They are not default user-facing questions and should only surface to the user when `/code` is genuinely blocked and cannot proceed safely without clarification.

## Smoke Validation

Before claiming a change is safe to continue, `/code` should run the cheapest real execution that could quickly falsify the implementation.

Required smoke validation for:
- hooks, routers, and activation logic
- CLI entrypoints or command handlers
- stateful, resumable, multi-terminal, or stale-data-sensitive changes
- contract-sensitive producer/consumer boundaries
- integration changes spanning multiple files or subsystems

The smoke step should prove at least one of:
- the edited path still imports/loads
- the primary workflow still executes end-to-end at a minimal level
- the changed boundary still produces and consumes the expected artifact/fields

Do not substitute prose confidence for smoke validation when the change touches runtime wiring.

## Critique-Agent Triggers

`/code` should use a critique/review agent when the implementation is high-risk, cross-boundary, or likely to be locally correct but systemically wrong.

Escalate to a critique agent when:
- the change touches hooks, routers, resume/restore flow, or state schema
- the change crosses producer/consumer boundaries or contract packets
- the implementation relies on subtle fallback/default behavior
- the change is integration-heavy enough that a second perspective can find blind spots faster than more local edits

The critique agent should focus on hidden regressions, contract drift, and edge cases the main implementation path may have normalized away.

## Consumer Contract Precheck (Between PLAN and TDD)

Before implementation begins, verify that every downstream consumer expected to use the new output actually exists and has explicit expectations.

If the work is contract-sensitive, load the latest `Contract Authority Packet` from `/arch` first and treat it as authoritative for boundary semantics during implementation.

**Principle: Enforcement lives with the consumer, not the producer.**

`/code` (and `/tdd`) must refuse to consume a plan artifact that fails its contract, rather than relying on a global hook to catch all bad writes. Write-time validation (what `/planning` does) prevents bad artifacts from being created; consume-time validation (what `/code` does here) ensures that contract drift between creation and consumption is caught at the point of use. Both sides are required — one without the other leaves a gap.

For each relevant boundary, name:

- producer
- consumer
- fields or outputs produced
- fields required by the consumer
- freshness authority
- invalidation trigger
- failure behavior if fields are missing or stale
- active `Contract Authority Packet` reference when applicable

Verify that implementation intent matches the packet on required fields, freshness authority, transcript-vs-artifact precedence, and failure behavior. Do not proceed by inferring or rewriting those semantics locally.

If the implementation depends on "the consumer will probably read this field," stop and return to `/arch` or `/planning`.

Before `/code` consumes a plan artifact, it must validate the plan through the shared consumer gate:

```bash
python - <<'PY'
from contract_primitives import validate_plan_for_execution
result = validate_plan_for_execution("plan.md", consumer="/code", required_phase=1)
print(result)
PY
```

`/code` is not allowed to rely on frontmatter prose alone. It may consume either:
- a fully `implementation-ready` plan, or
- a validated phased-ready plan whose `phase_ready_through` threshold covers the execution phase

Without explicit phase context, the local consumer gate defaults to Phase 1. If later-phase execution is intended, pass that phase explicitly into the consumer gate before editing code. If the consumer gate says the plan is blocked, stale, or below the required readiness threshold, route back to `/planning` or `/arch` instead of continuing.

## Routing Behavior

`/code` may suggest or stop-and-route to lower skills when required:

- route to `/planning` if execution shape, acceptance criteria, contract matrix, or required contract authority reference is missing
- route to `/planning` if the shared plan consumer gate rejects the plan artifact
- route to `/arch` if identity, ordering, dedupe, invalidation, source-of-truth, or contract packet semantics are unclear, stale, or absent
- suggest `/critique` and `/verify` as downstream proof steps

`/code` must not invent architecture or plan decisions that belong to those skills.

## TDD Fix Plan Protocol (TDD Phase)

For bug fixes specifically, follow this structured sequence:

1. **Describe** — State the exact symptom and expected behavior
2. **Reproduce** — Write a failing test that demonstrates the bug
3. **Diagnose** — Minimal investigation to identify root cause
4. **Implement** — Smallest change that makes the test pass
5. **Verify** — Run full test suite to catch regressions

This is a subset of the full TDD cycle, optimized for fixes where the scope is bounded.

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

See `references/validation-rules.md` for complete list. Key rules:

- **Plan handling is mandatory**: If `plan.md` exists, continue remaining tasks. If missing, create plan before TDD.
- **Execution model must be explicit**: state whether using subagents, team, or hybrid.
- **Task completion proof required**: RED fail + GREEN pass + REFACTOR pass + verifier PASS.
- **TDD compliance**: All code changes must have tests first.
- **Resume ledger required**: Per-run ledger with task state, evidence pointers, blockers.
- **TRACE mandatory**: No exemptions for any code changes (docs-only exempted).
- **Consumer contract precheck required**: Stateful or integration work must verify downstream consumers before implementation.
- **Contract Authority Packet required when applicable**: Contract-sensitive work must consume the active packet rather than infer boundary semantics from prose.
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

## Subagent Output Routing

See `references/subagent-output-routing.md` for Result Envelope spec and routing rules.

## AID Integration (v2.26.0)

Enhanced codebase discovery via AI Distiller during EXPLORE phase. See `references/aid-integration.md` for details.

## Core Plan v1 Integration

Three enhancements working together: evidence tracking, pre-execution checklist validation, and Ralph Loop auto-detection. See `references/core-plan-v1-integration.md` for full details.

## TDD Resume Context (ADR-20260324)

Auto-detect and restore TDD context after compaction or session resume. See `references/tdd-phase-details.md` for TDD Resume Context section.

## Shared Task List Discipline

Use the Claude shared task list as the coordination spine when using agent team/hybrid:
- Scoped task list ID per active build stream
- Every task includes: id, status, owner, dependencies, touched module/file scope
- On pause/stop, persist status updates and blockers before replying

## Allocation Directive

**When `/code` is invoked:**
1. Read Feature Flow (`flows/feature.md`)
2. Choose route (`--fast`, `--full`, or auto)
3. Choose execution model from thresholds
4. Set scoped task list context (team/hybrid only)
5. Resolve plan state: If the user references a named output from the conversation (e.g. "implement SuspicionDetector from /arch output"), use the conversation context as the plan source. If `/code` is bare (no args), use conversation context to determine the last active task and resume it. Only ask the user to clarify if the context is genuinely ambiguous.
6. Initialize/refresh resume ledger (full route)
7. REQUIREMENTS -> continue execution

## Till-Done Execution Rule

This is a till-done workflow, not a todo list. Each `/code` invocation runs to full completion or hits a genuine blocker:
- Never stop after completing a subset of tasks
- Never stop after completing a phase
- After last task passes verification, run completion sweep
- Run full test suite after all tasks complete

If stopping is genuinely required, output blocker report with: BLOCKED reason, current task, evidence, one direct question, numbered options.

## Producer/Consumer Trace Gate

Before claiming `/code` complete on stateful, resumable, hook, artifact, or integration work:

1. Trace the produced output into the real consumer path.
2. Verify the consumer reads the expected fields or artifact state.
3. Verify missing or stale required fields fail in the intended way.
4. Verify runtime behavior matches the active `Contract Authority Packet` on required fields, freshness authority, transcript-vs-artifact precedence, and failure behavior when a packet applies.
5. Record the proof in the completion evidence.

Producer-side proof alone is insufficient. "The file was written" does not prove "the consumer successfully resumed, restored, routed, or executed from it."

## Final Done Contract

Before claiming `/code` complete:
1. Report `Tasks complete: X/Y`
2. Report `Skipped tasks: <list>` with user approval reference
3. Report verification summary
4. Run done-claim validators
5. Include confidence calibration (residual risks)
6. Generate session summary

See `references/done-phase-details.md` for full Pre-Done Checklist and Build Verification details.

## Success Criteria

- [ ] TSK session created and active
- [ ] All tasks in `plan.md` marked complete
- [ ] Tests pass
- [ ] Knowledge updated

## Failure Modes

| Failure | Recovery |
|---------|----------|
| Test regression | `/checkpoint-restore` |
| Spec drift | Return to Phase 1 |
| Context overload | Use `context: fork` |

## Next Steps

**ONLY show when ALL 9 phases complete AND NOT in continuous mode:**

1. [Ready to Ship] `/qa` (Certify feature)
2. [Needs Refactoring] `/evolve` (Clean up debt)

## TSR Calculation

See `references/tsr-calculation.md` for Task Success Rate metric, evidence ledger structure, and pass/fail criteria.

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

**Version:** 2.29.0 (2026-04-02) | See `references/changelog.md` for version history.
