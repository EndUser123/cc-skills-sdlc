# Code Review Reception

## Overview

Process code review feedback with technical rigor rather than performative agreement.

**Mandatory Protocol:** See `__lib/review_management.md` for the Response Pattern (READ → VERIFY → EVALUATE), Pushback Criteria, and Implementation Order.

## Core Principle

External feedback = suggestions to evaluate, not orders to follow. Verify everything before implementation.

## Forbidden Responses

**NEVER use performative phrases:**
- "You're absolutely right!"
- "Excellent feedback!"
- "Let me implement that now" (without verification)

**INSTEAD:** Restate the technical requirement or ask clarifying questions.

## Implementation Order

1. **Blocking**: Breaks, Security.
2. **Simple**: Typos, Imports.
3. **Complex**: Logic, Refactoring.
4. **Verify**: Test each fix individually.

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
