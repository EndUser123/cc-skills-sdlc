---
name: sqa
description: Unified SQA Orchestrator — 11-layer sequential quality analysis pipeline with contract-integrity and resume-integrity certification.
version: 2.1.0
status: stable
category: quality
triggers:
  - /sqa
suggest:
  - /qr
entry_type: skill
enforcement: strict
workflow_steps:
  - L0_CHECKLIST
  - L0_PREDICTIVE
  - L1_SYNTACTIC
  - L2_SEMANTIC
  - L3_STRUCTURAL
  - L4_REQUIREMENTS
  - L5_SECURITY
  - L6_PERFORMANCE
  - L7_OPERATIONAL
  - L8_E2E
  - META_SYNTHESIS
  - L9_CONTRACTS
---

# /sqa — Unified SQA Orchestrator

Execute a sequential quality analysis pipeline against a target codebase.

**Mandatory Protocol:** See `__lib/quality_layers.md` for the 11-layer model, health score formula, and two-sided enforcement principle.

## Usage

```bash
/sqa <target-path>               # Explicit target
/sqa                             # Auto-detect target via context
/sqa --layer=N                   # Run specific layer (0-9, META)
/sqa --focus <lens>              # risk|gaps|security|comprehensive
/sqa --halt-on <severity>        # HIGH(default)|CRITICAL|MEDIUM|NONE
/sqa --fix                       # Auto-fix safe L1/L2 issues
```

## Layers Summary

1. **L0 (Checklist & Predictive)**: Fast-fail config and adversarial specialist dispatch.
2. **L1-L3 (Static & Structural)**: Syntax, cross-file imports, circular deps, guards.
3. **L4-L6 (Security & Performance)**: Spec compliance, path traversal, bottlenecks.
4. **L7-L9 (Operational & Contracts)**: Hook audit, E2E workflow, CAP alignment.

## Certification Thresholds

| Health Score | Certification |
|--------------|---------------|
| ≥80 | **CERTIFIED** |
| 60-79 | **CONDITIONAL** |
| <60 | **REJECTED** |

See `__lib/quality_layers.md` for detailed findings accumulation and halt behavior.

---

**Note**: `/sqa` does detection; route concrete fixes to `/code` or `/refactor`.
