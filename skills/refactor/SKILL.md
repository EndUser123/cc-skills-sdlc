---
name: refactor
description: Multi-file refactoring orchestration with agent discovery, TDD characterization, and constitutional filtering.
---
# /refactor - Multi-File Refactoring Orchestrator

## Overview

Orchestrate complex, multi-file refactoring while maintaining safety and TDD discipline.

**Mandatory Standards:** See `__lib/refactoring_patterns.md` for the 16-step workflow, debt classification types, and the Solo-Dev constitutional filter.

**Evidence-first rule:** Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures, not from assumption or not having looked.

## Workflow Summary

1. **Preflight**: Scope the diff, identify changed files.
2. **Correctness Sweep**: Line-by-line bug scan BEFORE architecture analysis (see below).
3. **Architecture Discovery**: Parallel agent analysis for hotspots, redundancy, coupling.
4. **Synthesis**: Consolidate findings, calculate Health Score, deduplicate.
5. **Analysis**: Verify P0/P1 defects via targeted reads.
6. **Planning**: Create a plan with tiny commits and migration shims.
7. **RED Phase**: Characterization tests MUST be created and verified FAILING.
8. **Execution**: AST-based refactoring (LibCST) with LSP validation.
9. **Closing**: Regression testing, simplification polish, and reporting metrics.

## Correctness Sweep (Step 2)

**Mandatory.** Before looking at architecture, scan every changed line for correctness bugs. This is the step that catches what architecture-focused agents miss.

Launch one dedicated agent that reads every hunk in the diff and checks for these patterns:

| Correctness Pattern | What to check |
|---------------------|---------------|
| Inverted/wrong conditions | `if not x` where `if x` was intended; `==` vs `!=` |
| Null/undefined deref | Accessing `.field` on Optional without guard |
| Missing `await` | Async function called without await |
| Falsy-zero confusion | `if not count` when `count == 0` is valid |
| Wrong-variable copy-paste | Variable name from adjacent code used by mistake |
| Swallowed exceptions | `except Exception: pass` or bare `except: return 0` |
| Silent failure | `except: return 0` with no logging or stderr output |
| API escaping mismatches | `re.escape()` used where SQL LIKE escaping is needed |
| Expression-eval bugs | `x or True` / `x and False` / `dict.get(k) or default` — always truthy |
| Cross-file interface mismatch | Caller passes args callee no longer accepts; other callers use different escaping |
| Assumption assertions | `table_a.rowid == table_b.id` without verification |
| Hook output pollution | `sys.stderr.write()` on success/error paths in hooks — corrupts hook JSON output |
| Cross-component escaping | Backend escaping differs from router/other caller escaping; query reaches backend untransformed |
| Platform shebang | `#!/usr/bin/env` on Windows (non-functional); missing shebang on Unix |
| Platform-specific paths | Backslash handling, `$VAR` expansion differences, junction vs symlink |

**Extended correctness patterns** (from /simplify and /code-review):
- Redundant state: state that duplicates existing state, cached values derivable
- Parameter sprawl: adding params instead of generalizing
- Stringly-typed code: raw strings where constants or enums exist
- Nested conditionals: ternary chains or nested if/else 3+ levels deep
- Unnecessary comments: narrating what the code does instead of why

**Agent output:** Each finding as `{file, line, summary, failure_scenario}`. Maximum 10 findings, ranked by severity.

**Why this step exists:** Architecture agents optimize for patterns and structure. They miss subtle per-line bugs like an extra backslash in a JSON string or `re.escape()` not covering LIKE wildcards. The correctness sweep catches what architecture analysis cannot.

**Reference:** See `references/code-review-integration.md` for the full design rationale.

## Quick Start

```bash
/refactor <path>                 # Refactor a directory or file
/refactor src/ --dry-run         # Analysis and findings only
/refactor src/ --focus security  # Tune agent focus
/refactor continue               # Run all priority levels without stopping
```

## Target Inference (When No Path Provided)

When invoked without a path argument (e.g., just `/refactor`):

1. **Check recently modified files** — Use `git diff --name-only` to find files changed in the current worktree. If a coherent package or module dominates, use that directory as the target.
2. **Check conversation context** — If the session has been working on a specific module, that module is the target scope.
3. **If exactly one candidate** — Use it automatically, but state the inferred target before proceeding.
4. **If multiple candidates OR no clear context** — Ask user to specify. Do not guess silently.

**Precedent:** Follows the same pattern as `/planning` context-aware behavior.

## Focus Lenses

- `security`: Race, injection, auth.
- `complexity`: High CC and nested logic.
- `performance`: Bottlenecks and N+1 patterns.
- `architecture`: Boundary violations and coupling.

---

**Note**: `/refactor` uses staggered Discovery agents (30s apart) to avoid context flooding.

## Where to Look

- `docs/planning/pytest-repair-strategy.md` — design rationale for the pytest repair tiers (C1 classify → C2 design → C3 repair) and the safety rails for cache drift, allowlist gaps, and cross-worktree path resolution.
- `refactor-workspace/refactor-enhancements-report.md` — scope inventory of the v1.1.0 enhancement series (synthesis module, 12-agent refactor-discovery configuration, GTO direct-import refactor, RNS migration, characterization tests). Includes "Pending" callouts for items not yet wired.
- `CHANGELOG.md` — version-by-version changelog with the same scope, in the Keep-a-Changelog format.
- `references/agent-configs.md` — the 12-agent configuration (12 dedicated `refactor-discovery-*` specialists) that backs the refactor dispatch.
- `scripts/synthesize_findings.py` — synthesis module that produces the Health Score. Imported by `refactor_plan.py` and surfaced in every plan's `overview.synthesis` block.
- `scripts/refactor_plan.py` — main orchestrator. `create_refactor_plan()` now returns a plan with `overview.synthesis = {module_available, health_score, severity_counts}`.

## Artifacts

Plans are written to `refactor-workspace/refactor_plan_<YYYYMMDD>_<HHMMSS>.json`. Each plan file is a single-source handoff for downstream `/executor` or `/code` skills.
