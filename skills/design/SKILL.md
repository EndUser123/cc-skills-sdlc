---
name: design
description: "Adaptive architecture advisor with template-based variants. Auto-routes to appropriate template based on domain and complexity. Enhanced with Graph-of-Thought (GoT) for alternatives analysis and Hook Registration Consistency Checking."
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

## Execution Workflow

1. **Classify Intent**: Detect domain and complexity (fast/deep).
2. **Claim Verification**: MANDATORY evidence check via `verify_claims.py`.
3. **Template Routing**: Load and execute template from `./resources/{template}.md`.
4. **Contract Closure**: For contract-sensitive work, emit a **Contract Authority Packet**.
5. **Critic Review**: Narrow audit for safety contradictions and packet drift.
6. **Payload Validation**: Save result and write verification flag.

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

- **GoT (Graph-of-Thought)**: Analysis of architecture alternatives.
- **Strategic Questioning**: Internal blind-spot check.

See `__lib/architectural_standards.md` for implementation details.

---

**Version:** 5.7 | **Architecture:** Template-based router with GoT, Structured Authority, and ADR phase gates.
