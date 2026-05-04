---
name: arch
description: "Architecture review and ADR advisor. Focuses on structural extraction vs capability reuse and ADR closure consistency. Redirects to /design for template-based deep dives."
version: "5.3"
status: stable
enforcement: advisory
depends_on:
  - sdlc: ">=0.1.0"
category: architecture
triggers:
  - arch
  - architecture
  - architectural decision
  - adf
suggest:
  - /planning
workflow_steps:
  - preflight_checks
  - select_template
  - execute_template_analysis
  - adr_critic_review
---

# Architecture Advisor

## Overview

This skill provides architectural guidance and ADR closure auditing.

**Mandatory Standards:** See `__lib/architectural_standards.md` for Constitutional Principles, Structured Authority (CAP/PHP), and Verification Gates.

## Key Gates

### 1. Scope Check
Determine if a proposal adds new boundaries (ADF applies) or shares existing ones (capability reuse).

### 2. ADR Consistency
Enforce safety policies (no fail-open), router precision, and packet alignment.

### 3. Verification
MANDATORY claim verification and temporal flow traces before ADR closure.

## Strategic Reasoning

- **GoT (Graph-of-Thought)**: Alternatives analysis.
- **Strategic Questioning**: Blind-spot detection.

See `__lib/architectural_standards.md` for full protocol details.

---

**Note**: For domain-specific deep dives (CLI, Python, ETL), use `/design`.
