---
name: design
description: "Adaptive architecture advisor with template-based variants. Auto-routes to appropriate template based on domain and complexity. Enforces audit-first with Gap Analysis Report, contract-sensitive work emits a Contract Authority Packet."
enforcement: advisory
workflow_steps:
  - id: audit-first
    description: "Run Audit-First Protocol from resources/audit-first.md. Produce Gap Analysis Report before proceeding."
  - id: classify-intent
    description: "Detect domain and complexity (fast/deep)"
  - id: claim-verification
    description: "MANDATORY evidence check via verify_claims.py"
  - id: template-routing
    description: "Load and execute template from ./resources/{template}.md"
  - id: contract-closure
    description: "For contract-sensitive work, emit a Contract Authority Packet using resources/contract-authority-packet.md"
  - id: critic-review
    description: "Narrow audit for safety contradictions and packet drift"
  - id: payload-validation
    description: "Save result and write verification flag"
---
# Architecture Advisor (Resource Router)

## Overview

This skill routes architecture queries to specialized templates based on domain and complexity.

**Mandatory Standards:** See `__lib/architectural_standards.md` for Constitutional Principles, Structured Authority (CAP/PHP), and Verification Gates.

## Templates

| Domain | Template | Trigger Keywords |
|--------|----------|------------------|
| CLI/POSIX | `cli` | cli, command line, terminal, shell, posix |
| Python | `python` | python, asyncio, type hint, pydantic, fastapi |
| Data Pipeline | `data-pipeline` | etl, pipeline, streaming, kafka, spark |
| ADR | `precedent` | adr, decision record, precedent |
| Testing Architecture | `testing` | mutation, test architecture, coverage strategy, test isolation, tdd design, mutation strategy |

## Execution Workflow

1. **Audit First (MANDATORY)**: Before routing to any template, run the Audit-First Protocol from `resources/audit-first.md`. Produce a Gap Analysis Report before proceeding.

2. **Classify Intent**: Detect domain and complexity (fast/deep).
3. **Claim Verification**: MANDATORY evidence check via `verify_claims.py`.

   > **Benchmark-Truth Guard:** Any claim about comparative system performance (e.g., "model X outperforms Y on domain Z", "approach A is faster than B") MUST cite a concrete artifact from `.data/ai-api/benchmarks/` or `domain-model-weights.json`. Claims sourced only from narrative memory (e.g., `model_competence_memory.md`) are **prohibited** as design grounds.

4. **Template Routing**: Load and execute template from `./resources/{template}.md`.
5. **Contract Closure**: For contract-sensitive work, emit a **Contract Authority Packet**.
6. **Critic Review**: Narrow audit for safety contradictions and packet drift.
7. **Payload Validation**: Save result and write verification flag.

   > **Testability Contract (implementation-bound designs):** If the design will be implemented as code, include a `testability_contract` section listing: (a) the critical-path behaviors that mutation testing must cover, (b) their target module paths, and (c) whether they qualify as `tier: critical` for `quality_gates.json`. Designs without this section cannot be handed off to `/go` or `/code`.


## ADR Phase Gates

When evaluating Architecture Decision Records or contract-sensitive designs, apply these gates:

### Gate 1: Scope Check
- Verify the ADR scope matches the actual change boundary
- Flag scope creep: decisions that affect systems beyond their stated boundary
- Confirm all affected systems are enumerated in the ADR

### Gate 2: ADR Consistency
- Cross-reference new ADR against existing ADRs for contradictions
- Verify status transitions: proposed → accepted → deprecated → superseded
- Ensure superseding ADRs explicitly reference the ADR they replace

### Gate 3: Verification
- Confirm the ADR includes measurable acceptance criteria
- Verify implementation evidence exists for "accepted" ADRs
- Check that reversal criteria are defined (when would we undo this decision?)

## Strategic Reasoning

- **Enumerate alternatives**: Before committing, list 2-3 different approaches with tradeoffs
- **State the winner and why**: Pick one option with explicit reasoning
- **Name the falsification condition**: What would make you change your mind?

See `__lib/architectural_standards.md` for implementation details.

---

**Version:** 5.7 | **Architecture:** Template-based router with GoT, Structured Authority, and ADR phase gates.
