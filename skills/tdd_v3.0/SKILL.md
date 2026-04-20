---
name: tdd
version: 3.0.0
description: Test-Driven Development with PARALLEL subagent delegation + Core Plan v1 evidence tracking. RED-GREEN-REFACTOR cycle with timestamped artifacts and 7-day cleanup.
status: stable
depends_on:
  - sdlc: ">=0.1.0"
enforcement: advisory
category: execution
activation_triggers: ['implement', 'refactor', 'CC.*[2-9][0-9]', 'extract.*method', 'reduce.*complexity', 'high complexity', 'simplify.*function', 'new feature', 'add.*function', 'add.*test', 'write.*test', 'update.*test', 'create.*test', 'unit.*test', 'regression.*test', 'typeddict', 'interface', 'contract', 'add.*type', 'type.*hint', 'fix', 'bug', 'broken', 'error', 'crash']
triggers:
  - '/tdd'
aliases:
  - '/tdd'
workflow_steps:
  - write_failing_tests
  - confirm_tests_fail
  - implement_minimal_code
  - confirm_tests_pass
  - behavior_smoke_proof
  - refactor_code
  - confirm_tests_still_pass
suggest: []
changelog:
  - version: 2.26.0 (2026-04-06)
    changes:
      - "MIGRATION: TDD hooks migrated from skill subprocess to in-process native hooks"
      - "PERFORMANCE: Eliminated subprocess overhead on every tool execution"
      - "RELIABILITY: Fixed __lib import path resolution for hook_base module"
      - "ARCHITECTURE: Hooks now registered in settings.json instead of SKILL.md"
  - version: 2.25.0 (2026-03-15)
    changes:
      - "NEW: Core Plan v1 evidence tracking integration"
      - "NEW: Timestamped evidence artifacts in .evidence/ directory"
      - "NEW: 7-day automatic cleanup policy for evidence artifacts"
      - "NEW: Integration with /code pre-execution checklist and task detection"
      - "DOCUMENTATION: Updated evidence collection documentation with Core Plan v1 API"
---
# TDD - Test-Driven Development with PARALLEL Delegation

**MANDATORY WORKFLOW:** Write tests BEFORE changing code.

## Purpose

Test-Driven Development for new features AND refactoring. Write tests first, then code. Delegates to subagents (tdd-test-writer, tdd-implementer, tdd-refactorer) in PARALLEL for independent tasks.

## Constraints

- **Solo-dev constraints apply** (CLAUDE.md)
- **TDD mandatory**: All code changes follow RED -> GREEN -> REFACTOR
- **Tests first**: Write tests BEFORE changing code, never after
- **PARALLEL delegation**: Use multiple subagents simultaneously for independent tasks
- **5-phase process**: DISCOVER -> RED -> GREEN -> VERIFY -> REGRESSION -> REFACTOR
- **Baseline capture**: Save test results before changes for comparison
- **TypedDict contracts**: Use for cross-module data structures

## Architecture Alignment

Integrates with /test (coverage analysis), /verify (run tests), /qa (certification). Part of testing and quality ecosystem.

When `/tdd` is consuming an existing plan rather than discovering tests from scratch, it should use the same shared plan-consumer validation as `/code` before trusting the plan:

```bash
python - <<'PY'
from contract_primitives import validate_plan_for_execution
result = validate_plan_for_execution(
    "plan.md",
    consumer="/tdd",
    require_implementation_ready=False,
    required_phase=1,
)
print(result)
PY
```

`/tdd` may proceed from a phased-ready plan only if the validated `phase_ready_through` threshold actually covers the TDD phase being executed. Without explicit phase context, the local consumer gate defaults to Phase 1. Otherwise route back to `/planning`.

## Search Integration (Before TDD)

Before writing tests, search for existing patterns:

```bash
/search "{feature} test patterns" --backend chs,cks,code
/search "{language} testing framework" --backend chs,cks,docs
/search "{component} tests" --backend code,cks
```

Search accelerates TDD by finding existing patterns, frameworks, fixtures, and anti-patterns.

---

## Workflow Overview

```
0. DISCOVER   -> Understand code (read first, THEN run tests)
1. RED        -> Write failing test (PARALLEL tdd-test-writer)
2. GREEN      -> Implement minimal code (PARALLEL tdd-implementer)
3. VERIFY     -> Run ACTUAL command (not dry-run, not mocks)
4. REGRESSION -> Run related tests (automatic)
5. REFACTOR   -> Clean up while tests pass (PARALLEL tdd-refactorer)
```

See `references/parallel-delegation.md` for phase-by-phase subagent delegation patterns and examples.

See `references/discovery-and-regression.md` for DISCOVER phase details and REGRESSION targeting.

See `references/verify-phase.md` for VERIFY phase requirements, plan discovery, and evidence format.

See `references/evidence-collection.md` for Core Plan v1 evidence tracking API and per-phase collection.

See `references/workflow-variants.md` for bug-fixing workflow and completion format.

---

## Quick Reference (Parallel-First)

| Step | New Feature | Refactoring | Agent Pattern |
|------|-------------|-------------|--------------|
| 0. DISCOVER | Read code, then baseline | Read code, then baseline | `general-purpose` x N (parallel) + You |
| 1. RED | Write test x N (one per case) | Write test x N (one per file) | `tdd-test-writer` x PARALLEL |
| 2. GREEN | Implement x N (one per file) | Extract/simplify x N (one per file) | `tdd-implementer`/`tdd-refactorer` x PARALLEL |
| 3. VERIFY | Run command | Run command | You |
| 4. REGRESSION | Auto-runs | Auto-runs x N (if failures) | Automatic |
| 5. REFACTOR | Clean up x N (one per cleanup) | Clean up x N (one per cleanup) | `tdd-refactorer` x PARALLEL |

**Rule:** If tasks are independent, launch ALL in parallel. No upper limit.

---

## Validation Rules

- **Before code changes**: Capture baseline test results
- **Before GREEN phase**: Confirm test fails (RED phase confirmed)
- **Before claiming verified**: Run actual command with real data
- **Before complete**: Compare regression results to baseline
- **TDD compliance**: Tests must be written BEFORE code changes

### Prohibited Actions

- Changing code without tests
- Skipping verification (dry-run doesn't count)
- Changing logic while refactoring (mixes refactoring with changes)
- Writing tests after code changes
- Claiming verified without actual command execution
- Using deprecated testing syntax without verification via /context7

**Testing Framework Syntax Verification (RED Phase):**
Before writing framework-specific tests, invoke `/context7` to verify current syntax. This is mandatory for pytest, Django, vitest, jest, and any rapidly-evolving framework.

**When:** Every RED phase involving framework-specific test code (pytest fixtures, Django test client, React Testing Library, etc.)

**Query expansion pattern:**
- Bad: "pytest fixtures"
- Good: "pytest fixtures syntax with examples for dependency injection in unit tests"
- Mode: `code_only` (familiar patterns); `full` (first contact with framework)

**Examples:**
| Framework | Query Expansion |
|-----------|----------------|
| pytest | "pytest fixtures dependency injection with function scope examples" |
| Django | "Django test client assert methods for status codes and JSON responses" |
| vitest | "vitest mocking modules with vi.mock and vi.fn() examples" |
| jest | "jest.spyOn and mock functions for async API testing" |

---

## Test-Truth Prompts

Before locking in tests or claiming coverage, `/tdd` should run a short internal test-truth check:

- What contract or behavior is this test actually proving?
- Could this test pass while the real bug still exists?
- Am I testing the mechanism, the user-visible behavior, or both?
- What stale-data, multi-terminal, or interruption case would make this test incomplete?
- What assumption about ordering, identity, or invalidation is this test silently making?
- What behavior must fail, not just succeed?
- What would a naive implementation do that this test should reject?
- Am I writing a test for a workaround instead of the real contract?
- What evidence would show this test matrix contradicts the stated design?
- If the implementation changed but the contract stayed the same, would this test still be valid?

These are internal self-check prompts. They are not default user-facing questions and should only surface to the user when `/tdd` is genuinely blocked and cannot proceed safely without clarification.

## Behavior Smoke Proof

`/tdd` should run a minimal real execution that proves the tests are attached to actual behavior, not just mocks or overly narrow assertions.

Required for:
- hooks, routers, or activation logic
- stateful or resumable workflows
- contract-sensitive producer/consumer boundaries
- bug fixes where the original failure mode involved integration or runtime state

The smoke proof should answer:
- does the targeted behavior execute in the real environment?
- would a naive or partially mocked implementation still be rejected?
- is there a minimal end-to-end proof that the contract under test is real?

`/tdd` may keep this lightweight, but it must not skip it on high-risk behavioral changes.

## Critique-Agent Triggers

`/tdd` should use a critique/review agent when test design is likely to miss the real contract or bless a workaround.

Escalate to a critique agent when:
- a new test matrix is defining a boundary contract or state-machine behavior
- ordering, invalidation, stale-data, or resume semantics are part of the bug or feature
- the tests are passing, but there is still a credible path where the real defect survives
- a second perspective is needed to challenge whether the tests prove the intended behavior instead of the chosen mechanism

The critique agent should focus on false confidence, missing failure paths, and tests that would pass while the real bug remains.

---

## When This Skill Activates

Activates for: "implement X", "refactor X", "add feature X", "reduce complexity of X", "X has CC N", "fix X bug", "X broken/error/crash"

Does NOT trigger for: Documentation changes, configuration updates, reading/analyzing code.

---

## Intent Detection

| Pattern | Intent | Workflow Variant |
|---------|--------|------------------|
| "fix X", "bug in X", "X broken/error/crash" | Bug fix | Bug-fixing workflow (see references/workflow-variants.md) |
| "implement X", "add feature X", "new feature" | New feature | Full RED->GREEN->REFACTOR |
| "refactor X", "simplify X", "reduce complexity" | Refactoring | Refactoring workflow |

---

## Subagent Capabilities

| Subagent | Best For | Context Required |
|----------|----------|------------------|
| `tdd-test-writer` | RED phase - failing tests | Spec, desired behavior |
| `tdd-implementer` | GREEN phase - minimal code | Failing test, clear spec |
| `tdd-refactorer` | REFACTOR - cleanup while tests pass | Working code + tests |
| `code-reviewer` | Bug detection, security, quality | Code only (fresh eyes) |
| `code-critic` | Root cause analysis | Code + error description |
| `code-explorer` | Architecture, dependency mapping | Module path or pattern |
| `general-purpose` | Multi-step, research | Clear task description |

---

## Anti-Patterns

| Don't | Why |
|-------|-----|
| Change code without tests | Can't detect behavior changes |
| Skip verification | May have broken something |
| Change logic while refactoring | Mixing refactoring with changes |
| Write tests after code | Defeats TDD philosophy |
| Run subagents sequentially when parallel is possible | Wastes time and token efficiency |

---

## File Locations

- **Gap loader utility:** `P:/.claude/skills/tdd/gap_loader.py`
- **Test gap files:** `{project_root}/.claude/state/test_gaps/*.json`
  - Terminal-scoped: `{terminal_id}_gaps_READY.json`
  - Global fallback: `_READY.json`
  - Consumed: `{terminal_id}_gaps_CONSUMED.json`
- **Refactoring safety tests:** `tests/test_refactor_safety.py`
- **Feature tests:** `tests/test_[feature].py`
- **Integration tests:** `tests/test_[module].py`
- **Test Results:** `P:/.claude/tdd-guard/data/test.json`
- **TDD State:** `P:/.claude/tdd-state.json`

---

## Configuration

**Enable TDD enforcement:** `TDD_ENABLED=1`
**Bypass TDD (not recommended):** `TDD_BYPASS=1`

---

## References

**Reference files in `references/`:**

| File | Contents |
|------|----------|
| `parallel-delegation.md` | Phase-by-phase subagent delegation patterns, strategies, and end-to-end examples |
| `discovery-and-regression.md` | DISCOVER phase details, /t integration, gap loading, REGRESSION test targeting |
| `evidence-collection.md` | Core Plan v1 evidence tracking API, per-phase collection, 7-day cleanup policy |
| `verify-phase.md` | VERIFY phase requirements, plan discovery, evidence format, prohibited responses |
| `workflow-variants.md` | Bug-fixing workflow, closure protocol, completion/summary format |

**External:**
- [TDD Guard](https://github.com/nizos/tdd-guard) - Automated TDD enforcement
- [Alex Oprea's TDD Workflow](https://alexop.dev/posts/custom-tdd-workflow-claude-code-vue/) - Multi-agent TDD approach
