# Implementation Plan: Refactor Skill Improvements

## Overview

Implement 8 priority improvements to the `/refactor` skill following architecture decision (Option C: both SKILL.md documentation AND Python automation modules). Focus on P0 high-impact improvements first (rollback automation, test generation, synergy detection).

## Architecture

### Module Structure
```
P:\.claude\skills\refactor\
├── SKILL.md                      # Update with 8 improvements (workflow documentation)
├── __init__.py                   # Entry point (exists)
├── __csf/src/refactor/                      # NEW: Python automation modules
│   ├── __init__.py
│   ├── rollback_manager.py       # P0: Git-based rollback automation
│   ├── test_generator.py         # P0: TDD phases (RED/GREEN/REGRESSION)
│   ├── synergy_detector.py       # P0: Cross-file pattern clustering
│   ├── complexity_triage.py      # P1: Risk-based prioritization
│   ├── state_manager.py          # P1: Progress persistence (.evidence/refactor/state.json)
│   └── config.py                 # P1: CLI params + config file support
└── __csf/tests/refactor/                        # NEW: Test suite
    ├── __init__.py
    ├── test_rollback_manager.py
    ├── test_test_generator.py
    ├── test_synergy_detector.py
    └── test_config.py
```

### Key Components

1. **Rollback Manager** (`lib/rollback_manager.py`)
   - Capture git state before refactoring
   - Generate rollback scripts (.evidence/refactor/rollbacks/)
   - Cleanup on success

2. **Test Generator** (`lib/test_generator.py`)
   - Create characterization tests before refactoring (RED phase)
   - Verify tests fail before changes
   - Verify tests pass after refactoring (GREEN phase)

3. **Synergy Detector** (`lib/synergy_detector.py`)
   - Cross-file pattern clustering
   - DRY violation detection
   - Extraction opportunity identification

4. **Complexity Triage** (`lib/complexity_triage.py`)
   - Calculate cyclomatic complexity
   - Risk-based prioritization (CC × usage × risk)
   - High-complexity flagging (CC ≥ 15)

5. **State Manager** (`lib/state_manager.py`)
   - Progress persistence (.evidence/refactor/state.json)
   - Track completed/in-progress findings
   - Incremental mode support

6. **Config** (`lib/config.py`)
   - CLI argument parsing
   - Config file support (.refactor.yaml)
   - Threshold configuration (--cc-threshold, --dry-threshold)

## Data Flow

```
User invokes /refactor
    ↓
Load config (CLI args + .refactor.yaml)
    ↓
Load state (.evidence/refactor/state.json) if exists
    ↓
DISCOVER: Launch parallel agents (Task tool)
    ↓
DEDUPLICATE: Merge findings
    ↓
PRIORITIZE: Aggregate by P0→P3
    ↓
COMPLEXITY TRIAGE: Risk-based scoring (CC × usage × risk)
    ↓
SYNERGY DETECTION: Cluster cross-file patterns
    ↓
CONSTITUTIONAL FILTER: Apply SoloDevConstitutionalFilter
    ↓
If --dry-run: STOP and present findings
    ↓
For each finding:
    ├─ Create rollback plan (rollback_manager)
    ├─ RED phase: Create test (test_generator)
    ├─ Verify test FAILS
    ├─ Apply refactoring
    ├─ GREEN phase: Verify test PASSES
    ├─ Update state (state_manager)
    └─ Cleanup rollback on success
    ↓
REGRESSION: Run full test suite
    ↓
Save state (.evidence/refactor/state.json)
```

## Error Handling

1. **Git operations**: Catch subprocess errors, provide user-friendly messages
2. **Test generation**: Handle missing test directories, create if needed
3. **State persistence**: Handle corrupted state files, fallback to empty state
4. **Config loading**: Use defaults if config file missing/invalid

## Test Strategy

### Unit Tests (per module)
- `test_rollback_manager.py`: Test rollback plan creation, cleanup
- `test_test_generator.py`: Test RED/GREEN/REGRESSION phases
- `test_synergy_detector.py`: Test pattern clustering, DRY detection
- `test_config.py`: Test CLI parsing, config loading

### Integration Tests
- End-to-end refactor workflow with rollback
- State persistence across sessions
- Config file loading with overrides

### Edge Cases
- Empty findings list
- Corrupted state file
- Missing git repository
- Concurrent refactor sessions

## Standards Compliance

**Python 3.12+ standards:**
- Type hints on all public functions
- `asyncio` for I/O-bound operations (git, file I/O)
- `pathlib.Path` for path operations
- `dataclasses` for data models
- Context managers for resource management

**Universal principles:**
- DRY: Reuse existing evidence collection infrastructure
- Separation of concerns: Each module has single responsibility
- Testing: 80%+ coverage threshold
- Documentation: Docstrings on all public APIs

## Ramifications

**Impact on existing code:**
- SKILL.md: Add 8 improvements to workflow documentation
- No breaking changes to existing functionality
- Backward compatible: All improvements are additive

**Migration path:**
- No migration needed - new modules are independent
- State file created on first run
- Config file optional (defaults provided)

## Pre-Mortem Analysis

**Failure Mode 1: Rollback script fails to revert**
- **Root cause**: Git state changed between snapshot and revert
- **Prevention**: Store git commit hash, verify before rollback, warn if state changed
- **Test scenario**: Simulate changed git state, verify error handling

**Failure Mode 2: Test generation creates invalid tests**
- **Root cause**: Incorrect template or missing test directory
- **Prevention**: Validate test syntax before writing, create directories if missing
- **Test scenario**: Generate test for file without test directory, verify created

**Failure Mode 3: State corruption causes data loss**
- **Root cause**: Concurrent writes to state file, interrupted writes
- **Prevention**: File locking, atomic writes (write to temp then rename), backup old state
- **Test scenario**: Simulate concurrent writes, verify data integrity

**Observability:**
- **Metrics**: Rollback success rate, test generation success rate, state load/save errors
- **Logs**: All operations logged to `.evidence/refactor/refactor.log`
- **Alerts**: State corruption detected, git operation failures

## Implementation Tasks

### Task 1: Create lib/ directory structure
- [ ] Create `lib/__init__.py`
- [ ] Create `__csf/tests/refactor/` directory with `__init__.py`

### Task 2: Implement config.py (P1)
- [ ] Create RefactorConfig dataclass
- [ ] Implement CLI argument parsing
- [ ] Implement config file loading (.refactor.yaml)
- [ ] Add threshold defaults (CC=15, dry=80)
- [ ] Tests: test_config.py

### Task 3: Implement rollback_manager.py (P0)
- [ ] Create RollbackPlan dataclass
- [ ] Implement git state capture
- [ ] Implement rollback script generation
- [ ] Implement cleanup on success
- [ ] Tests: test_rollback_manager.py

### Task 4: Implement test_generator.py (P0)
- [ ] Implement RED phase (test creation)
- [ ] Implement GREEN phase (test verification)
- [ ] Implement REGRESSION phase (full test suite)
- [ ] Integrate with evidence_collector
- [ ] Tests: test_test_generator.py

### Task 5: Implement synergy_detector.py (P0)
- [ ] Implement pattern clustering algorithm
- [ ] Implement DRY violation detection
- [ ] Implement extraction opportunity identification
- [ ] Tests: test_synergy_detector.py

### Task 6: Implement complexity_triage.py (P1)
- [ ] Implement cyclomatic complexity calculation
- [ ] Implement risk-based scoring (CC × usage × risk)
- [ ] Implement high-complexity flagging
- [ ] Tests: test_complexity_triage.py

### Task 7: Implement state_manager.py (P1)
- [ ] Implement state persistence (.evidence/refactor/state.json)
- [ ] Implement progress tracking
- [ ] Implement incremental mode
- [ ] Add file locking for concurrent access
- [ ] Tests: test_state_manager.py

### Task 8: Update SKILL.md
- [ ] Document 8 improvements in workflow
- [ ] Add new sections: Rollback Automation, Test Generation, Synergy Detection, Complexity Triage, Incremental Mode, Configuration Thresholds, Progress Persistence
- [ ] Update options section with new CLI flags
- [ ] Update evidence collection section

### Task 9: Integration testing
- [ ] End-to-end refactor workflow test
- [ ] State persistence test
- [ ] Config file override test
- [ ] Rollback recovery test

### Task 10: Documentation
- [ ] Update README (if exists)
- [ ] Add usage examples for new features
- [ ] Document config file format
