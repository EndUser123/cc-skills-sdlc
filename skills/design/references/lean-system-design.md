# Lean System Design Reference

## Lean Principles Applied to `/arch`

Lean System Design is **applied automatically** to all `/arch` outputs. It optimizes for value delivery with minimal waste.

**Opt-out**: `--no-lean` flag

---

## Core Principles

### 1. Value Optimization
Focus on the ~80% of value delivered by ~20% of the effort. Every architecture recommendation should identify its "core plan" — the minimal set of changes that deliver the majority of the benefit.

**Application in /arch**:
- Identify the smallest design change that solves the problem
- Distinguish "core" (must-have for 80% value) from "extended" (nice-to-have for remaining 20%)
- Quantify: "This change gives you ~80% of the benefit with 3 tasks"

### 2. Extension Over Creation
Prefer extending existing patterns, modules, and infrastructure over creating new ones.

**Application in /arch**:
- Before proposing a new file/module, check if an existing one can be extended
- Before proposing a new dependency, check if an existing one can serve the need
- Name the existing artifact being extended

### 3. Dependency Pruning
Classify every dependency as MUST, SHOULD, or MAY:

| Level | Description | Example |
|-------|-------------|---------|
| **MUST** | The design cannot function without this | `sqlite3` for file-based state |
| **SHOULD** | The design is significantly better with this | `filelock` for atomic writes |
| **MAY** | The design is slightly better with this | `rich` for colored output |

**Application in /arch**:
- Every proposed dependency must be classified
- Minimize MUST dependencies
- Question each MUST: "Is there a stdlib or existing alternative?"

### 4. Contract-First Design
Define boundaries before implementation. For every producer/consumer boundary, specify:
- What the producer guarantees
- What the consumer requires
- What happens when the contract is violated

**Application in /arch**:
- Emit Contract Authority Packets for contract-sensitive designs
- Never assume "the consumer probably handles it"

### 5. Core vs Extended Plans
- **Core plan**: 5-10 tasks for ~80% value
- **Extended plan**: Remaining tasks for the final ~20%

**Application in /arch**:
- When producing implementation recommendations, separate core from extended
- Core tasks first; extended tasks clearly labeled as such

### 6. Environment Alignment
Design for the actual deployment environment:
- **OS**: Windows 11
- **Workflow**: CLI-centric
- **Team size**: Solo developer
- **Tool**: Claude Code agentic harness

**Application in /arch**:
- Avoid multi-team governance patterns
- Avoid cloud infrastructure assumptions
- Prefer local-first, file-based solutions
- Account for Windows path conventions

---

## Dependency Classification Template

```yaml
dependencies:
  - name: package_name
    level: MUST | SHOULD | MAY
    justification: "Why this dependency is classified at this level"
    alternatives: ["alternative 1", "alternative 2"]
    why_not_alternative: "Why alternatives were rejected"
```

---

## Value Assessment Questions

Before recommending a design change, answer:

1. **What unique value does this provide?** (Not already covered by existing code)
2. **What existing code is being replaced or extended?**
3. **What is the smallest change that delivers 80% of the value?**
4. **What is the blast radius if this change is wrong?**

---

## Anti-Patterns (Violations of Lean Principles)

| Anti-Pattern | Principle Violated | Better Approach |
|--------------|-------------------|-----------------|
| Creating new module when existing one can be extended | Extension over creation | Extend existing module |
| Adding new dependency for minor convenience | Dependency pruning | Use existing dependency |
| Proposing 30-task implementation for a simple change | Value optimization | Identify 5-task core plan |
| Designing for multi-team governance | Environment alignment | Design for solo dev |
| Assuming cloud deployment | Environment alignment | Design for local-first |
| Proposing new framework without stdlib check | Dependency pruning | Check stdlib first |
