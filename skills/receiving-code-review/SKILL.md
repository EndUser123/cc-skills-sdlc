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
