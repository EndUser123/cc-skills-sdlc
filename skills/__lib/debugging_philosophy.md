# Systematic Debugging Philosophy

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## The Four Phases

### Phase 1: Root Cause Investigation
**BEFORE attempting ANY fix:**
1. **Read Error Messages Carefully**
2. **Reproduce Consistently**
3. **Check Recent Changes**
4. **Gather Evidence in Multi-Component Systems**
5. **Trace Data Flow** (See `root-cause-tracing.md`)

### Phase 2: Pattern Analysis
**Find the pattern before fixing:**
1. **Find Working Examples**
2. **Compare Against References** (Read them COMPLETELY)
3. **Identify Differences**
4. **Understand Dependencies**

### Phase 3: Hypothesis and Testing
**Scientific method:**
1. **Form Single Hypothesis**
2. **Test Minimally** (One variable at a time)
3. **Verify Before Continuing**
4. **When You Don't Know: Ask for help.**

### Phase 4: Implementation
**Fix the root cause, not the symptom:**
1. **Create Failing Test Case** (MANDATORY)
2. **Implement Single Fix** (Smallest possible change)
3. **Verify Fix**
4. **If 3+ Fixes Failed: Question Architecture**

## Red Flags - STOP and Follow Process
- "Quick fix for now"
- "Just try changing X"
- "I'll write the test after"
- "It's probably X"
- Proposing solutions before tracing data flow
- Each fix reveals a new problem elsewhere

## Your Human Partner's Signals
- "Is that not happening?"
- "Stop guessing"
- "Ultrathink this"
- "We're stuck?"
