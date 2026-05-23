# Execution Mode Reference

## Execution Mode Steps (Direct Testing)

For targeted testing without full discovery:

1. **Extract context** - Parse conversation for target files and work type
2. **Generate codemap** - Reuse enhance_command.create_codemap() for dependency analysis
3. **Trace dependencies** - Extract affected modules and information flow from codemap.relationships
4. **Calculate incremental scope** - Map modules to tests, identify affected tests only
5. **Check cache** - Reuse cached results for unchanged tests
6. **Calculate risk score** - Apply deterministic formula: tier x size x kind
7. **Determine strictness** - HIGH -> T1+T2, MEDIUM -> T1 only, LOW -> T2 optional
8. **Acquire lock** - Multi-terminal coordination using msvcrt.locking()
9. **Run tests** - Execute all test types with profiling
10. **Detect flaky tests** - Flag intermittent failures
11. **Analyze trends** - Coverage changes over 7/30/90-day windows
12. **Group failures** - Cluster by root cause to reduce noise
13. **Cache results** - Store for future runs
14. **Release lock** - Free multi-terminal lock
15. **Generate report** - Director-friendly decision table + all analytics

## Validation Rules

- **Before testing**: Verify target files exist, validate paths are in project root
- **During testing**: All test execution must produce actual output (no synthesis)
- **After testing**: Verify test results before caching (no corrupted cache entries)
- **Multi-terminal**: Always acquire lock before cache operations, release after
- **Windows-only**: Use msvcrt.locking(), never Unix domain sockets or POSIX flock

## Integration with Existing Skills

- **`/test`** - Reuses test discovery patterns and health check utilities
- **`/tdd`** - Consumes `.test_gaps.json` for test-driven development
- **`/verify`** - Shares pytest results and coverage data

## Files

- `__main__.py` - Entry point with CLI argument parsing
- `t_core.py` - Context extraction + codemap integration
- `risk_scoring.py` - Deterministic risk formula
- `director_output.py` - Director-friendly formatting
- `windows_ipc.py` - Windows file locking primitives
- `incremental_testing.py` - Incremental test scope calculation
- `test_cache.py` - Test result caching
- `flaky_detection.py` - Flaky test detection
- `coverage_trends.py` - Coverage trend analysis
- `profiling.py` - Test execution profiling
- `failure_grouping.py` - Failure pattern grouping
- `code_map.py` - Codemap visualization wrapper
- `README.md` - Skill documentation

## Testing

Tests are located in `tests/`:
- `test_windows_ipc.py` - Windows file locking tests
- `test_risk_scoring.py` - Risk scoring determinism tests
- `test_codemap_integration.py` - Codemap reuse tests

Run tests with:
```bash
cd P://.claude/skills/t
python -m pytest tests/ -v
```

## Success Criteria

- Context extraction works (conversation-based, no git needed)
- Codemap reuse successful (leveraging enhance_command.create_codemap())
- Code visualization generates director-friendly views
- Risk scoring is deterministic (same inputs -> same score)
- Multi-terminal safety (no corrupted cache, no deadlocks)
- All test types run (functional, unit, regression, integration, intelligent)
- Director-friendly output (decision tables, code maps, test heatmaps, gap analysis)
- Incremental testing works (400+ seconds saved on average)
- Test caching works (6+ seconds saved per run)
- Flaky detection flags intermittent failures
- Coverage trends track improving/degrading modules
- Profiling identifies slow tests (>5s)
- Failure grouping reduces noise by clustering root causes
