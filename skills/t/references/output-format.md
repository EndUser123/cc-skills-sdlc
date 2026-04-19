# Output Format Reference

## Executive Summary
```
## Executive Summary
Risk Score: 0.72/1.0 (HIGH)
Context: Working on router.py (feature work)
Affected: 5 modules (direct + downstream dependencies)
Strictness: Strict (T1+T2, all test types)
```

## Decision Table
```
## Decision Table
| Component | Required | Rationale |
|-----------|----------|-----------|
| Functional | YES | Core functionality testing |
| Unit Tests | YES | Tier 1 critical path coverage |
| Integration | YES | Tests module interactions |
| Regression | YES | Prevents regressions in deps |
| Intelligent | YES | AI-generated edge case tests |
| Pytest Cov | YES | Coverage analysis |
| Health Chk | YES | Prevent collection errors |
| Solo-Dev | YES | Constitutional compliance |
```

## Incremental Test Scope
```
## Incremental Test Scope
Changed: router.py (3 lines)
Affected modules: auth.py, handlers.py, api.py, middleware.py (from codemap)
Test scope: 47 tests (vs 847 full suite)
Time saved: ~400 seconds
```

## Advanced Analytics

**Test Cache Stats:**
```
Cache hits: 12/47 tests (25.5%)
Time saved: 6.2 seconds
Cache size: 847 entries
```

**Flaky Tests Detected:**
```
test_concurrent_write (passed 7/10 runs) - FLAKY
  - Error: "Connection timeout" (3 times)
  - Error: "Lock acquisition failed" (2 times)
```

**Coverage Trend (Last 7 Days):**
```
Current: 84.0% (-2.3% from last week)

High-risk modules with declining coverage:
- router.py: 92% → 87% (-5%)
- auth.py: 89% → 82% (-7%)
```

**Slow Tests (>5s):**
```
1. test_full_integration (12.3s) - Consider splitting
2. test_database_migration (8.7s) - Could use fixtures
3. test_api_e2e (6.2s) - Mark with @pytest.mark.slow
```

**Grouped Failures:**
```
### Root Cause: Database connection timeout
**Affected tests:** 5

Tests:
- test_user_login
- test_auth_refresh
- test_api_call
- test_data_fetch
- test_background_job

**Sample error:**
sqlalchemy.exc.OperationalError: server closed the connection unexpectedly
```
