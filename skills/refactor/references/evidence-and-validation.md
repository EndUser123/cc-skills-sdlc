# Evidence Collection & Validation Integration

## Evidence Collection

**MANDATORY:** All TDD phases use `src.core.evidence_collector` for verification.

### Quick Reference

```python
from src.core.evidence_collector import collect_test_evidence, verify_tdd_green, get_evidence_collector

baseline = collect_test_evidence("pytest tests/test_module.py -v")           # 1. Baseline
# ... apply refactoring ...
after = collect_test_evidence("pytest tests/test_module.py -v")              # 2. Verify
assert verify_tdd_green(after).is_verified, "Refactoring broke tests"
regression = collect_test_evidence("pytest tests/ -v")                        # 3. Regression
```

### Evidence Storage

All artifacts stored in `P:\.evidence/` — subdirectories: `commands/`, `tests/`, `files/`, `state/`, `refactor/`.

**New directories** (Priority 1 enhancements):
- `.evidence/refactor/rollbacks/` — Rollback plans with git state
- `.evidence/refactor/behavior/` — Behavior characterizations

| Phase | Evidence Required | Verification |
|-------|------------------|--------------|
| Rollback planning | Rollback plan JSON with git commit | Rollback plan created before refactoring |
| Characterization | Behavior snapshots (before/after) | Behavior preserved within 10% tolerance |
| Refactoring | Post-change test results | `verify_tdd_green()` passes |
| Regression | Full suite results | No new failures introduced |

## Sequential Enforcement (from /v)

**/v provides hook-based stage tracking to prevent skipping validation steps.**

| Hook | Event | Purpose |
|------|-------|---------|
| `PreToolUse_v_stage_enforcer.py` | PreToolUse | Blocks skipping stages |
| `PostToolUse_v_halt_enforcer.py` | PostToolUse | Enforces halt gates |
| `PostToolUse_v_state_tracker.py` | PostToolUse | Tracks stage completion |
| `StopHook_v_completion_gate.py` | Stop | Validates completion |

**Integration pattern:**
```python
from scripts.state_manager import StateManager

state_mgr = StateManager()
state_file = str(state_mgr.state_file)
# Track phase: 'discovery', 'prioritization', 'constitutional_filter', 'red', 'refactor'
```

## Dead Code Detection (from /v Stage 3)

```bash
# Dead code detection with Vulture 2.14
python -m vulture <target> --min-confidence 80
```

| Confidence | Meaning |
|-----------|---------|
| 100% | Definitely unused |
| 90-99% | Likely unused |
| 80-89% | Possibly unused |
| <80% | Too many false positives |

## Layer 4 Quality Gate (from /v)

```python
# Filter synergy findings by confidence threshold
MIN_CONFIDENCE = 80

high_confidence_findings = [
    f for f in all_findings
    if f.get('confidence', 0) >= MIN_CONFIDENCE
]

summary = {
    'input': len(all_findings),
    'output': len(high_confidence_findings),
    'rejection_rate': (len(all_findings) - len(high_confidence_findings)) / len(all_findings) * 100
}
```
