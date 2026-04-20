#!/usr/bin/env python3
"""Unit tests for context7_rate_limiter.py module.

This test suite verifies the Context7 shared rate limiter which provides:
- Shared rate limit tracking across all modernization tracks (Track 1, Track 2, EXPLORE)
- Batch query optimization (groups similar queries)
- Result caching across projects
- Rate limit detection and backoff trigger
- Graceful fallback to local version checking
- Never blocks EXPLORE phase (always returns results, never raises)

Run with: pytest P:/.claude/skills/code/tests/test_context7_rate_limiter.py -v
"""

import sys
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.context7_rate_limiter import (
    BatchQueryOptimizer,
    Context7RateLimiter,
    RateLimitTracker,
    reset_shared_state,
)


@pytest.fixture(autouse=True)
def reset_singleton_state():
    """Reset shared state before each test to prevent test pollution."""
    reset_shared_state()
    yield


class TestSharedRateLimitTracking:
    """Tests for shared rate limit tracking across multiple tracks."""

    def test_multiple_tracks_share_rate_limit_state(self):
        """
        Test that multiple modernization tracks share the same rate limit state.

        Given: Track 1, Track 2, and EXPLORE agents all create rate limiter instances
        When: Track 1 makes 5 queries, Track 2 makes 3 queries
        Then: Both see the same total query count (8) and coordinate queries
        """
        # Arrange
        tracker1 = RateLimitTracker()
        tracker2 = RateLimitTracker()

        # Act
        for i in range(5):
            tracker1.record_query("track1", "pandas")

        for i in range(3):
            tracker2.record_query("track2", "numpy")

        # Assert
        # Both trackers should see total of 8 queries (shared state via singleton)
        assert tracker1.get_total_queries() == 8
        assert tracker2.get_total_queries() == 8

    def test_rate_limit_threshold_shared_across_tracks(self):
        """
        Test that rate limit threshold is enforced across all tracks.

        Given: Rate limit threshold is 10 queries per minute
        When: Track 1 makes 8 queries, Track 2 attempts 3 more
        Then: Track 2's last query is blocked by shared rate limit
        """
        # Arrange
        limiter = Context7RateLimiter(queries_per_minute=10)

        # Act
        results = []
        for i in range(8):
            results.append(limiter.query_library("track1", "pandas"))

        # Track 2 should hit rate limit
        for i in range(3):
            results.append(limiter.query_library("track2", "numpy"))

        # Assert
        # First 10 should succeed, last 1 should be rate limited
        successful = sum(1 for r in results if r.get("rate_limited") is not True)
        assert successful == 10
        assert results[10].get("rate_limited") is True

    def test_explorer_phase_never_blocks(self):
        """
        Test that EXPLORE phase never blocks, always returns results.

        Given: Rate limit threshold exceeded
        When: EXPLORE agent makes a query
        Then: Query returns results (possibly degraded/fallback), never raises
        """
        # Arrange
        limiter = Context7RateLimiter(queries_per_minute=5, allow_explore_fallback=True)

        # Exhaust rate limit
        for i in range(10):
            limiter.query_library("track1", "library")

        # Act
        # EXPLORE query should not raise, should return with fallback flag
        result = limiter.query_library("EXPLORE", "django")

        # Assert
        # Should never raise, should return result with fallback indication
        assert result is not None
        assert "fallback" in result or "rate_limited" in result

    def test_rate_limit_reset_after_time_window(self):
        """
        Test that rate limit resets after time window expires.

        Given: Rate limit of 5 queries per minute is exhausted
        When: Wait 61 seconds and make another query
        Then: New query succeeds (rate limit reset)
        """
        # Arrange
        limiter = Context7RateLimiter(queries_per_minute=5, window_seconds=60)

        # Exhaust rate limit
        for i in range(5):
            limiter.query_library("track1", "library")

        # Act - wait for window to expire
        with patch("time.time", return_value=time.time() + 61):
            result = limiter.query_library("track1", "another-library")

        # Assert
        assert result.get("rate_limited") is not True


class TestBatchQueryOptimization:
    """Tests for batch query optimization."""

    def test_similar_queries_are_batched(self):
        """
        Test that similar queries are batched into single Context7 call.

        Given: Multiple tracks query "pandas" library
        When: All queries are made within batch window
        Then: Only one Context7 API call is made, results are cached
        """
        # Arrange
        optimizer = BatchQueryOptimizer(batch_window_ms=100)
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/pandas", "versions": ["2.0.0"]}

        # Act - make multiple similar queries quickly
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result1 = optimizer.query_library("track1", "pandas")
            result2 = optimizer.query_library("track2", "pandas")
            result3 = optimizer.query_library("EXPLORE", "pandas")

        # Assert
        # Should only call API once due to batching
        assert mock_api.call_count == 1
        assert result1["library_id"] == result2["library_id"] == result3["library_id"]

    def test_batch_window_groups_queries_by_time(self, mock_time):
        """
        Test that batch window determines how long to wait for grouping.

        Given: Batch window of 100ms
        When: Query 1 at t=0, query 2 at t=50ms, query 3 at t=150ms
        Then: Queries 1-2 batch together, query 3 is separate batch
        """
        # Arrange
        optimizer = BatchQueryOptimizer(batch_window_ms=100)
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/test", "versions": ["1.0.0"]}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result1 = optimizer.query_library("track1", "test")

            # Advance time by 50ms (within batch window)
            mock_time.tick(delta=timedelta(milliseconds=50))
            result2 = optimizer.query_library("track2", "test")

            # Advance time by 150ms (outside batch window)
            mock_time.tick(delta=timedelta(milliseconds=150))
            result3 = optimizer.query_library("track3", "test")

        # Assert
        # Should make 2 API calls (batch 1-2, then 3 separately)
        assert mock_api.call_count == 2

    def test_different_libraries_not_batched(self):
        """
        Test that different library queries are not batched together.

        Given: Queries for "pandas", "numpy", "django"
        When: All queries are made within batch window
        Then: Each library gets separate Context7 API call
        """
        # Arrange
        optimizer = BatchQueryOptimizer(batch_window_ms=100)
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/test", "versions": ["1.0.0"]}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            optimizer.query_library("track1", "pandas")
            optimizer.query_library("track2", "numpy")
            optimizer.query_library("track3", "django")

        # Assert
        # Should make 3 separate API calls (different libraries)
        assert mock_api.call_count == 3

    def test_batch_query_returns_same_result_to_all_requesters(self):
        """
        Test that batched query returns identical results to all requesters.

        Given: Three tracks batch query for "pytest"
        When: Batch query executes and returns results
        Then: All three tracks receive identical result data
        """
        # Arrange
        optimizer = BatchQueryOptimizer(batch_window_ms=100)
        expected_result = {"library_id": "/org/pytest", "versions": ["7.0.0", "8.0.0"]}
        mock_api = MagicMock(return_value=expected_result)

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result1 = optimizer.query_library("track1", "pytest")
            result2 = optimizer.query_library("track2", "pytest")
            result3 = optimizer.query_library("EXPLORE", "pytest")

        # Assert
        assert result1 == result2 == result3 == expected_result


class TestResultCachingAcrossProjects:
    """Tests for result caching across projects."""

    def test_cache_is_shared_across_tracks(self):
        """
        Test that cache is shared across all modernization tracks.

        Given: Track 1 queries "requests" library
        When: Track 2 queries "requests" library later
        Then: Track 2 uses cached result from Track 1, no API call
        """
        # Arrange
        limiter = Context7RateLimiter()
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/requests", "versions": ["2.28.0"]}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result1 = limiter.query_library("track1", "requests")
            result2 = limiter.query_library("track2", "requests")

        # Assert
        # Should only call API once (second query uses cache)
        assert mock_api.call_count == 1
        assert result1 == result2

    def test_cache_key_includes_library_name(self):
        """
        Test that cache key includes library name.

        Given: Cache has result for "pandas"
        When: Query for "numpy"
        Then: Cache miss, new API call made
        """
        # Arrange
        limiter = Context7RateLimiter()
        mock_api = MagicMock()
        mock_api.side_effect = [
            {"library_id": "/org/pandas", "versions": ["2.0.0"]},
            {"library_id": "/org/numpy", "versions": ["1.24.0"]},
        ]

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            limiter.query_library("track1", "pandas")
            limiter.query_library("track1", "numpy")

        # Assert
        # Should call API twice (different libraries)
        assert mock_api.call_count == 2

    def test_cache_can_be_cleared_globally(self):
        """
        Test that cache can be cleared globally for all tracks.

        Given: Cached results exist
        When: clear_cache() is called on any track
        Then: All tracks' cache is cleared, next queries hit API
        """
        # Arrange
        limiter1 = Context7RateLimiter()
        limiter2 = Context7RateLimiter()
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/test", "versions": ["1.0.0"]}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            # Populate cache
            limiter1.query_library("track1", "test")
            limiter1.query_library("track1", "test")  # Cache hit

            # Clear cache from limiter2
            limiter2.clear_cache()

            # Query again - should hit API
            limiter1.query_library("track1", "test")

        # Assert
        # Should call API twice (before cache clear, after cache clear)
        assert mock_api.call_count == 2

    def test_cache_persistence_across_multiple_projects(self):
        """
        Test that cache persists across multiple project queries.

        Given: Project A queries "fastapi"
        When: Project B queries "fastapi" in different modernization track
        Then: Project B uses Project A's cached result
        """
        # Arrange
        limiter = Context7RateLimiter()
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/fastapi", "versions": ["0.100.0"]}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            # Project A (Track 1)
            result_a = limiter.query_library("track1", "fastapi")

            # Project B (Track 2)
            result_b = limiter.query_library("track2", "fastapi")

            # Project C (EXPLORE)
            result_c = limiter.query_library("EXPLORE", "fastapi")

        # Assert
        # Should only call API once (shared across projects)
        assert mock_api.call_count == 1
        assert result_a == result_b == result_c


class TestRateLimitDetectionAndBackoff:
    """Tests for rate limit detection and backoff trigger."""

    def test_rate_limit_error_detected_from_api_response(self):
        """
        Test that rate limit error is detected from Context7 API response.

        Given: Context7 API returns rate_limit_exceeded error
        When: query_library() is called
        Then: Error is detected, backoff is triggered
        """
        # Arrange
        limiter = Context7RateLimiter()
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 5}

        # Act & Assert
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result = limiter.query_library("track1", "test")

        # Should detect rate limit and set flag
        assert result.get("rate_limited") is True
        assert result.get("retry_after") == 5

    def test_backoff_triggered_after_rate_limit(self):
        """
        Test that backoff is triggered after rate limit is hit.

        Given: Rate limit detected
        When: Next query is made within backoff period
        Then: Query is delayed until backoff expires
        """
        # Arrange
        limiter = Context7RateLimiter(initial_backoff=0.1, max_retries=0)
        mock_api = MagicMock()
        mock_api.side_effect = [
            {"error": "rate_limit_exceeded", "retry_after": 0.1},
            {"library_id": "/org/test", "versions": ["1.0.0"]},
        ]

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            start_time = time.time()
            result1 = limiter.query_library("track1", "test")  # Rate limited
            result2 = limiter.query_library("track1", "test")  # Retry with backoff
            elapsed = time.time() - start_time

        # Assert
        # Should have taken at least backoff time
        assert elapsed >= 0.1
        assert result1.get("rate_limited") is True
        assert result2.get("library_id") == "/org/test"

    def test_exponential_backoff_increments_on_repeated_limits(self):
        """
        Test that backoff increases exponentially on repeated rate limits.

        Given: Multiple consecutive rate limit errors
        When: Queries retry after each rate limit
        Then: Backoff time doubles each time (0.1s, 0.2s, 0.4s...)
        """
        # Arrange
        limiter = Context7RateLimiter(initial_backoff=0.1)
        mock_api = MagicMock()
        mock_api.side_effect = [
            {"error": "rate_limit_exceeded", "retry_after": 0.1},
            {"error": "rate_limit_exceeded", "retry_after": 0.1},
            {"library_id": "/org/test", "versions": ["1.0.0"]},
        ]

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            start_time = time.time()
            result = limiter.query_library("track1", "test")
            elapsed = time.time() - start_time

        # Assert
        # Should have taken at least 0.1 + 0.2 = 0.3s due to exponential backoff
        assert elapsed >= 0.3
        assert result.get("library_id") == "/org/test"

    def test_max_retries_respected_during_backoff(self):
        """
        Test that max retries is respected during backoff.

        Given: Max retries set to 3
        When: 4 consecutive rate limit errors occur
        Then: Returns error after 3 retries without infinite loop
        """
        # Arrange
        limiter = Context7RateLimiter(max_retries=3)
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 0.01}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            start_time = time.time()
            result = limiter.query_library("track1", "test")
            elapsed = time.time() - start_time

        # Assert
        # Should return error after max retries, not hang forever
        assert result.get("rate_limited") is True or result.get("error") is not None
        # Should have attempted retries (taken some time)
        assert elapsed >= 0.01


class TestGracefulFallbackToLocalVersionChecking:
    """Tests for graceful fallback to local version checking."""

    def test_fallback_triggered_when_rate_limit_hit(self):
        """
        Test that local version checking fallback is triggered on rate limit.

        Given: Rate limit exceeded, max retries hit
        When: Query is made
        Then: Falls back to local version checking instead of raising
        """
        # Arrange
        limiter = Context7RateLimiter(enable_fallback=True, max_retries=2)
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 1}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result = limiter.query_library("track1", "pandas")

        # Assert
        # Should return fallback result, not raise
        assert result is not None
        assert result.get("fallback") is True
        assert result.get("source") == "local"

    def test_fallback_returns_local_version_when_available(self):
        """
        Test that fallback returns local version when available.

        Given: Rate limit hit, local pandas installation is version 2.0.1
        When: Query for pandas falls back to local check
        Then: Returns local version 2.0.1
        """
        # Arrange
        limiter = Context7RateLimiter(enable_fallback=True)
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 1}

        # Act - mock local version check
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            with patch("utils.context7_rate_limiter._get_local_version", return_value="2.0.1"):
                result = limiter.query_library("track1", "pandas")

        # Assert
        assert result.get("fallback") is True
        assert result.get("local_version") == "2.0.1"

    def test_fallback_returns_graceful_degradation_when_unavailable(self):
        """
        Test that fallback returns graceful degradation when local unavailable.

        Given: Rate limit hit, library not installed locally
        When: Query falls back to local check
        Then: Returns indication that library is unavailable, not error
        """
        # Arrange
        limiter = Context7RateLimiter(enable_fallback=True)
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 1}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            with patch("utils.context7_rate_limiter._get_local_version", return_value=None):
                result = limiter.query_library("track1", "nonexistent-lib")

        # Assert
        # Should not raise, should return graceful degradation
        assert result.get("fallback") is True
        assert result.get("local_version") is None
        assert "unavailable" in result or "not_found" in result

    def test_fallback_disabled_when_flag_false(self):
        """
        Test that fallback is disabled when enable_fallback=False.

        Given: Rate limit hit, enable_fallback=False
        When: Query is made
        Then: Returns error without fallback attempt
        """
        # Arrange
        limiter = Context7RateLimiter(enable_fallback=False, max_retries=0)
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 1}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result = limiter.query_library("track1", "pandas")

        # Assert
        # Should not attempt fallback
        assert result.get("fallback") is not True
        assert result.get("rate_limited") is True or result.get("error") is not None


class TestNeverBlocksExplorePhase:
    """Tests that EXPLORE phase never blocks."""

    def test_explore_query_never_raises_exception(self):
        """
        Test that EXPLORE query never raises exception, even on errors.

        Given: Context7 API returns various errors
        When: EXPLORE agent makes query
        Then: Always returns result dict, never raises
        """
        # Arrange
        limiter = Context7RateLimiter(allow_explore_fallback=True)
        mock_api = MagicMock()
        mock_api.side_effect = Exception("Service unavailable")

        # Act & Assert
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            # Should not raise
            result = limiter.query_library("EXPLORE", "any-library")

        # Should always return a result
        assert result is not None
        assert isinstance(result, dict)

    def test_explore_always_returns_fallback_on_rate_limit(self):
        """
        Test that EXPLORE always returns fallback on rate limit.

        Given: Rate limit exceeded
        When: EXPLORE agent makes query
        Then: Returns fallback result immediately
        """
        # Arrange
        limiter = Context7RateLimiter(queries_per_minute=1, allow_explore_fallback=True)
        mock_api = MagicMock()
        mock_api.return_value = {"error": "rate_limit_exceeded", "retry_after": 60}

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result = limiter.query_library("EXPLORE", "test-lib")

        # Assert
        # Should return fallback, not wait or raise
        assert result is not None
        assert result.get("fallback") is True or result.get("rate_limited") is True

    def test_explore_returns_partial_results_on_error(self):
        """
        Test that EXPLORE returns partial results on API error.

        Given: Context7 API returns malformed response
        When: EXPLORE agent makes query
        Then: Returns partial result with error flag
        """
        # Arrange
        limiter = Context7RateLimiter(allow_explore_fallback=True)
        mock_api = MagicMock()
        mock_api.return_value = {"incomplete": "response"}  # Malformed

        # Act
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result = limiter.query_library("EXPLORE", "test-lib")

        # Assert
        # Should return partial result, not raise
        assert result is not None
        assert isinstance(result, dict)

    def test_explore_phase_bypasses_rate_limit_when_critical(self):
        """
        Test that EXPLORE can bypass rate limit when configured as critical.

        Given: Rate limit exceeded
        When: EXPLORE marked as critical_phase=True makes query
        Then: Query proceeds even at cost of exceeding rate limit
        """
        # Arrange
        limiter = Context7RateLimiter(queries_per_minute=1, allow_explore_bypass=True)
        mock_api = MagicMock()
        mock_api.return_value = {"library_id": "/org/critical", "versions": ["1.0.0"]}

        # Act
        # Exhaust rate limit
        limiter.query_library("track1", "lib1")

        # EXPLORE critical query should bypass
        with patch("utils.context7_rate_limiter._call_context7_api", mock_api):
            result = limiter.query_library("EXPLORE", "critical-lib", critical_phase=True)

        # Assert
        # Should have bypassed rate limit and gotten result
        assert result.get("library_id") == "/org/critical"


class TestSingletonPattern:
    """Tests for singleton pattern ensuring shared state."""

    def test_rate_limiter_is_singleton(self):
        """
        Test that Context7RateLimiter implements singleton pattern.

        Given: Multiple calls to Context7RateLimiter()
        When: Instances are created
        Then: All instances share the same underlying state
        """
        # Arrange & Act
        limiter1 = Context7RateLimiter()
        limiter2 = Context7RateLimiter()

        # Act - record query via limiter1
        tracker1 = RateLimitTracker()
        tracker1.record_query("track1", "test")

        # Assert
        # Both instances should see same query count
        assert limiter1.get_total_queries() == limiter2.get_total_queries()

    def test_singleton_state_persists_across_imports(self):
        """
        Test that singleton state persists across module imports.

        Given: Module imported in different places
        When: State is modified in one place
        Then: Changes are visible in all imports
        """
        # This test verifies that the singleton pattern works correctly
        # In practice, this would test importing from different modules
        # For now, we verify the pattern is in place

        # Arrange
        limiter1 = Context7RateLimiter()
        limiter2 = Context7RateLimiter()

        # Act
        id1 = id(limiter1._get_shared_state())
        id2 = id(limiter2._get_shared_state())

        # Assert
        # Should be same object (same id)
        assert id1 == id2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
