---
name: refactor
description: This skill should be used when the user asks to "refactor this code", "clean up this module", "find duplication across files", "modernize this package", "improve code quality", "simplify this codebase", or invokes "/refactor". Provides multi-file refactoring orchestration with 8-agent discovery, TDD enforcement, and constitutional filtering.
version: 3.0.0
status: stable
category: refactoring
enforcement: advisory
workflow_steps:
  - PREFLIGHT
  - DISCOVER
  - DEDUPLICATE
  - CLASSIFY_DEBT
  - PRIORITIZE
  - CONSTITUTIONAL_FILTER
  - PLAN
  - RED_PHASE
  - CHECKPOINT_RED
  - ADVERSARIAL_REVIEW
  - REFACTOR
  - LSP_VALIDATE
  - CHECKPOINT_GREEN
  - REGRESSION
  - CODE_SIMPLIFICATION
  - DELETION_METRIC
triggers:
  - /refactor
aliases:
  - /refactor
hooks:
  PreToolUse:
    - matcher: "Edit|Write|Bash|Task"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/refactor/hooks/PreToolUse_refactor_gate.py\""
          timeout: 10
  PostToolUse:
    - matcher: "Bash|Task"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/refactor/hooks/PostToolUse_refactor_validator.py\""
          timeout: 10
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/refactor/hooks/PostToolUse_refactor_transition.py\""
          timeout: 10
  Stop:
    - hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/refactor/hooks/Stop_refactor_verifier.py\""
---

# /refactor - Multi-File Refactoring Orchestrator

## Hook Behavior

- **PreToolUse gate**: Blocks tools not allowed in current phase (e.g., REFACTOR tools blocked during PLANNING)
- **PostToolUse validator**: Checks for errors in command output, verifies artifacts created
- **PostToolUse transition**: Advances phase when completion criteria met, updates allowed tools
- **Stop agent**: Verifies all completion criteria before allowing STOP — the self-verification mechanism
- **State file**: `P:/.claude/hooks/state/refactor_{instance_id}.json`

## Purpose

Multi-file refactoring with orchestration -- discovers synergies across files, prioritizes findings, and executes TDD characterization tests before refactoring.

## Project Context

- **Solo-dev constraints apply** (CLAUDE.md)
- **No enterprise patterns**: Service extraction, factory patterns, complex abstractions auto-filtered
- **Constitutional filter required**: All recommendations pass SoloDevConstitutionalFilter
- **TDD mandatory**: Characterization tests before any changes
- **15-step workflow**: Discovery -> Deduplicate -> Classify Debt -> Prioritize -> Constitutional Filter -> Plan -> RED Phase -> Checkpoint -> Adversarial Review -> Refactor -> LSP Validate -> Checkpoint -> Regression -> Simplification -> Deletion Metric
- **Parallel agents**: 8 agents with structured 8-dimension analysis rubric
- **Priority levels**: P0 (bugs/race), P1 (error handling), P2 (DRY), P3 (conventions)
- **Debt types**: design debt, code debt, test debt, documentation debt
- **Rollback safety**: Git tag checkpoints after RED and GREEN phases

For code quality standards, naming conventions, regex best practices, and pre-edit safety checks, see `references/code-quality-standards.md`.

## Your Workflow

**CRITICAL: When user invokes `/refactor continue`, execute ALL priority levels (P0->P1->P2->P3) without stopping.**

## Phase 0: PREFLIGHT — Structural Migration Safety

Before DISCOVER, assess whether this refactor involves structural migration (path changes,
module moves, import rewrites). If so, establish safety rails BEFORE launching agents.

### PREFLIGHT Checklist
For import/path refactors, complete before DISCOVER:

1. **Detect migration type**: Is this a pure path-move (same API, new location) or a
   semantic change? Pure path-moves use shim layers; semantic changes need feature flags.
2. **Identify callers**: Use `Grep` to find all files importing from the target module(s).
   Report count and list of affected files.
3. **Create compatibility shim** (for path-moves): For each target module, create a
   re-export shim at the OLD path that imports from the NEW path:
   ```python
   # old/module.py — COMPATIBILITY SHIM (delete after full migration)
   from new.module import *
   __all__ = ["SymbolA", "SymbolB"]  # explicit public API
   ```
4. **Verify shim works**: Import from the old path in a test — must succeed before proceeding.
5. **Set boy scout rule**: From this point, all NEW code must use the NEW import path.
   Violations are flagged in ADVERSARIAL_REVIEW.
6. **Document rollback**: If anything goes wrong, rollback is: delete new module,
   restore old module from git. The shim is the rollback boundary.

### When PREFLIGHT applies
- Import path changes (e.g., TID252 relative→absolute imports)
- Module relocation (file moved to new directory)
- Package boundary changes
- **When PREFLIGHT does NOT apply**: Pure code quality refactors (naming, DRY, complexity) —
  skip to DISCOVER and proceed normally.

See `references/migration-safety.md` for the full playbook: shim patterns, boy scout rule,
feature flags for behavioral changes, static lint enforcement, and rollback playbook.

1. **DISCOVER** -- Before launching agents:
   - If `--scan` is set: Call `scan_complexity(all_python_files, min_cc=N)` from `scripts/complexity_scanner.py`. Results (type=`HIGH_CC`) are merged into findings before deduplication. Run as: `python scripts/complexity_scanner.py <files...> --min-cc N`.
   - Use CDS/`Grep`/CKS/CHS to locate hotspots; targeted `Read`s on those files. Then launch 8 staggered Task agents (30s apart to avoid context flooding). Each agent scores findings on the **8-dimension analysis rubric**. See `references/agent-configs.md` for full agent assignments, launch protocol, output paths, verification requirements, and findings reuse rules.
   - **8-dimension analysis rubric** (from NTCoding/lightweight-design-analysis): Each agent scores findings across 8 dimensions, weighting by its specialty:
     | Dimension | What it measures | Weighted high by |
     |-----------|-----------------|-----------------|
     | Naming | Clarity and consistency of identifiers | Agent 4 (quality) |
     | Object Calisthenics | SRP, no getters/setters, small objects | Agent 2 (DRY) |
     | Coupling/Cohesion | Module boundaries, dependency direction | Agent 6 (architecture) |
     | Immutability | Mutable state, side effects | Agent 1 (bugs) |
     | Domain Integrity | Business logic leaks, anemic models | Agent 6 (architecture) |
     | Type System | Type hints, generics, unions | Agent 4 (quality) |
     | Simplicity | CC, nesting, parameter count | Agent 5 (standards) |
     | Performance | Algorithmic complexity, resource usage | Agent 3 (performance) |
   - **modernize synergy** (default ON): Context7 lookups for deprecated patterns -- runs automatically unless `--synergy-type` is explicitly set to a non-modernize value. See `references/agent-configs.md` for Context7 query expansion patterns.
   - **For Python async**: Run `` `ruff` + `/p` `` to detect existing async bugs before refactoring
   - **Shim detection**: Also detect existing compatibility shims (re-export patterns) and files
     importing from OLD paths that should use NEW paths. These are `migration_debt` findings
     (see CLASSIFY_DEBT step).
2. **DEDUPLICATE** -- Run `scripts/deduplicate.py` to merge findings by file+line, assign canonical IDs (e.g., `COMP-001/DRY-003` for cross-agent duplicates), and annotate evidence tiers. Also detect **cross-file semantic similarity**: functions in different files with similar structure (parameter patterns, call graphs, naming) flagged as potential DRY candidates even when not text-identical. Output goes to `{artifacts_dir}/{target}/refactor/deduplicated.json`.
2.5. **EVIDENCE TIER** (optional checkpoint) -- Only run if findings lack `[VERIFIED]` annotations from DISCOVER agents, or if a prior run's findings are being reused. Targeted reads for unverified findings. Labels:
   - `[VERIFIED]` -- Tier 1: confirmed via targeted read or test execution
   - `[UNVERIFIED]` -- Tier 3: static analysis only, claim could not be confirmed
   - `[CONTESTED]` -- Tier 4: user or agent flagged as overstated/stale
   - `[INFERRED]` -- Tier 3: plausible mechanism but unconfirmed root cause
3. **CLASSIFY_DEBT** -- Label each finding with a debt type for targeted remediation:
   - `design_debt`: Architecture issues -- coupling, missing abstractions, boundary violations
   - `code_debt`: Implementation issues -- duplication, complexity, dead code, naming
   - `test_debt`: Missing or brittle tests, uncovered edge cases
   - `documentation_debt`: Stale docs, missing docstrings, misleading comments
   - `migration_debt`: Structural issues -- old import paths, stale re-exports, callers not
     migrated to new module paths (see `references/migration-safety.md`)
   - Use the **code smell classification tree** to map findings to refactoring techniques (see `references/refactoring-mechanics.md` for the full classification table and step-by-step procedures)
   ```bash
   python "P:/.claude/skills/refactor/hooks/ledger_append.py" CLASSIFY_DEBT
   ```
4. **PRIORITIZE** -- P0: Bugs/Race -> P1: Error Handling -> P2: DRY -> P3: Conventions
   ```bash
   python "P:/.claude/skills/refactor/hooks/ledger_append.py" PRIORITIZE
   ```
5. **CONSTITUTIONAL FILTER** -- Apply SoloDevConstitutionalFilter (see `references/constitutional-compliance.md`)
   - **If `--dry-run`**: Continue to step 6, then STOP
   - **If "continue" or no `--dry-run`**: Execute steps 7-15 for ALL priority levels
   ```bash
   python "P:/.claude/skills/refactor/hooks/ledger_append.py" CONSTITUTIONAL_FILTER
   ```
6. **PLAN** -- Call `create_refactor_plan(findings, target_path, session_id)` from `scripts/refactor_plan.py`. Also runnable as CLI for testing: `python scripts/refactor_plan.py <deduplicated.json> <target> <session> [--output-dir <dir>]`.
   - **Migration Strategy** (required for structural changes): If `migration_debt` findings exist, the plan MUST include a "Migration Strategy" section with:
     - Shim location (OLD path → NEW path mapping)
     - Boy scout rule: "All new code uses NEW path. If you touch OLD path, migrate it."
     - Migration scope: which files change per commit
     - Rollback: how to revert each phase
     - Cleanup trigger: when to remove shims (after all callers migrated + prod verification)
   - **Tiny commits breakdown**: Each finding must be broken into smallest-safe-change commits. Each commit must leave the codebase in a working state (tests pass). Plan must specify commit boundaries: `[commit N] description`.
   - **Out of Scope section**: Every plan MUST include an explicit "Out of Scope" section listing: changes considered but rejected (with reason), files touched but not refactored (with rationale), findings deprioritized to future passes. This prevents scope creep during execution.
   - **Adversarial review**: Call `adversarial_review_plan(plan)` from `scripts/plan_review.py`. Also runnable as CLI for testing: `python scripts/plan_review.py <plan.json>`.
7. **RED PHASE** -- Create characterization tests, verify they FAIL (see `references/tdd-implementation.md`)
8. **CHECKPOINT_RED** -- Git tag `refactor/red-{target}-{timestamp}` after RED phase. This creates a rollback point before any production code changes. If GREEN phase fails catastrophically, reset to this tag.
9. **ADVERSARIAL REVIEW** -- Stress-test characterization tests via `adversarial-review` (8 perspectives)
10. **REFACTOR** -- Apply changes (GREEN phase). Must use AST-based refactoring (see `references/ast-refactoring.md`)
11. **LSP_VALIDATE** -- After each file edit in REFACTOR phase, run LSP diagnostics (`textDocument/publishDiagnostics`) to catch type errors, undefined references, and import issues immediately. If diagnostics reveal errors: pause, fix, re-validate before proceeding to next file. This prevents cascading type errors across files.
12. **CHECKPOINT_GREEN** -- Git tag `refactor/green-{target}-{timestamp}` after GREEN phase passes tests. This marks the "known working" state. If regression phase reveals issues, reset here rather than re-running the full refactor.
13. **REGRESSION** -- Run full test suite, verify no new failures
14. **CODE SIMPLIFICATION** -- Polish via `pr-review-toolkit:code-simplifier`
    ```bash
    python "P:/.claude/skills/refactor/hooks/ledger_append.py" CODE_SIMPLIFICATION
    ```
15. **DELETION_METRIC + QUALITY SCORE** -- Calculate and report:
   - **Deletion metric**: `lines_removed - lines_added`. Positive = successful simplification. Track per-priority-level: P0 through P3 should each show net deletion or explain why addition was necessary (e.g., missing error handling). If net lines added > 0 across all priorities, flag for review.
   - **Quality score**: Rate the target code 0-10 across the 8 dimensions from DISCOVER, before and after refactoring. Report delta per dimension:
     ```
     | Dimension        | Before | After | Delta |
     |------------------|--------|-------|-------|
     | Naming           | 5      | 8     | +3    |
     | Object Calisthenics | 4   | 7     | +3    |
     | Coupling/Cohesion| 6      | 9     | +3    |
     ```
   - A dimension that doesn't improve means the refactoring didn't address it -- flag for the user.

**Completion Criteria:**
Each priority level has explicit "done" conditions. Do not advance to the next level until current level meets its criteria:

| Level | Done When |
|-------|-----------|
| **P0 (Bugs/Race)** | No crashes, no race conditions, all error paths produce a result (not silent failure) |
| **P1 (Error Handling)** | No bare `except`, all exceptions have actionable messages, no swallowed errors |
| **P2 (DRY)** | No code duplication >6 identical lines across files, no CC>10 functions, all extracted helpers verified identical to originals |
| **P3 (Conventions)** | Passes `ruff check`, type hints on all public APIs, no `# type: ignore` without justification |

**Stopping Conditions:**
- STOP only if: user says "stop", **a blocking decision only the user can make is required** (not a result presentation or a choice the skill can make), or all findings processed AND all completion criteria met
- DO NOT STOP after completing one priority level. Continue: P0 -> P1 -> P2 -> P3
- DO NOT STOP to present findings or ask "want to proceed?" — make a recommendation and execute unless the user explicitly says stop or a blocking decision is required

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
| `--scan` | Run radon cyclomatic complexity scan before agent discovery. Use `--min-cc` to set threshold (default 5). Output fed into deduplication pipeline. |
| `--min-cc N` | Minimum cyclomatic complexity to flag (default 5). Only relevant when `--scan` is set. |

## Synergy Types

| Type | Description | Example |
|------|-------------|---------|
| `extract` | Extract common code to shared module | 3 files with similar validation |
| `merge` | Merge similar interfaces | 2 protocol classes can combine |
| `consolidate` | Consolidate scattered patterns | Config access across 5 files |
| `standardize` | Standardize inconsistent patterns | Error handling varies by file |
| `restructure` | Restructure to break cycles | Circular imports |
| `modernize` | Update outdated library usage | Deprecated APIs, old syntax |

When synergy-type=modernize, invoke `/context7` before recommending replacements. See `references/agent-configs.md` for query expansion patterns and examples.

## Evidence Collection

Evidence stored in `P:/.claude/.artifacts/{terminal_id}/refactor/` (subdirectories: `commands/`, `tests/`, `files/`, `state/`, `refactor/`).

## TDD Checkpoint

Characterization tests MUST be created and verified FAILING before any findings are presented. The RED phase happens AUTOMATICALLY -- not delegated to `/tdd`. See `references/tdd-implementation.md` for full enforcement flow, exemption detection, and phase implementation.

| Phase | Error Message | User Action |
|-------|--------------|-------------|
| **RED** | `{test_file} must FAIL before changes` | Write test capturing current behavior |
| **GREEN** | `{test_file} must PASS after changes` | Fix code or revert |
| **REGRESSION** | `REGRESSION failed: {N} new failures` | Fix regressions before completing |

TDD exemptions apply -- not all findings require characterization tests. See `references/tdd-implementation.md` for the full exemption table and rationale.

## See Also

- `/aid` - Single-file refactoring analysis
- `/p` - Python 2025 standards compliance
- `/complexity` - Code complexity analysis
- `/tdd` - TDD workflow with evidence collection
- `/v` - Sequential validation pipeline

## Reference Files

| File | Contents |
|------|----------|
| `references/agent-configs.md` | 8-agent assignment table, launch protocol, output paths, verification rules, findings reuse, Context7 integration |
| `references/refactoring-mechanics.md` | Code smell classification table and step-by-step transformation procedures |
| `references/code-quality-standards.md` | Standards guiding refactoring decisions -- what to simplify, consolidate, or standardize |
| `references/tdd-implementation.md` | TDD enforcement flow, exemption detection, and phase implementation |
| `references/constitutional-compliance.md` | Solo-dev constitutional constraints filter for all refactoring recommendations |
| `references/ast-refactoring.md` | AST-based refactoring using LibCST transformations (required for all Python refactoring) |
| `references/evidence-and-validation.md` | Evidence collection, storage, sequential enforcement, and quality gates |
| `references/plan-and-review-libraries.md` | Plan creation (`refactor_plan.py`) and adversarial review (`plan_review.py`) libraries |
| `references/agent-enhancements.md` | Complexity triage (Agent 2) and import hygiene (Agent 3) enhancement specs |
| `references/subagent-routing.md` | Subagent result envelope and output routing rules |
| `references/aid-integration.md` | AI Distiller (AID) integration for enhanced refactoring analysis |
| `references/changelog.md` | Reference file changelog |

## Examples

| File | Scenario |
|------|----------|
| `examples/single-file-refactor.md` | Complete 15-step workflow for refactoring `base_provider.py` |
| `examples/dry-run-analysis.md` | Analysis-only mode with resume via `/refactor continue` |
