---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans that are concrete, verifiable, and ready for automated execution.

**Mandatory Standards:** See `__lib/planning_standards.md` for the No-Placeholder rule and v2 Plan Shape.

## Core Principle

Assuming the engineer has zero context for our codebase. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, and how to test it.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- Write failing test.
- Run it (verify failure).
- Write minimal code.
- Run it (verify pass).
- Commit.

See `__lib/planning_standards.md` for the full task structure template.

## Execution Handoff

After saving the plan, offer execution choice:

**1. Subagent-Driven (recommended)** - Fresh subagent per task, review between tasks.
**2. Inline Execution** - Execute tasks in this session using `executing-plans`.