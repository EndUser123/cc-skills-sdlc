---
name: refactor
description: Multi-file refactoring orchestration with agent discovery, TDD characterization, and constitutional filtering.
version: 3.1.0
status: stable
category: refactoring
enforcement: advisory
workflow_steps:
  - PREFLIGHT
  - DISCOVER
  - DEDUPLICATE
  - EVIDENCE_VERIFY
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

## Focus Lenses

- `security`: Race, injection, auth.
- `complexity`: High CC and nested logic.
- `performance`: Bottlenecks and N+1 patterns.
- `architecture`: Boundary violations and coupling.

---

**Note**: `/refactor` uses staggered Discovery agents (30s apart) to avoid context flooding.
