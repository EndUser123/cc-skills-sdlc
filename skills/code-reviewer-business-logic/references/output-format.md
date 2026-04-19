# Output Format

All 8 sections required. Missing any = review rejected.

```markdown
# Business Logic Review (Correctness)

## VERDICT: [PASS | FAIL | NEEDS_DISCUSSION]

## Summary

[2-3 sentences about business correctness]

## Issues Found

- Critical: [N]
- High: [N]
- Medium: [N]
- Low: [N]

## Mental Execution Analysis

### Function: [name] at file.ts:123-145

**Scenario:** [Concrete scenario]
**Result:** Correct | Issue (see Issues section)
**Edge cases tested:** [List]

### Function: [another]

...

**Full Context Review:**

- Files read: [list]
- Ripple effects: [None | See Issues]

## Business Requirements Coverage

**Requirements Met:**

- [Requirement 1]
- [Requirement 2]

**Requirements Not Met:**

- [Missing requirement]

## Edge Cases Analysis

**Handled:**

- Zero values
- Empty collections

**Not Handled:**

- [Edge case with business impact]

## What Was Done Well

- [Good domain modeling]
- [Proper validation]

## Next Steps

[Based on verdict]
```

## Section Requirements

| # | Section | Required Content |
|---|---------|-----------------|
| 1 | VERDICT | PASS, FAIL, or NEEDS_DISCUSSION |
| 2 | Summary | 2-3 sentences on business correctness |
| 3 | Issues Found | Counts by severity |
| 4 | Mental Execution Analysis | Per-function traces with scenarios |
| 5 | Business Requirements Coverage | Met and not-met lists |
| 6 | Edge Cases Analysis | Handled and not-handled lists |
| 7 | What Was Done Well | Positive findings |
| 8 | Next Steps | Actions based on verdict |
