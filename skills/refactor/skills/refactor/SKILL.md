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

1. **DISCOVER** -- Before launching agents, use CDS/`Grep`/CKS/CHS to locate hotspots; targeted `Read`s on those files. Then launch 8 staggered Task agents (30s apart to avoid context flooding):
   - Agent 1: `adversarial-compliance` -- Bugs/Logic (race conditions, error handling, TOCTOU)
   - Agent 2: `adversarial-performance` -- DRY/Simplicity (duplication, extraction, concurrency)
   - Agent 3: `adversarial-performance` (tuned `--focus performance`) -- Leaks/bottlenecks/N+1/algorithmic improvements
   - Agent 4: `adversarial-quality` -- Conventions (type hints, patterns, maintainability)
   - Agent 5: `python-simplifier` -- Python 2025 standards, async patterns
   - Agent 6: `/ai-pi-zai-glm51` -- Architecture lens: cross-module coupling, abstraction gaps, boundary violations, shared state patterns. Each finding MUST be verified by reading the actual file before writing.
   - Agent 7: `/ai-pi-mm-m27` -- Testing lens: coverage gaps, missing test scenarios, edge cases not covered, brittle tests. Each finding MUST be verified by reading the actual file before writing.
   - Agent 8: `/ai-gemini` -- Deep insight lens: semantic bugs, idiom violations, improvement opportunities that static analysis misses. Each finding MUST be verified by reading the actual file before writing.
   - **modernize synergy** (default ON): Context7 lookups for deprecated patterns — runs automatically unless `--synergy-type` is explicitly set to a non-modernize value
   - **For Python async**: Run `ruff` + `/p` to detect existing async bugs before refactoring
   - **Agent output format**: Each agent MUST use the `Write` tool (not `Bash`) to write findings JSON. The orchestrator MUST substitute the actual path before launching agents:
     - Artifacts dir: `P:/.claude/.artifacts/` (NOT `.refactor/` subdirectory of target)
     - Output path: `{artifacts_dir}/{target}/refactor/findings-{agent-name}.json`
     - Example: `P:/.claude/.artifacts/yt-is/refactor/findings-adversarial-compliance.json`
     - Shell quoting in Bash commands causes 3-4 wasted turns per agent. Write tool avoids this entirely.
   - **Minimum finding quality**: Every finding MUST have a non-empty `description`, `file`, `line`, and `confidence` score. Findings with empty descriptions or confidence=0 indicate the agent failed to analyze the code — do not include them in deduplication.
   - **Verification in DISCOVER**: Each agent verifies every finding by reading the actual file at the reported line before including it. Confidence is raised to 95+ for verified findings. Confidence is left as-is (or lowered) for unverified findings. The agent must distinguish: confirmed code exists at (file, line) = VERIFIED; code structure matches description = VERIFIED; description-only inference = UNVERIFIED.
   - **Graceful degradation**: If any agent fails or times out, skip it and continue with remaining agents. All findings are merged in step 2 regardless of source.
   - **Findings reuse**: If `{artifacts}/{target}/refactor/findings-*.json` files exist from a prior `--dry-run`, skip DISCOVER and go directly to DEDUPLICATE unless `--rediscover` is specified.
2. **DEDUPLICATE** -- Run `scripts/deduplicate.py` to merge findings by file+line, assign canonical IDs (e.g., `COMP-001/DRY-003` for cross-agent duplicates), and annotate evidence tiers. Output goes to `{artifacts}/{target}/refactor/deduplicated.json`.
2.5. **EVIDENCE TIER** (optional checkpoint) -- Only run if findings lack `[VERIFIED]` annotations from DISCOVER agents, or if a prior run's findings are being reused. Targeted reads for unverified findings. Labels:
   - `[VERIFIED]` — Tier 1: confirmed via targeted read or test execution
   - `[UNVERIFIED]` — Tier 3: static analysis only, claim could not be confirmed
   - `[CONTESTED]` — Tier 4: user or agent flagged as overstated/stale
   - `[INFERRED]` — Tier 3: plausible mechanism but unconfirmed root cause
3. **PRIORITIZE** -- P0: Bugs/Race -> P1: Error Handling -> P2: DRY -> P3: Conventions
4. **CONSTITUTIONAL FILTER** -- Apply SoloDevConstitutionalFilter (see `references/constitutional-compliance.md`)
   - **If `--dry-run`**: Continue to steps 4.5-4.6, then STOP
   - **If "continue" or no `--dry-run`**: Execute steps 5-9 for ALL priority levels
   4.5. **CREATE PLAN** -- Call `create_refactor_plan(findings, target_path, session_id)` from `scripts/refactor_plan.py`. Also runnable as CLI for testing: `python scripts/refactor_plan.py <deduplicated.json> <target> <session> [--output-dir <dir>]`.
   4.6. **ADVERSARIAL REVIEW** -- Call `adversarial_review_plan(plan)` from `scripts/plan_review.py`. Also runnable as CLI for testing: `python scripts/plan_review.py <plan.json>`.
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
| **default** | All 8 agents + modernize | Publication-ready refactoring |
| `--focus security` | Agent 1: race, injection, auth | Vulnerabilities first |
| `--focus complexity` | Agent 2: CC >= 10, nested logic | High-CC targets first |
| `--focus performance` | Agent 3: leaks, bottlenecks, N+1 | Performance issues first |
| `--focus architecture` | All: boundary violations, coupling | Structure and boundaries |
| `--focus test` | Agent 4: missing tests, coverage | Test coverage first |
| `--focus quality` | Agent 4 & 5: standards, conventions | Code quality and style |

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
| `--rediscover` | Force re-discovery even if `.refactor/findings-*.json` exists |
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

Evidence stored in `P:/.claude/.artifacts/{terminal_id}/refactor/` (subdirectories: `commands/`, `tests/`, `files/`, `state/`, `refactor/`).

## TDD Checkpoint

Characterization tests MUST be created and verified FAILING before any findings are presented. The RED phase happens AUTOMATICALLY -- not delegated to `/tdd`. See `references/tdd-implementation.md` for full enforcement flow, exemption detection, and phase implementation.

| Phase | Error Message | User Action |
|-------|--------------|-------------|
| **RED** | `{test_file} must FAIL before changes` | Write test capturing current behavior |
| **GREEN** | `{test_file} must PASS after changes` | Fix code or revert |
| **REGRESSION** | `REGRESSION failed: {N} new failures` | Fix regressions before completing |

### TDD Exemptions

Not all findings require characterization tests. Skip RED phase when:

| Finding Type | TDD Required? | Rationale |
|-------------|---------------|-----------|
| **P0: Crash bugs** (missing import, AttributeError, NameError) | **NO** | The "behavior" is "it crashes." A test that asserts `crash == True` adds no value. Fix directly. |
| **P0: Data loss** (INSERT OR REPLACE destroying rows) | **YES** | Characterize what data is preserved vs lost before changing the SQL strategy. |
| **P1: Race conditions** (missing locks) | **NO** | Race conditions are probabilistic; characterization tests for them are unreliable. Add the lock. |
| **P2: DRY extraction** | **YES** | Must verify extracted helpers produce identical output to the original duplicated code. |
| **P2: Parameter reduction** | **YES** | Must verify all callers still pass correct arguments after signature change. |
| **P3: Dead code removal** | **NO** | If no callers exist (verified by Grep), removing it is safe without tests. |
| **P3: Naming/convention** | **NO** | Renaming doesn't change behavior. |

**Principle**: TDD protects against behavior change. If the fix changes broken behavior to correct behavior (crash → works), tests add ceremony without protection. If the fix changes working behavior to different working behavior (SQL strategy), tests prevent regression.

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
