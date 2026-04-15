# Constitutional Compliance (REQUIRED)

**CRITICAL:** All refactoring recommendations MUST be filtered against solo-dev constitutional constraints.

## Prohibited Patterns (Auto-Filter)

Before suggesting any refactoring, check against these prohibited patterns (CLAUDE.md:240-262):

| Pattern | Filter Because | Alternative |
|---------|---------------|-------------|
| `lock ordering`, `acquisition order` | Enterprise bloat | Use single RLock per object |
| `continuous monitoring` | Background service prohibited | Use on-demand `/health` |
| `real-time metrics` | Background service prohibited | Use query-based metrics |
| `complex abstraction` | Enterprise pattern prohibited | Keep it simple |
| `scalability requirement` | Enterprise pattern prohibited | Optimize when needed |
| `enterprise-grade` | Enterprise pattern prohibited | Use simple solution |

## Required Filter Step

**Before generating action items, ALWAYS run:**

```python
# Import the constitutional filter
from src.core.solo_dev_constitutional_filter import SoloDevConstitutionalFilter

filter_obj = SoloDevConstitutionalFilter()

# Check each proposed refactoring
for action in proposed_refactorings:
    result = filter_obj.check_action_item(action)
    if result.violates_constitution:
        # Skip this action - don't suggest it
        continue
```

## Why This Matters

Refactoring suggestions are high-risk for enterprise bloat:
- "Extract to service" → unnecessary microservice
- "Add abstraction layer" → over-engineering
- "Implement factory pattern" → enterprise pattern
