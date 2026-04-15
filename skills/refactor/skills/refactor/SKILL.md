---
name: refactor
description: Multi-file refactoring with orchestration - discovers synergies and assigns tasks to agents.
version: 1.0.0
status: stable
category: refactoring
enforcement: advisory
workflow_steps:
  - DISCOVER
  - DEDUPLICATE
  - PRIORITIZE
  - CONSTITUTIONAL_FILTER
  - PLAN
  - RED_PHASE
  - ADVERSARIAL_REVIEW
  - REFACTOR
  - REGRESSION
  - CODE_SIMPLIFICATION
triggers:
  - /refactor
aliases:
  - /refactor

---

# /refactor - Multi-File Refactoring Orchestrator

## Purpose

Multi-file refactoring with orchestration -- discovers synergies across files, prioritizes findings, and executes TDD characterization tests before refactoring.

## Project Context

- **Solo-dev constraints apply** (CLAUDE.md)
- **No enterprise patterns**: Service extraction, factory patterns, complex abstractions auto-filtered
- **Constitutional filter required**: All recommendations pass SoloDevConstitutionalFilter
- **TDD mandatory**: Characterization tests before any changes
- **7-step workflow**: Discovery -> Prioritization -> Constitutional Filter -> RED Phase -> Output -> Refactor -> Regression
- **Parallel agents**: 3+ agents for bugs/logic, DRY/simplicity, conventions
- **Priority levels**: P0 (bugs/race), P1 (error handling), P2 (DRY), P3 (conventions)

For code quality standards, naming conventions, regex best practices, and pre-edit safety checks, see `references/code-quality-standards.md`.

## Your Workflow

**CRITICAL: When user invokes `/refactor continue`, execute ALL priority levels (P0->P1->P2->P3) without stopping.**

1. **DISCOVER** -- Before launching agents, use CDS/`Grep`/CKS/CHS to locate hotspots; targeted `Read`s on those files. Then launch 3+ parallel Task agents:
   - Agent 1: `adversarial-compliance` -- Bugs/Logic (race conditions, error handling, TOCTOU)
   - Agent 2: `adversarial-performance` -- DRY/Simplicity (duplication, extraction, concurrency)
   - Agent 3: `adversarial-quality` -- Conventions (type hints, patterns, maintainability)
   - **For Python**: Add `python-simplifier` (Agent 4)
   - **For Python async**: Run `` `ruff` + `/p` `` to detect existing async bugs before refactoring
2. **DEDUPLICATE** -- Merge findings where multiple agents flagged the same code location
3. **PRIORITIZE** -- P0: Bugs/Race -> P1: Error Handling -> P2: DRY -> P3: Conventions
4. **CONSTITUTIONAL FILTER** -- Apply SoloDevConstitutionalFilter (see `references/constitutional-compliance.md`)
   - **If `--dry-run`**: Continue to steps 4.5-4.6, then STOP
   - **If "continue" or no `--dry-run`**: Execute steps 5-9 for ALL priority levels
   4.5. **CREATE PLAN** -- `scripts/refactor_plan.py` (see `references/plan-and-review-libraries.md`)
   4.6. **ADVERSARIAL REVIEW** -- `scripts/plan_review.py` (see `references/plan-and-review-libraries.md`)
5. **RED PHASE** -- Create characterization tests, verify they FAIL (see `references/tdd-implementation.md`)
6. **ADVERSARIAL REVIEW** -- Stress-test characterization tests via `adversarial-review` (8 perspectives)
7. **REFACTOR** -- Apply changes (GREEN phase). Must use AST-based refactoring (see `references/ast-refactoring.md`)
8. **REGRESSION** -- Run full test suite, verify no new failures
9. **CODE SIMPLIFICATION** -- Polish via `pr-review-toolkit:code-simplifier`

**Stopping Conditions:**
- STOP only if: user says "stop", question requires user input, or all findings processed
- DO NOT STOP after completing one priority level. Continue: P0 -> P1 -> P2 -> P3

**Agent Enhancement Specs**: See `references/agent-enhancements.md` for complexity triage and import hygiene details.

## Validation Rules

- **Before recommending**: Apply SoloDevConstitutionalFilter check
- **Before refactoring**: Create characterization tests for current behavior
- **Before suggesting extraction**: Verify actual reuse benefit (not hypothetical)
- **Constitutional compliance**: Auto-filter prohibited patterns

### Prohibited Actions

- Recommending service extraction without proven need
- Adding abstraction layers for "flexibility" (YAGNI)
- Implementing factory patterns (enterprise bloat)
- Suggesting changes without reading actual code first
- Returning agent analysis inline instead of writing findings to disk with Result Envelope
- Running high-output discovery agents in parallel -- stagger them
- Reading entire files into agent prompts when only a section is relevant

For subagent output routing rules, see `references/subagent-routing.md`.

## Quick Start

```bash
/refactor src/features/lib/llm_providers/       # Refactor a directory
/refactor "**/*provider*.py"                     # With glob pattern
/refactor file1.py file2.py file3.py             # Specific files
/refactor src/ --dry-run                         # Analysis only
/refactor src/ --focus security                  # Tune agent focus
/refactor src/ --synergy-type extract            # Specific synergy type
```

## Smart Defaults

| Feature | Default | When Disabled |
|---------|---------|---------------|
| **Comprehensive focus** | All agents run | `--focus <lens>` |
| **Confidence filtering** | ON (80% threshold) | `--no-confidence-filter` |
| **Recent mode** | ON if git has changes | `--no-recent` |
| **Exploration** | ON for >20 files | `--no-explore` |
| **Multi-review** | ON (parallel) | `--no-multi-review` |

## Focus Lens

| Focus | Agent Tuning | Emphasizes |
|-------|-------------|-----------|
| **default** | All agents: full scope | Publication-ready refactoring |
| `--focus security` | Agent 1: race, injection, auth | Vulnerabilities first |
| `--focus complexity` | Agent 2: CC >= 10, nested logic | High-CC targets first |
| `--focus performance` | Agent 1: leaks, bottlenecks, N+1 | Performance issues first |
| `--focus architecture` | All: boundary violations, coupling | Structure and boundaries |
| `--focus test` | Agent 3: missing tests, coverage | Test coverage first |
| `--focus quality` | Agent 2 & 3: standards, conventions | Code quality and style |

## Options

| Option | Description |
|--------|-------------|
| `--focus <lens>` | Tune agent prompts (security, complexity, performance, architecture, test, quality) |
| `--agents N` | Override agent count (1-10) |
| `--synergy-type TYPE` | Filter by synergy type |
| `--min-confidence N` | Minimum confidence (default: 80) |
| `--max-effort LEVEL` | Filter by effort (low, medium, high) |
| `--include-aid` | Run /aid refactor on each file |
| `--dry-run` | Analysis only, no changes |
| `--no-confidence-filter` | Disable confidence filtering |
| `--no-recent` | Analyze all files |
| `--no-explore` | Disable exploration phase |
| `--no-multi-review` | Disable multi-agent review |

## Synergy Types

| Type | Description | Example |
|------|-------------|---------|
| `extract` | Extract common code to shared module | 3 files with similar validation |
| `merge` | Merge similar interfaces | 2 protocol classes can combine |
| `consolidate` | Consolidate scattered patterns | Config access across 5 files |
| `standardize` | Standardize inconsistent patterns | Error handling varies by file |
| `restructure` | Restructure to break cycles | Circular imports |
| `modernize` | Update outdated library usage | Deprecated APIs, old syntax |

**`modernize` Context7 Integration:**
When synergy-type=modernize (deprecated API updates), invoke `/context7` before recommending replacements. This ensures refactoring follows current library best practices, not outdated patterns.

**Query expansion pattern:**
- Bad: "replace deprecated requests"
- Good: "current best practice for replacing deprecated requests.Session() in Python with httpx async"
- Mode: `code_only` (familiar replacements); `full` (unfamiliar library)
- Pin version if specific version mentioned (e.g., `/requests/requests/v2.28.0`)

**Examples:**
| Deprecated | Query Expansion |
|------------|----------------|
| `requests` | "replace requests.Session() with httpx async client Python" |
| `pd.DataFrame.append` | "pandas DataFrame append deprecation replacement merge/concat" |
| `datetime.utcnow()` | "Python datetime timezone-aware replacement for utcnow()" |
| `mock.patch.object` | "unittest.mock patch.object vs patch for method replacement" |

## Evidence Collection

All TDD phases use `src.core.evidence_collector`. See `references/evidence-and-validation.md` for full details including sequential enforcement, dead code detection, and quality gate patterns.

Evidence stored in `P:\.evidence/` (subdirectories: `commands/`, `tests/`, `files/`, `state/`, `refactor/`).

## TDD Checkpoint

Characterization tests MUST be created and verified FAILING before any findings are presented. The RED phase happens AUTOMATICALLY -- not delegated to `/tdd`. See `references/tdd-implementation.md` for full enforcement flow, exemption detection, and phase implementation.

| Phase | Error Message | User Action |
|-------|--------------|-------------|
| **RED** | `{test_file} must FAIL before changes` | Write test capturing current behavior |
| **GREEN** | `{test_file} must PASS after changes` | Fix code or revert |
| **REGRESSION** | `REGRESSION failed: {N} new failures` | Fix regressions before completing |

## See Also

- `/aid` - Single-file refactoring analysis (see `references/aid-integration.md`)
- `/p` - Python 2025 standards compliance
- `/complexity` - Code complexity analysis
- `/tdd` - TDD workflow with evidence collection
- `/v` - Sequential validation pipeline

## Reference Files

| File | Contents |
|------|----------|
| `references/code-quality-standards.md` | DRY, naming, function design, regex, pre-edit safety |
| `references/tdd-implementation.md` | TDD enforcement flow, exemption detection, phase code |
| `references/constitutional-compliance.md` | Prohibited patterns, filter step, filter code |
| `references/ast-refactoring.md` | LibCST transformations, when to use AST |
| `references/evidence-and-validation.md` | Evidence collection, sequential enforcement, dead code, quality gate |
| `references/plan-and-review-libraries.md` | Plan creation, adversarial review, check catalog |
| `references/agent-enhancements.md` | Complexity triage, import hygiene |
| `references/subagent-routing.md` | Result envelope, routing rules, targeted reads |
| `references/aid-integration.md` | AID workflow, ROI analysis, when to use |
