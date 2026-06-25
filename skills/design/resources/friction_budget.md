# Friction Budget Quality Attribute

## Definition

**Friction budget** measures how much cognitive load the design places on the user.

A design should minimize friction by:
- Reducing unnecessary clarification requests
- Preferring recommendations over choice prompts
- Reaching useful output quickly
- Shielding users from internal tool/gate failures

## Metrics

| Metric | What It Measures | Good Threshold | Warning Threshold |
|--------|------------------|----------------|-------------------|
| **Clarification count** | How many times user must clarify | ≤ 1 | > 1 |
| **Permission push count** | How many times assistant asks permission instead of recommending | 0 for routine tasks | > 1 |
| **Implementation choice burden** | How many choices pushed onto user | ≤ 1 | > 2 |
| **Internal failure exposure** | How many internal tool/gate failures shown to user | 0 | > 0 |
| **Time to first action** | How long until useful output | < 2 minutes (fast), < 5 minutes (deep) | > 5 minutes (fast), > 10 minutes (deep) |
| **Safe default availability** | Could assistant recommend safely instead of asking? | Yes | No |

## Validation Rules

### Fail Conditions (Critical)

A design **fails** friction budget validation if:

1. **Clarification count > 3** without clear justification
   - Example: Asking 4+ clarifications before offering a recommendation
   - Exception: When clarification materially changes the implementation approach

2. **Time to first action exceeds threshold**
   - Fast template: > 5 minutes without useful output
   - Deep template: > 10 minutes without useful output

3. **No safe default for preference-based choices**
   - Every A/B choice requires user input
   - Neither option is marked as recommended with criterion

### Warn Conditions (Advisory)

A design **warns** on friction budget if:

1. **Permission push count > 2** for routine tasks
   - Example: "May I?" for 3+ non-destructive changes in a row

2. **Clarification count > 1** for clearly-scoped requests
   - Example: User provides clear requirements, but assistant asks for clarification anyway

3. **Internal tool failures exposed to user**
   - User sees "Tool X failed, trying fallback..." instead of handling transparently

## Decision Framework: Ask vs Recommend

**Ask the user when:**
- The choice is genuinely preference-based and affects UX significantly
- User explicitly asks for options ("show me alternatives")
- The decision is irreversible or has major cost implications
- User has domain knowledge and wants to be in control

**Recommend with criterion when:**
- The choice has a clear objective best path (performance, reliability, cost)
- User is frustrated or asked for the "optimal happy path"
- User said "I'm bad with words" or "I don't know what I don't know"
- The choice is reversible or low-cost
- Time-to-value is critical

## Examples

### Good (Low Friction)

```
I recommend using `redis` for caching.

**Criterion:** Redis provides the lowest latency with the smallest operational overhead
for your use case (single cache key, no complex queries).

**First reversible step:** Add `redis` as a dependency and wire it up with a
one-minute integration test.

**Risk:** If Redis goes down, cache misses go to the database.
**Mitigation:** Configure Redis with a fallback to in-memory cache.
```

### Bad (High Friction)

```
We have several caching options:

A. Redis — Good for distributed systems, but requires infrastructure
B. Memcached — Simple, but no persistence
C. In-memory — Fastest, but no sharing across terminals
D. File-based cache — No external dependencies, but slow

Which would you prefer?
```

**Problems:**
- Pushes 4 choices onto user (burden = 4)
- No criterion or recommendation
- No first step provided
- User must make infrastructure decision without clear guidance

## Integration

### In Templates

Add to quality checklists in `base.md`:

```markdown
### Quality Checklist

- [ ] Friction budget: clarification_count ≤ 1
- [ ] Friction budget: permission_push_count = 0 for routine tasks
- [ ] Friction budget: time_to_first_action < threshold
- [ ] Friction budget: safe_default_choice available for non-preference choices
```

### In Validation

Use `validate_friction_budget()` from `validate_templates.py`:

```python
friction_issues = validate_friction_budget(output_content)
if friction_issues:
    for issue in friction_issues:
        print_status(issue, "warn" if "warn" in issue.lower() else "fail")
```

## References

- See `SKILL.md` → "Frustrated User / Unclear Objective Protocol" → "Reduce User Decision Burden"
- See `routing.py` → `should_use_recommendation_mode()` for agency mode detection