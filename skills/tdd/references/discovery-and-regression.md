# Discovery Phase Details

## DISCOVER Phase: Code Understanding and Gap Loading

**DISCOVER phase happens FIRST, before writing any tests.**

### Discovery Workflow

```
1. Check for /t gap files (automatic /t integration)
2. If gaps exist -> Use gap data to prioritize test creation
3. If no gaps -> Proceed with manual code analysis
4. Read relevant code files
5. Capture baseline test results
```

### /t Integration: Load Test Gaps

**AUTOMATIC:** When `/tdd` is invoked, automatically check for gap files created by `/t`:

```python
from pathlib import Path
import sys

# Add gap_loader to path
sys.path.insert(0, str(Path(__file__).parent))
from gap_loader import load_test_gaps, format_gap_summary

# Load gaps from /t discovery
project_root = Path.cwd()  # Or explicit target
gap_data = load_test_gaps(project_root)

if gap_data:
    # Display gap summary
    print(format_gap_summary(gap_data))

    # Use gaps to prioritize test creation
    # Example: gap_data["gaps"] contains specific missing tests
    # Example: gap_data["test_types"] shows which types are missing
else:
    print("No /t gap file found - proceeding with manual analysis")
```

**Gap file locations:**
- Terminal-scoped: `.claude/state/test_gaps/{terminal_id}_gaps_READY.json`
- Global fallback: `.claude/state/test_gaps/_READY.json`

**Gap data structure:**
```json
{
  "target": "p:/packages/handoff",
  "gaps": [
    "Coverage gap: 48.7% covered, missing: ...",
    "Missing test type: regression tests"
  ],
  "test_types": {
    "unit": 53,
    "integration": 30,
    "edge_case": 9,
    "error_path": 19,
    "regression": 0
  },
  "coverage_percent": 48.69,
  "total_tests": 111,
  "timestamp": "2026-02-28T00:52:28.282674+00:00"
}
```

### Discovery Checklist

**With /t gap data:**
- Gaps loaded and displayed
- Missing test types identified
- Coverage gaps understood
- Prioritize based on gap severity

**Without /t gap data:**
- Read target code files
- Understand architecture and dependencies
- Identify testable scenarios
- Plan test cases manually

**Baseline capture (both paths):**
```bash
# Capture baseline test results
pytest tests/ --tb=no -q > /tmp/baseline.txt
```

---

# REGRESSION Phase (AUTOMATIC - Prevent Cascading Breaks)

**After VERIFY, ALWAYS run related tests to catch cascading failures.**

## What Tests to Run

| Change Type | Run These Tests (TARGETED) | Time |
|-------------|---------------------------|------|
| Display plugin changes | `pytest tests/test_display*.py` | ~10s |
| Download module changes | `pytest tests/test_download*.py tests/test_batch*.py` | ~30s |
| Any refactoring | `pytest tests/test_refactor_safety.py` | ~5s |
| New feature | `pytest tests/test_<feature>.py` | ~5s |

## Targeted vs Full Regression

**DEFAULT: Targeted regression first.**

| Approach | Command | When to Use |
|----------|---------|-------------|
| **Targeted** | `pytest tests/test_X*.py tests/test_Y*.py -v` | First check - only affected modules |
| **Keyword** | `pytest tests/ -k "display or download" -v` | Change spans multiple test files |
| **Full suite** | `pytest tests/ -v` | Before final verification/commit |
