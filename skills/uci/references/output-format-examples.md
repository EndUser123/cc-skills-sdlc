# UCI Output Format Examples

## Markdown (default)

```markdown
## Unified Code Inspection Report

### Verdict: Needs Attention
**Reason**: 1 high security issue, 2 medium performance concerns

### MUST FIX BEFORE MERGE

#### LOGIC-001: Null pointer dereference
- **Impact**: HIGH (runtime crash)
- **Effort**: LOW (add null check)
- **Location**: `src/auth.py:45`
- **Validated by**: adversarial-logic, adversarial-security
```

## JSON

```json
{
  "verdict": "Needs Attention",
  "reason": "1 high security issue, 2 medium performance concerns",
  "blockers": 0,
  "high": 1,
  "medium": 2,
  "low": 5,
  "findings": [...]
}
```

## Summary

High-level verdict with top issues only. Use `--format=summary` for quick overview.
