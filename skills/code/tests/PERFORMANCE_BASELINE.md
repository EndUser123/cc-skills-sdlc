# Performance Baseline

## Test Suite Performance Baseline

This document records the baseline execution time for the Core Plan test suite and defines the acceptable performance regression threshold.

### Baseline Execution Time

**Baseline**: 10 seconds

The full test suite (`tests/` directory) should complete in approximately 10 seconds when run with time mocking enabled (via the `mock_time` fixture).

### How Baseline Was Measured

1. **Environment**: Windows 11, Python 3.14+
2. **Test Discovery**: `pytest tests/ -v`
3. **Time Mocking**: `freezegun` library freezes time during test execution
4. **Measurement**: Wall-clock time from test start to completion

### Performance Regression Threshold

**Acceptable Threshold**: 1.2× baseline = 12 seconds

If the test suite execution time exceeds 12 seconds (1.2× the 10-second baseline), this indicates a potential performance regression that should be investigated.

### Performance Regression Test

The `test_performance_regression()` function in `conftest.py` enforces this threshold using the `@pytest.mark.timeout(12)` decorator. If the suite exceeds 12 seconds, the test will timeout and fail.

### Factors Affecting Execution Time

- **Time Mocking**: Tests use `freezegun` to mock time, ensuring consistent execution
- **Fixture Overhead**: `mock_time` fixture adds minimal overhead
- **File I/O**: Evidence artifact generation is minimal with time mocking
- **Test Isolation**: Each test runs in isolation with automatic cleanup

### Recalibrating the Baseline

If test suite execution time consistently changes due to legitimate additions:

1. Measure new baseline time: `pytest tests/ -v --timing`
2. Update this file with new baseline
3. Update threshold: `new_baseline × 1.2`
4. Update `@pytest.mark.timeout(N)` decorator in `test_performance_regression()`

### Monitoring

To check current test suite performance:

```bash
# Run with timing information
pytest tests/ -v --timing

# Run performance regression test only
pytest tests/ -v -k test_performance_regression
```

---

**Last Updated**: 2026-03-16
**Baseline Version**: 1.0
