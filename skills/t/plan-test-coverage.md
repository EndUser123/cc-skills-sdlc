# Test Coverage Implementation Plan

**Status**: Active
**Created**: 2026-02-26
**Goal**: Increase test coverage for /t skill modules

## Executive Summary

Implement tests for uncovered /t skill modules following strategic priority:
1. Quick wins: code_map.py (helper functions)
2. Medium effort: Advanced features (test_cache, flaky_detection, coverage_trends, profiling)
3. Higher effort: director_output.py (45% → 80%)

**Outcome Anchor**: All new tests pass, overall coverage increases, no regressions.

## Tasks

### Task 1: Test code_map.py (Quick Win)
**Priority**: HIGH (easy win, low risk)
**File**: `tests/test_code_map.py`
**Acceptance**:
- Test `generate_layer_view()` with mock codemap
- Test `generate_dependency_graph()` with mock relationships
- Test `generate_test_heatmap()` with mock data
- Coverage target: 70%+

### Task 2: Test director_output.py (Higher Value)
**Priority**: HIGH (increase from 45% → 80%)
**File**: `tests/test_director_output.py`
**Acceptance**:
- Test `determine_strictness()` boundary conditions
- Test `format_director_report()` with mock data
- Test risk threshold mappings
- Coverage target: 80%+

### Task 3: Test test_cache.py (Medium Effort)
**Priority**: MEDIUM (self-contained, will be needed)
**File**: `tests/test_test_cache.py`
**Acceptance**:
- Test `calculate_file_hash()` consistency
- Test `calculate_test_key()` with dependencies
- Test cache get/set/invalidate operations
- Test statistics calculation
- Coverage target: 70%+

### Task 4: Test flaky_detection.py (Medium Effort)
**Priority**: MEDIUM (self-contained, will be needed)
**File**: `tests/test_flaky_detection.py`
**Acceptance**:
- Test `record_run()` storage
- Test `analyze_flakiness()` pass rate calculation
- Test flaky detection thresholds
- Coverage target: 70%+

## Task Breakdown

### Task 1: code_map.py Tests

**Test Cases**:
1. `test_generate_layer_view()` - Verify layer extraction from codemap
2. `test_generate_dependency_graph()` - Verify mermaid graph generation
3. `test_generate_test_heatmap()` - Verify heatmap formatting

**Implementation**:
- Mock codemap dict with file_structure and relationships
- Verify output format (markdown, correct structure)
- Test edge cases (empty codemap, missing sections)

### Task 2: director_output.py Tests

**Test Cases**:
1. `test_determine_strictness_high_risk()` - risk >= 0.7 → T1+T2 hard_fail
2. `test_determine_strictness_medium_risk()` - 0.4 <= risk < 0.7 → T1 hard, T2 soft
3. `test_determine_strictness_low_risk()` - risk < 0.4 → T1 soft, T2 skip
4. `test_format_director_report()` - Verify decision table format

**Implementation**:
- Test risk boundaries at 0.0, 0.4, 0.7, 1.0
- Verify strictness tuples match expected values
- Test report formatting with mock data

### Task 3: test_cache.py Tests

**Test Cases**:
1. `test_calculate_file_hash()` - Same file → same hash
2. `test_calculate_test_key()` - Hash includes test + dependencies
3. `test_cache_get_set()` - Store and retrieve cache entries
4. `test_cache_invalidate()` - Remove stale entries
5. `test_get_stats()` - Calculate cache statistics

**Implementation**:
- Use temp files for hash testing
- Verify hash determinism (same input → same output)
- Test cache CRUD operations
- Test statistics accuracy

### Task 4: flaky_detection.py Tests

**Test Cases**:
1. `test_record_run()` - Store test run results
2. `test_analyze_flakiness()` - Detect flaky tests (30-70% pass rate)
3. `test_get_all_flaky_tests()` - List all flaky tests
4. `test_history_trimming()` - Keep only last 20 runs

**Implementation**:
- Test run history storage
- Create flaky test scenarios (7/10 passes with different errors)
- Verify flaky detection logic
- Test history size limits

## Success Criteria

- ✅ All 4 test files created
- ✅ All tests pass
- ✅ Coverage increased:
  - code_map.py: 0% → 70%+
  - director_output.py: 45% → 80%+
  - test_cache.py: 0% → 70%+
  - flaky_detection.py: 0% → 70%+
- ✅ No regressions in existing tests
- ✅ Test execution time < 10 seconds total

## Risks

| Risk | Mitigation |
|------|------------|
| Mock complexity for codemap | Use simple dict mocks, not full objects |
| Hash test file cleanup | Use tempfile.TemporaryDirectory() |
| Flaky detection time complexity | Limit history size in tests |
| Director output format changes | Test behavior, not exact format string |

## Rollback Strategy

If any task fails:
1. Delete the problematic test file
2. Keep passing tests
3. Document the gap in README
4. Continue with remaining tasks
