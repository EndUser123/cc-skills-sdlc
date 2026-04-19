---
name: prrp
description: LLM Production-Ready Code Review Prompt - comprehensive post-coding production-ready reviews
version: 1.0.0
status: stable
category: code-review
triggers:
  - /prrp
aliases:
  - /prrp

suggest:
  - /comply
  - /qa
  - /review
---

# Production-Ready Review Prompt (PRRP)

Comprehensive prompt for LLM-based post-coding production-ready reviews.

## Purpose

Comprehensive post-coding production-ready review system with constitutional compliance, security validation, and quality gates.

## Project Context

### Constitution/Constraints
- Enforces CSF NIP constitutional compliance
- Solo-developer optimized (no enterprise bloat)
- Evidence-based development (all claims must be supported)

### Technical Context
- Specification: `P:/__csf/src/csf/cli/nip/prrp.md`
- Modular architecture with stub references (~0.3k vs full 13.6k tokens)
- CKS integration for automatic coding standards discovery

### Architecture Alignment
- Integrates with `/comply` for standards validation
- Works alongside `/analyze` for unified analysis
- Quality gates: 0.9+ minimum score, 0.70+ confidence threshold

## Your Workflow

1. **Pre-Code Planning**: Architecture review, assumptions, threat modeling
2. **Code Review**: Standards, security, performance, maintainability checks
3. **Security Validation**: Critical/High/Medium/Low severity classification
4. **Post-Review Actions**: Recommendations, quick wins, reporting
5. **Generate Verdict**: Production-ready certification

### Review Phases
- **Phase 1**: Pre-Code Planning (Architecture, assumptions, threat modeling)
- **Phase 2**: Code Review (Standards, security, performance, maintainability)
- **Phase 3**: Post-Review Actions (Recommendations, quick wins, reporting)

## Validation Rules

### Core Principles
- **Evidence-Based Development**: All claims must be supported by concrete evidence
- **Simplicity Principle**: Use the simplest solution that provides required benefit
- **Value-Driven Complexity**: Complexity must deliver measurable value
- **ROI Requirement**: Development time must be justified by automation value
- **Solo Developer Optimization**: Solutions must be maintainable by solo developers

### Prohibited Actions
- Do not skip security validation
- Do not approve code without evidence-based claims
- Do not use enterprise patterns for solo-developer projects

## Quick Start

```bash
/prrp <code-to-review>
```

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Evidence-Based Development** | All claims must be supported by concrete evidence |
| **Simplicity Principle** | Use the simplest solution that provides required benefit |
| **Value-Driven Complexity** | Complexity must deliver measurable value |
| **ROI Requirement** | Development time must be justified by automation value |
| **Solo Developer Optimization** | Solutions must be maintainable by solo developers |

## Key Features

- **CKS Integration**: Automatic coding standards discovery and validation
- **Constitutional Compliance**: Full validation against CSF NIP principles
- **Security Validation**: Critical/High/Medium/Low severity classification
- **Proportional Security**: Right-sized for solo developers (no enterprise bloat)
- **Quality Gates**: 0.9+ minimum quality score, 0.70+ confidence threshold

## Review Phases

1. **Phase 1: Pre-Code Planning** - Architecture, assumptions, threat modeling
2. **Phase 2: Code Review** - Standards, security, performance, maintainability
3. **Phase 3: Post-Review Actions** - Recommendations, quick wins, reporting

## Implementation

- **Specification**: `P:/__csf/src/csf/cli/nip/prrp.md`
- **Architecture**: Modular (stub references main documentation)
- **Token Savings**: ~13.3k tokens per invocation (stub ~0.3k vs full 13.6k)

## Related Commands

- `/code-review-v2` - Enhanced code review with shared services
- `/cognitive-review` - Cognitive-Stack Framework component review
- `/comply` - Unified standards and constitutional validation
- `/analyze` - Unified analysis engine
