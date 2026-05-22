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

1. **Preflight & Discovery**: Identify hotspots and parallel agent analysis.
2. **Analysis**: Deduplicate findings and verify P0/P1 defects via targeted reads.
3. **Planning**: Create a plan with tiny commits and migration shims.
4. **RED Phase**: Characterization tests MUST be created and verified FAILING.
5. **Execution**: AST-based refactoring (LibCST) with LSP validation.
6. **Closing**: Regression testing, simplification polish, and reporting metrics.

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
