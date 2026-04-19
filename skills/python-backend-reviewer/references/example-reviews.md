# Example Reviews

Concrete examples of how to use the Python Backend Reviewer for common scenarios.

---

## Example 1: Duplicate Validation Logic

**User request:** "Review this code for quality issues"

**Analysis:**

```bash
uv run python scripts/detect_duplicates.py api/
```

**Finding:** Email validation duplicated in 5 files

**Recommendation:**

```python
# Extract to utils/validation.py
def validate_email(email: str) -> None:
    if not email or "@" not in email:
        raise ValueError("Invalid email")

# Import everywhere
from utils.validation import validate_email
```

---

## Example 2: Recreated Retry Logic

**User request:** "Check if we're recreating utility functions"

**Analysis:**

```bash
uv run python scripts/analyze_imports.py services/
```

**Finding:** Custom retry logic in 3 services

**Recommendation:**

```python
# Replace with tenacity
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def fetch_data(url: str):
    return await client.get(url)
```

---

## Example 3: Complex Function

**User request:** "This function is hard to understand"

**Analysis:**

```bash
uv run python scripts/complexity_analyzer.py utils/processor.py
```

**Finding:** Complexity 23, nesting depth 6

**Recommendation:** Extract nested logic into helper functions (see [refactoring_patterns.md](refactoring_patterns.md#pattern-extract-nested-logic))
