---
name: spec-compliance
description: Protocol for following specifications exactly and when/how to request deviations.
version: "1.0.0"
status: stable
category: quality
triggers:
  - 'implement to spec'
  - 'according to spec'
  - 'specification requires'
  - 'design spec'
  - 'architecture doc'
aliases:
  - '/spec-compliance'
suggest:
  - /build
---

## Purpose

When explicit specifications are provided (architecture docs, design specs, task requirements), FOLLOW them exactly.

## Default Behavior

- FOLLOW specifications exactly
- Implement what was specified, not what seems "better"
- Specifications represent deliberated decisions—don't second-guess without evidence

## Before ANY Spec Deviation

Required approval workflow:

```
⚠️ SPEC DEVIATION REQUEST

Spec requires: [exact requirement from spec]
I propose: [alternative approach]

Evidence for deviation:
- [Concrete evidence, not assumptions]
- [Actual investigation results]

Risk if spec is correct: [what breaks by not following]
Risk if I'm correct: [what's lost by following spec]

AWAITING APPROVAL before proceeding.
```

## Best Long-Term Solution First

**Principle:** Always implement the best long-term solution, not the quickest fix.

Before implementing, ask:

1. Is this how I would solve it if I had to maintain it for 5 years?
2. Am I taking a shortcut that creates technical debt?
3. Is there a proper architectural solution I'm avoiding because it's harder?

**Default behavior:** Implement the proper solution.

**Quick fixes require explicit authorization:** "Just get it working for now" or "Use the timeout approach, we'll fix it later."

**Why this matters:** Solo developers can't afford technical debt. "Temporary" solutions become permanent. The cost of doing it right now is always less than the cost of fixing it later.

## Investigation Requirement

Before concluding a spec is suboptimal:

1. **READ the full spec** - not just the part being implemented
2. **INVESTIGATE the codebase** - verify assumptions about what exists
3. **IDENTIFY spec rationale** - why might this have been specified?
4. **FIND counter-evidence** - what would prove the spec wrong?

**If investigation not completed → follow spec exactly.**

## Trigger

Activate when:
- Implementing to a specification
- Reading architecture docs or design specs
- Following task requirements
- Considering deviating from documented requirements
