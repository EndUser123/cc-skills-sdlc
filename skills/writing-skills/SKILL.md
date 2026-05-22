---
name: writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
---
# Writing Skills

## Overview

**Writing skills IS Test-Driven Development applied to process documentation.**

**Mandatory Standards:** See `__lib/skill_writing_standards.md` for the Iron Law, TDD mapping, and bulletproofing rules.

## The Iron Law

```
NO SKILL WITHOUT A FAILING TEST FIRST
```

Write skill before testing? Delete it. Start over.

## RED-GREEN-REFACTOR for Skills

### PHASE 1: RED (Failing test documentation — Generation)

1. **RED**: Run pressure scenario with subagent WITHOUT the skill. Document failure.

**STOP GATE — After RED phase:**
```
STOP — Before writing any skill code:

RED phase produces FAILURE DOCUMENTATION.
This is evidence of WHAT DOESN'T WORK, not a prescription for what WILL work.

Do NOT proceed to GREEN until RED documentation is complete and verified.
```

### PHASE 2: GREEN (Skill writing — Generation + Validation of RED evidence)

2. **GREEN**: Write skill that addresses those specific failure modes.

**STOP GATE — After GREEN phase, before REFACTOR:**
```
STOP — Before claiming the skill works:

GREEN phase produced DRAFT SKILL CODE.
The skill addresses RED failure modes on paper.
This is NOT proof the skill will work in practice.

Do NOT claim the skill is complete. Proceed to REFACTOR to close loopholes.
```

### PHASE 3: REFACTOR (Loophole closing — Generation)

3. **REFACTOR**: Close loopholes and re-test until bulletproof.

**STOP GATE — After REFACTOR phase:**
```
STOP — Before claiming skill is deployable:

REFACTOR phase may have closed loopholes, but the skill has NOT been tested
against a fresh RED scenario (real-world failure documentation from Phase 1).

Run a new RED scenario. If it fails differently, return to GREEN.
If it passes, the skill is valid — but still requires the original RED evidence.
```

---

### Evidence-First Principles

## Frontmatter Rule

**CRITICAL: Description = When to Use, NOT What the Skill Does**

The description should ONLY describe triggering conditions. Do NOT summarize the skill's process or workflow in the description.

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