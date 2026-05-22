---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---
# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Detailed Protocol:** See `__lib/debugging_philosophy.md` for the mandatory 4-phase workflow.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work

## The Four Phases (Summary)

1. **Phase 1: Root Cause Investigation** - Reproduce, gather evidence, trace data flow.
2. **Phase 2: Pattern Analysis** - Compare working vs broken code.
3. **Phase 3: Hypothesis and Testing** - Scientific method, minimal tests.
4. **Phase 4: Implementation** - Failing test, root cause fix, architecture check.

## Supporting Techniques

- **`root-cause-tracing.md`** - Trace bugs backward through call stack.
- **`defense-in-depth.md`** - Add validation at multiple layers.
- **`condition-based-waiting.md`** - Replace arbitrary timeouts.

**Related skills:**
- **test-driven-development** - For failing tests.
- **verification-before-completion** - Verify fix worked.