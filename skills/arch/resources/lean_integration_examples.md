# Lean System Design Integration Examples

This document shows how /arch templates integrate the **Lean System Design** framework from `shared_frameworks.md`.

## Template Integration Pattern

All /arch templates reference the Lean System Design framework during design/planning stages:

```markdown
## Stage 0.5: Framework Application

**Frameworks applied:**
- Lean System Design (value optimization, consolidation, dependency pruning)
- [Domain-specific frameworks]
- [Other shared frameworks]

**Core goals alignment:**
- Cross-file/codebase-level understanding and validation
- Consolidation and simplification of skills/tools
- Runtime safety and correctness
```

## Example: deep.md Integration

In `deep.md`, after Stage 0.3 (Codebase-Aware Analysis), add:

```markdown
## Stage 0.5: Lean Design Principles

**Frameworks applied:**
- Lean System Design (value optimization, consolidation, contract-first)
- Systems Thinking (ripple effects)
- First Principles Thinking (assumption challenge)

**Value optimization check:**
For each proposed subsystem, explicitly state how it advances core goals:
- [ ] Cross-file understanding
- [ ] Consolidation
- [ ] Runtime safety

**Duplicate mechanism check:**
Compare proposed components against existing hooks/policies:
- [ ] PreToolUse hooks: [list relevant hooks]
- [ ] PostToolUse hooks: [list relevant hooks]
- [ ] Stop hooks: [list relevant hooks]
- [ ] Existing skills: [list overlapping skills]

If overlap detected → Design merged system, remove weaker one

**Dependency audit:**
- MUST (required for v1): [list]
- SHOULD (nice-to-have): [list]
- MAY (optional enhancements): [list]
```

## Example: fast.md Integration

In `fast.md`, during Stage 5 (Decision), add:

```markdown
### Lean Design Filter

Before presenting recommendation:

**1. Core Plan (v1)**
- Tasks: [5-10 critical tasks]
- Dependencies: MUST-level only
- Value: ~80% of user's goal

**2. Extended Plan (optional)**
- Tasks: [additional ceremony/features]
- Dependencies: SHOULD/MAY-level
- Trigger: [when to execute]

**3. Consolidation check**
- Duplicate mechanisms identified: [list]
- Merge strategy: [how to consolidate]

**4. Environment fit**
- Solo dev constraints respected: [yes/no]
- Stdlib-only for hooks: [yes/no]
- Windows 11 compatible: [yes/no]
```

## Example: DEFAULT Path Output

When generating architecture decisions, include Lean Design sections:

```markdown
## Architecture Decision: [Title]

### Core Contracts
[Schema/API definitions before tasks]

### Core Plan (v1 - 80% value)
1. [Task 1]
2. [Task 2]
...
5. [Task 5]

**Dependencies:** MUST-level only
**Value:** Advances [cross-file understanding / consolidation / runtime safety]

### Extended Plan (optional)
[Additional tasks marked as "only if needed"]

### Consolidation & Gaps
**Duplicate mechanisms removed:** [list]
**Missing contracts filled:** [list]

### Environment & Preference Fit
**Solo dev:** Compatible
**Stdlib-only:** Yes (MUST deps only)
**Windows 11:** Yes
**Consolidation:** Merges [existing components]

### Confidence
**Score:** [X]%
**Evidence:** [sources]
**Assumptions:** [list]
```

## Template Chaining Considerations

When using template chaining (e.g., `template=python+data-pipeline`):

```markdown
## Stage 0.5: Framework Application

**Frameworks applied:**
- Lean System Design (value optimization, consolidation)
- Python-specific frameworks (asyncio, type hints)
- Data-pipeline frameworks (ETL/ELT patterns, streaming)

**Merge strategy:**
- Primary: Python template
- Secondary: Data-pipeline domain concerns
- Lean principles applied to BOTH domains
```

## Quick Reference for Template Authors

When adding Lean System Design to templates:

**Minimum required:**
1. Reference framework in Stage 0.5
2. Core goals alignment check
3. Dependency audit (MUST/SHOULD/MAY)
4. Consolidation check (duplicates)
5. Core vs Extended plan separation

**Optional enhancements:**
1. Contract-first schema definitions
2. Environment fit checklist
3. Value justification per component
4. Adversarial self-review (weakest assumption)

**Skip conditions:**
- User specifies `--no-lean` flag
- Query is purely theoretical/hypothetical
- Fast path for trivial decisions (<3 alternatives)

## Integration Checklist

For each template (fast, deep, cli, python, data-pipeline, precedent):

- [ ] Added Stage 0.5: Framework Application
- [ ] Reference shared_frameworks.md Lean System Design section
- [ ] Include core goals alignment check
- [ ] Add dependency audit (MUST/SHOULD/MAY)
- [ ] Add consolidation check (duplicate mechanisms)
- [ ] Separate Core Plan from Extended Plan
- [ ] Include Environment & Preference Fit section
- [ ] Document skip conditions (if any)

## Verification

To verify integration is working:

```bash
# Test lean principles are applied
/arch "design caching system" template=deep

# Expected output should include:
# - Core goals alignment
# - Dependency audit (MUST/SHOULD/MAY)
# - Consolidation check
# - Core vs Extended plan
# - Environment fit
```

---

**Document status:** Active integration guide
**Last updated:** 2026-03-10
**Version:** 1.0
