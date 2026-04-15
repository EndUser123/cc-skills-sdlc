# Investigation Report

Complete documentation of debugging or RCA investigation.

## Analysis Contract

Do not name a root cause until you can fill all of these with evidence:
- Observable Definition
- Evidence Buckets
- Executed Path
- Competing Hypothesis
- Falsifier
- First Divergence
- Root Cause
- Verification

If any of those are missing, do not name a root cause yet. Keep investigating instead of drafting a conclusion.

## Metadata

- **Date**: [YYYY-MM-DD]
- **Investigator**: [Name/Agent]
- **Session ID**: [From rca session]
- **Investigation Type**: [Debug / RCA]
- **Severity**: [Critical / High / Medium / Low]

## Problem Statement

### What is broken?
[One sentence description]

### Observable Definition

**Expected Observable**
[What the user should directly see or experience]

**Non-Equivalent Proxies**
- [Proxy] -> Why this is not proof

**Exact Success Evidence**
[What would directly prove the feature works]

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happens]

### Impact
[Who is affected and how]

## Investigation Summary

### Evidence Buckets

**Mechanism**
[How the code is wired]

**State**
[What runtime state/logs/files show]

**Outcome**
[What the user actually saw]

### Executed Path

[Entry point -> ... -> failure point]
[Name the exact files/functions that were reached]

### Competing Hypothesis

[Strongest alternative explanation]
[Why it is plausible]

### Falsifier

[Evidence that refutes the competing hypothesis]
[Be explicit about why the alternative loses]

### First Divergence

[Earliest point where reality stopped matching the expected path]

### RCA Think Pass

[Strongest likely diagnosis]
[Strongest competing explanation]
[Most pragmatic explanation]
[Smallest discriminating check]
[One refinement only]

### Root Cause

**[Root cause statement]**

**Technical**
[What broke, at the mechanism level]

**Systemic**
[Why the failure was possible]

**Why this is the root cause**
[Tie the root cause back to the executed path and the divergence]

### Evidence Chain

1. **Phase 0: Reproduction**
   - Steps: [How to reproduce]
   - Result: [What happened]

2. **Phase 1: Data Flow / Mental Trace**
   - Trace: [Code path analysis]
   - Finding: [What was discovered]

3. **Phase 2: Hypothesis Testing**
   - Hypothesis 1: [Description] - Rejected
   - Hypothesis 2: [Description] - Confirmed

4. **Phase 3: Root Cause Analysis**
   - 5 Whys: [Why chain]
   - Root Cause: [Final answer]

### Fix Applied

```python
# [Code change or description]
```

### Verification

- [ ] Direct verification on the failure path
- [ ] Regression test added
- [ ] Counterexample checked

## Lessons Learned

### What went well?
- [What worked in this investigation]

### What could be improved?
- [What could be done better next time]

### Prevention
- [How to prevent this type of issue]

## Related Issues

- [Links to related issues, PRs, or investigations]
