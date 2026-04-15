# Priority Inference Implementation Plan

## Overview

Build an automatic priority triage system for rca that scores files/contexts from 0-100 based on execution patterns, eliminating dependency on manual memory files (prod-bugs.md, critical-paths.md).

## Architecture

### Module Structure

```
rca/
├── tools/
│   └── priority_inference.py  # NEW: Main priority scoring module
├── tests/
│   └── test_priority_inference.py  # NEW: Test coverage
└── hooks/
    └── (existing hooks provide data source)
```

### Components

**1. PriorityInference Class** (`tools/priority_inference.py`)
- `calculate_priority_score(file_path: str) -> int` (0-100)
- `get_priority_factors(file_path: str) -> dict` (breakdown of scores)
- `rank_contexts(contexts: list[str]) -> list[tuple[str, int]]`

**2. Error Frequency Clustering** (HIGH priority, 40% weight)
- Count how often each file appears in error states
- Source: Hook state database (rca_workflow.json, actions_*.json)
- Decay old errors exponentially (time-weighted frequency)

**3. Recent Change Detection** (HIGH priority, 30% weight)
- Git history analysis for file modification recency
- Score: (1 / age_days) * max_score
- Files changed in last 7 days get priority boost

**4. Static Complexity Metrics** (MEDIUM priority, 20% weight)
- Cyclomatic complexity (AST-based)
- Function length (lines per function)
- Nesting depth (maximum indent level)
- Normalized: 0-100 scale

**5. Test Coverage Gaps** (MEDIUM priority, 10% weight)
- Parse pytest coverage reports (.coverage)
- Lower coverage = higher priority
- Files with <80% coverage flagged

### Data Flow

```
Hook State DB (rca_workflow.json)
    ↓
Error Frequency Aggregator
    ↓
Priority Scorer (combines all signals)
    ↓
Rank Output (file → score 0-100)
```

### Error Handling

- Missing git repository → Skip recent change detection (log warning)
- Missing coverage file → Skip test coverage (log advisory)
- Corrupted state DB → Return default priority (50), log error
- File not found → Return priority 0 (not applicable)

### Test Strategy

**Unit Tests:**
- `test_error_frequency_clustering()` - Mock state DB with error patterns
- `test_recent_change_detection()` - Mock git log output
- `test_complexity_metrics()` - Test Python files with known complexity
- `test_priority_score_calculation()` - Verify 0-100 range, weights sum to 1.0
- `test_rank_contexts()` - Verify sorting by priority score

**Integration Tests:**
- `test_end_to_end_priority()` - Real hook state, git repo
- `test_missing_git_repository()` - Graceful degradation
- `test_missing_coverage_file()` - Advisory only, doesn't crash

**Edge Cases:**
- Empty state database → All files get priority 50 (default)
- File with no history → Priority 0 (not applicable)
- Corrupted JSON files → Log error, return safe defaults
- Concurrent access → FileLock on state DB reads

## Standards Compliance

**Python 3.12+ Standards:**
- Type hints on all functions
- Async/await not needed (file I/O is fast enough)
- Context managers for file locks
- dataclasses for data structures
- pathlib.Path for all file paths
- logging for structured output (not print)

**Code Quality:**
- ruff linting (no warnings)
- mypy type checking (strict mode)
- pytest coverage >80%
- README with usage examples

## Ramifications

**Impact on existing code:**
- None (new module, no modifications to existing hooks)
- Optional integration (rca can call it, but not required)

**Backwards compatibility:**
- Existing rca workflow unchanged
- New feature is additive only

**Performance:**
- Error frequency: O(n) where n = actions in state DB
- Git history: O(log n) with git log --limit
- Complexity metrics: O(m) where m = AST nodes
- Total latency: <100ms for typical files

**Observability:**
- Log scoring decisions at INFO level
- Emit metrics: priority_score, error_frequency, git_age_days, complexity
- Store priority cache for 5 minutes (reduce repeated scoring)

## Pre-Mortem

**Failure Mode 1: Infinite loop in git log parsing**
- Root cause: Malformed git output causes regex to never match
- Prevention: Timeout after 5 seconds, limit git log to 100 commits

**Failure Mode 2: Memory exhaustion on large files**
- Root cause: AST loading of 10K+ line files
- Prevention: Skip complexity analysis for files >5K lines, log advisory

**Failure Mode 3: Race condition on state DB reads**
- Root cause: Two terminals read state DB simultaneously
- Prevention: Use portalocker.FileLock with 5-second timeout

**Failure Mode 4: Priority score always 50 (default)**
- Root cause: All signals failing (no git, no state DB, no coverage)
- Prevention: Log WARNING with details of which signals failed
