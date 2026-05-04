---
name: design
description: "Adaptive architecture advisor with template-based variants. Auto-routes to appropriate template based on domain and complexity. Enhanced with Graph-of-Thought (GoT) for alternatives analysis and Hook Registration Consistency Checking."
version: "5.6"
status: stable
enforcement: strict
depends_on:
  - sdlc: ">=0.1.0"
category: architecture
triggers:
  - design
  - architecture
  - architectural decision
  - adf
suggest:
  - /planning
follow_up_offer:
  - /ai-pcli
hooks:
  pre_response:
    - command: "python skills/design_v1.0/hooks/stop_if_unverified.py"
workflow_steps:
  - preflight_checks
  - explore_context
  - classify_intent
  - claim_verification
  - contract_sensitivity_classification
  - select_template
  - execute_template_analysis
  - contract_boundary_closure
  - emit_contract_authority_packet
  - adr_critic_review
  - payload_validation
  - generate_architecture_review
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

## Strategic Reasoning

- **GoT (Graph-of-Thought)**: Analysis of architecture alternatives.
- **Strategic Questioning**: Internal blind-spot check.

See `__lib/architectural_standards.md` for implementation details.

---

**Version:** 5.6 | **Architecture:** Template-based router with GoT and Structured Authority.
