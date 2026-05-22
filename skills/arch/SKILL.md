---
name: arch
description: "Architecture review and ADR advisor. Focuses on structural extraction vs capability reuse and ADR closure consistency. Redirects to /design for template-based deep dives."
---
# Architecture Advisor

## Overview

This skill provides architectural guidance and ADR closure auditing.

**Mandatory Standards:** See `__lib/architectural_standards.md` for Constitutional Principles, Structured Authority (CAP/PHP), and Verification Gates.

## Phase Gates

Architecture work is divided into **generation phases** (analysis, design) and **validation phases** (gate checks). Each gate is a hard STOP — the gate evaluation must pass before proceeding to the next phase.

### Gate 1 — Scope Check

| Aspect | Detail |
|--------|--------|
| **Type** | Validation (gate check) |
| **Purpose** | Classify the proposal: does it add new boundaries (ADF applies) or share existing ones (capability reuse)? |
| **Output artifact** | Scope classification: `new_boundaries` or `capability_reuse` |
| **STOP condition** | Stop if scope cannot be classified. Do not proceed to design generation without a classified scope. |

**Gate evaluation before proceeding**: Confirm scope classification is documented.

### Gate 2 — ADR Consistency

| Aspect | Detail |
|--------|--------|
| **Type** | Validation (gate check) |
| **Purpose** | Enforce safety policies: no fail-open, router precision, packet alignment |
| **Output artifact** | ADR policy compliance checklist (checked or N/A per item) |
| **STOP condition** | Stop if any safety policy is violated or unverified. Do not proceed to verification without a clean ADR consistency check. |

**Gate evaluation before proceeding**: Confirm all applicable ADR safety policies are checked and satisfied.

### Gate 3 — Verification

| Aspect | Detail |
|--------|--------|
| **Type** | Validation (gate check) |
| **Purpose** | MANDATORY claim verification and temporal flow traces before ADR closure |
| **Output artifact** | Evidence log: each claim linked to tool-verified evidence; temporal flow trace documented |
| **STOP condition** | Stop if any claim lacks evidence or temporal flow is untraced. Do not close the ADR without verified claims. |

**Gate evaluation before proceeding**: Confirm all claims have tool-verified evidence and temporal flow is traced.

---

### Phase Separation Summary

```
Phase 1: Analysis & Design Generation
  └── Gate 1 (Scope Check) — STOP: scope classified
Phase 2: ADR Drafting & Consistency
  └── Gate 2 (ADR Consistency) — STOP: safety policies satisfied
Phase 3: Evidence Gathering & Verification
  └── Gate 3 (Verification) — STOP: claims verified, flow traced
Phase 4: ADR Closure
```

**Generation** (analysis, design) happens before each gate. **Validation** (gate evaluation) happens at each gate. The STOP condition is the gate's output — it must be satisfied before the next phase begins.

## Strategic Reasoning

- **GoT (Graph-of-Thought)**: Alternatives analysis.
- **Strategic Questioning**: Blind-spot detection.

See `__lib/architectural_standards.md` for full protocol details.

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious

---

**Note**: For domain-specific deep dives (CLI, Python, ETL), use `/design`.
