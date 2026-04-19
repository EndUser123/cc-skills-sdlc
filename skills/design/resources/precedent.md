# ADR Documentation Analysis

## Template Metadata
- **Target Complexity:** Any
- **Target Domain:** Architectural Decision Records
- **Expected Output Size:** ~20 KB
- **Execution Instructions:** Read steps, execute in order, do not restate.

## Common Glossary
- **ARCHITECTURE_REVIEW:** Query asks to review/evaluate proposed design or architecture
- **IMPROVE_SYSTEM:** Query asks to optimize/harden existing subsystem
- **DEFAULT:** General architecture decision without improvement intent
- **CKS.db:** Constitutional Knowledge System

## Execution Instructions

**Do not:** Restate these instructions, summarize, or paraphrase.

**Do:**
1. Execute steps sequentially
2. Follow decision tree exactly
3. ADR-specific analysis (documenting decisions, alternatives)
4. Stop at each decision point and evaluate

---

## Stage 0: Detect Intent Type

From the user query, identify:

**Is this an ARCHITECTURE_REVIEW request?**
- Keywords: review, evaluate, assess, analyze, audit, validate, critique
- Context: design, architecture, integration, proposal, theoretical
- **If YES:** Proceed to "Stage 0: ARCHITECTURE_REVIEW Path" (below)

**Is this an IMPROVE_SYSTEM request?**
- Keywords: improve, optimize, harden, stabilize, enhance, strengthen
- Subsystem: memory, CKS, hooks, research, retro, lesson, ingestion, validation
- **If YES:** This template may not apply - use appropriate domain template

**Otherwise (DEFAULT):**
- Proceed to "ADR Documentation Analysis" below

---

## Stage 0.1: Constitutional Compliance Check (MANDATORY)

**Before proceeding to any decision path, evaluate:**

### Multi-Terminal Isolation & Stale Data Immunity

**For ALL architecture decisions, evaluate:**

1. **Identify shared mutable state**: Does this design create or modify files, databases, or in-memory state that could be accessed by multiple terminals?

2. **Assess concurrency safety**: Can multiple Claude Code terminals execute this pattern simultaneously without:
   - Data races (corrupted state)
   - Stale reads (terminal A sees outdated state)
   - Lost updates (write from terminal A overwrites terminal B silently)

3. **Check propagation mechanisms**: If state changes, how do other terminals discover the change?
   - File-based state: Requires polling or file system events
   - Database-based state: Requires query or notification mechanism
   - In-memory state: Cannot propagate across terminals (violates isolation)

4. **Document edge cases**: What happens when:
   - Terminal A writes while terminal B reads?
   - Two terminals write simultaneously?
   - A terminal crashes mid-operation?
   - Network filesystem has delays?

**Red flags that REQUIRE explicit mitigation:**
- ❌ Shared JSON/YAML files without atomic write + locking
- ❌ SQLite databases without WAL mode or proper transaction isolation
- ❌ In-memory caches without per-terminal isolation
- ❌ File locking assumptions (flock doesn't work across all platforms)
- ❌ Assumptions that only one terminal will run at a time

**Required output:**
- If design is multi-terminal safe: Document the isolation mechanism
- If design is single-terminal only: Explicitly state limitation + migration path
- Always document edge cases and failure modes

---

## Stage 0: ARCHITECTURE_REVIEW Path

**Purpose**: Evaluate proposed architecture/design WITHOUT recommending alternatives or suggesting implementation first.

### Scope Constraints

**CRITICAL: Architecture reviews are valid EVEN for theoretical/unimplemented designs.**

**DO:**
- Identify gaps and risks in the proposed design
- Evaluate against best practices (from web research in Stage 0.7)
- Assess feasibility and complexity
- **Verify absence claims before stating them** (see verification_tiers.md Absence Claim Protocol)
- Flag missing components or edge cases
- Cite evidence (files, lines, docs) for each finding

**DO NOT:**
- Suggest skipping or delaying the work
- Recommend installation before review
- Propose alternative architectures (that's DEFAULT path)
- Gatekeep based on implementation status
- Declare design "premature" due to lack of installation
- Tell user to "implement first, then review"

### Key Principle

> **Architecture reviews exist PRECISELY to evaluate designs BEFORE implementation.**
> Theoretical designs deserve rigorous analysis precisely to prevent costly mistakes.
> If the design were already implemented, we wouldn't need a review—we'd test it instead.

### Review Stages

1. **Scope Verification** — Confirm understanding of what's being reviewed
2. **Gap Analysis** — Identify missing elements from proposed design
3. **Risk Assessment** — What could fail, based on research + design analysis
4. **Evidence Table** — Each finding MUST be backed by:
   - Specific file:line from codebase (if applicable)
   - Specific line from design document/proposal
   - External source (web research, standards, best practices)

### Output Format

## Architecture Review: [Title]

### Scope
[What was reviewed - 1-2 sentences]

### Design Summary
[Brief description of what the design proposes - 2-4 sentences]

### Findings

| ID | Severity | Finding | Evidence | Impact |
|-----|-----------|----------|-----------|---------|
| ARCH-001 | HIGH | [description] | [file:line or source] | [consequence] |
| ARCH-002 | MEDIUM | [description] | [file:line or source] | [consequence] |
| ARCH-003 | LOW | [description] | [file:line or source] | [consequence] |

### Risk Summary
- Technical: [summary]
- Operational: [summary]
- Integration: [summary]

### Conclusion
[Overall assessment - proceed with caution / needs clarification / looks viable with noted gaps]

---
**Confidence:** [X]%

**Evidence basis:**
- Design doc: [source]
- Web research: [count] sources
- Codebase analysis: [files reviewed]

**Key assumptions:**
1. [assumption]
2. [assumption]

## ADR Documentation Format

**Enhanced ADR template based on industry best practices:**

```markdown
# ADR-XXXX: [Descriptive Short Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-YYYY | Rejected
**Decomposed by:** [ADR-YYYY if superseding/replacing another decision]
**Decision Maker:** [Team/Individual who made this decision]

## Context and Problem Statement

[Describe the context and problem statement - 2-5 sentences]
- What situation prompted this decision?
- What problem does this decision solve?
- What are the driving forces or constraints?
- What are the success criteria?

## Decision

[One clear statement of what was decided]
- Technology choice, architectural pattern, or approach
- Scope of the decision (what's included/excluded)
- Any key constraints or assumptions

## Rationale

[Why this is the right decision - evidence-based]
- What patterns or principles apply?
- What research/evidence supports this decision?
- What are the key benefits of this approach?
- How does this align with project goals and constraints?

**Evidence sources:**
- [Cite web research, standards, best practices]
- [Reference existing codebase patterns]
- [Industry standards or documentation]

## Alternatives Considered

| Alternative | Description | Pros | Cons | Why Rejected |
|-------------|-------------|------|------|--------------|
| **Option A (CHOSEN)** | [Description] | [Benefit 1, Benefit 2] | [Cost 1, Cost 2] | N/A |
| Option B | [Description] | [Benefit 1, Benefit 2] | [Cost 1, Cost 2] | [Reason for rejection] |
| Option C | [Description] | [Benefit 1, Benefit 2] | [Cost 1, Cost 2] | [Reason for rejection] |

**Differentiation axes:** [How options differed - technology, coupling, complexity, risk]

## Consequences

### Positive
- [Benefit 1]: [Description]
- [Benefit 2]: [Description]

### Negative
- [Cost/Risk 1]: [Description and mitigation]
- [Cost/Risk 2]: [Description and mitigation]

### Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk description] | High/Medium/Low | High/Medium/Low | [Mitigation strategy] |

## Implementation

### Implementation Plan
- **Phase 1:** [Description] | Effort: [X hours/days]
- **Phase 2:** [Description] | Effort: [X hours/days]
- **Phase 3:** [Description] | Effort: [X hours/days]

### Rollback Strategy
[How to undo this decision if needed]
- Rollback steps
- Data migration requirements
- Feature flags or toggles

### Success Criteria
- [Criterion 1]: [How to measure]
- [Criterion 2]: [How to measure]

## Related Decisions
- **ADR-XXXX:** [Title] ([relationship - implements, supersedes, contradicts, complements])
- **ADR-YYYY:** [Title] ([relationship])

## Multi-Terminal Isolation Assessment
[Required per constitutional compliance]

**State sharing:** [Does this design create shared mutable state?]
- If YES: [Document isolation mechanism]
- If NO: [State "None - single-terminal safe"]

**Concurrency safety:** [Can multiple terminals execute simultaneously?]
- [Document any race conditions or edge cases]

**Stale data immunity:** [How do terminals discover state changes?]
- [Propagation mechanism or N/A]

## References
- [External source 1](URL): [Key takeaway]
- [External source 2](URL): [Key takeaway]
- [Internal document]: [Reference]

---

**Confidence:** [X]% — [evidence summary]

**Review status:** Reviewed by | Pending review

**Last updated:** YYYY-MM-DD
```

**Feature flags:**
- `RESILIENCE_DISABLED_FOR=<skill_names>` — disable resilience for specific features
- `RESILIENCE_OBSERVE_ONLY=true` — log without applying resilience patterns

**Import:**
```python
from src.lib.resilience_patterns import with_resilience, TransientLLMError, QuotaError
