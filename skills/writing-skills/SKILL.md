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

1. **RED**: Run pressure scenario with subagent WITHOUT the skill. Document failure.
2. **GREEN**: Write skill that addresses those specific failure modes.
3. **REFACTOR**: Close loopholes and re-test until bulletproof.

## Frontmatter Rule

**CRITICAL: Description = When to Use, NOT What the Skill Does**

The description should ONLY describe triggering conditions. Do NOT summarize the skill's process or workflow in the description.