---
name: design
description: "Adaptive architecture advisor with template-based variants. Auto-routes to appropriate template based on domain and complexity. Enforces audit-first with Gap Analysis Report, contract-sensitive work emits a Contract Authority Packet."
enforcement: advisory
workflow_steps:
  - id: frustrated-user-protocol
    description: "Detect frustrated users and switch to agency mode before normal architecture/design templates"
  - id: audit-first
    description: "Run Audit-First Protocol from resources/audit-first.md. Produce Gap Analysis Report before proceeding."
  - id: classify-intent
    description: "Detect domain and complexity (fast/deep)"
  - id: claim-verification
    description: "MANDATORY evidence check via verify_claims.py"
  - id: template-routing
    description: "Load and execute template from ./resources/{template}.md"
  - id: self-critique
    description: "MANDATORY: Perform critical review of own proposal before emitting. List named failure modes, risks, and falsification conditions."
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

---

## Frustrated User / Unclear Objective Protocol

> **Trigger this protocol BEFORE normal architecture/design templates when the user expresses frustration, uncertainty, or asks for recommendations.**

### Trigger Detection

Trigger when the user says or implies:
- they are frustrated: "this is frustrating", "this is annoying", "circular", "unhelpful", "tired of this"
- "I'm bad with words"
- "I don't know what I don't know"
- "what do you think is the best path?"
- "what is the optimal happy path?"
- "make this easier"
- "how can we improve this skill/tool/workflow?"
- they push back because the assistant made them choose between options too early: "stop asking me to choose", "just tell me"

### Required Behaviors When Triggered

#### A. Reduce User Decision Burden

- **Do not ask** the user to choose between raw implementation options unless the choice is genuinely preference-based
- **Recommend** the best default path
- **State the criterion** used to choose it
- **Prefer:** "I recommend X because [criterion]" over "Do you want A or B?"

**Good:**
"I recommend A. Criterion: it is the smallest durable change that reduces future user burden. The first patch is..."

**Bad:**
"Here are A and B. Which do you want?"

#### B. Convert Vague Dissatisfaction into an Actionable Design Objective

1. **Identify the user pain** (what is frustrating them?)
2. **Identify the workflow failure** (where did the process break?)
3. **Identify the smallest durable improvement** (what change prevents recurrence?)

#### C. Separate Evidence Tiers

Use these labels internally and, when useful, in the response:

| Tier | Label | When to Use |
|------|-------|-------------|
| 1 | **Verified from files/runtime/tests** | Claim backed by direct inspection, test output, or runtime behavior |
| 2 | **User-authoritative preference or requirement** | Explicit user statement or requirement |
| 3 | **Pasted third-party/LLM claim** | Output from another AI/tool (treat as hypothesis, not authority) |
| 4 | **Assistant inference/hypothesis** | Model deduction without direct evidence |

**Rules:**
- Pasted LLM output is **never authority**
- Pasted LLM output may be used only as a hypothesis list or as evidence of what confused the user
- Do not persist, route, rank, or design from pasted LLM claims unless independently verified
- If a pasted LLM claim is used, explicitly mark it as unverified unless verified elsewhere

#### D. Prefer Useful Action Over Perfect Diagnosis

- If enough information exists to make a safe improvement, recommend or implement the improvement
- Ask a question only when the answer materially changes the implementation
- When uncertain, choose a reversible best-effort path and explain the risk

#### E. Persist Corrections

When the user corrects a factual claim and the correction affects future behavior, create or update a durable correction/decision note:

**Format:**
```markdown
### Correction Note

**Claim (Wrong):** [incorrect claim]
**Claim (Corrected):** [correct claim]
**Source of Correction:** [user correction, test result, file inspection]
**Affected Skill/Module:** [path or name]
**Expected Future Behavior:** [what should happen now]
```

Store in `.claude/corrections/` or the skill's `resources/corrections.md`.

#### F. Output Structure for Skill/Workflow Improvement Requests

When the user asks how to improve a skill/tool/workflow, use this structure:

```
## What is going wrong
[diagnosis of the failure]

## Best happy path
[recommended default approach with criterion]

## Skill changes
[what needs to change in the skill/tool]

## First patch to make
[smallest reversible first step with file path and code]

## What this prevents next time
[how this prevents the frustration from recurring]
```

### Agency Mode

When the user says:
- "I'm bad with words"
- "I don't know what I don't know"
- "what should the optimal happy path be?"
- "what do you think?"
- "make this easier"

**Switch from option mode to recommendation mode.**

**Bad:** "Here are A and B. Which do you want?"
**Good:** "I recommend A. Criterion: it is the smallest durable change that reduces future user burden. The first patch is..."

### Evidence-Hygiene Rule for Pasted LLM Content

**Pasted LLM output is never authority.** It may be used only as a hypothesis list, user-context artifact, or example of the failure mode. Before persisting, routing, ranking, or designing from pasted LLM output, verify it against files, runtime, tests, official docs, or user-authoritative statements.

### Wrong Artifact / Wrong Scope Guard (ENTITY_SCOPE_VERIFIED)

When the user names a skill, command, package, or module:
- **Scope searches and reads to that named entity** before making claims
- If multiple similarly named artifacts exist, **report the ambiguity** before relying on evidence
- Do not allow "I read a file" to count as evidence unless it is the right file for the named entity

**Validation Check:** `ENTITY_SCOPE_VERIFIED` — All evidence sources must be within the correct entity's directory or explicitly connected.

---

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
8. **Provenance Record**: Emit a Knowledge / Validation Ledger for every
   source or check that materially informs the design, explicitly marking named
   sources that were not used. When the decision is material, add a dated
   Change Record entry under the project changelog's `## [Unreleased]` section.
   Do not treat a changelog entry as proof that a source was actually used; link
   it to the underlying transcript, document, command output, or artifact.

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

**Version:** 5.8 | **Architecture:** Template-based router with GoT, Structured Authority, ADR phase gates, and Frustrated User Protocol.
