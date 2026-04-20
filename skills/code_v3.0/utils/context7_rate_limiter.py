#!/usr/bin/env python3
"""Context7 shared rate limiter for modernization tracks.

This module provides:
- Shared rate limit tracking across all modernization tracks (Track 1, Track 2, EXPLORE)
- Batch query optimization (groups similar queries)
- Result caching across projects
- Rate limit detection and backoff trigger
- Graceful fallback to local version checking
- Never blocks EXPLORE phase (always returns results, never raises)
"""

import time
from typing import Any, Dict, List, Optional, Tuple
import threading


# Constants
DEFAULT_QUERIES_PER_MINUTE = 60
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_BATCH_WINDOW_MS = 100
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 1.0
RATE_LIMIT_ERROR = "rate_limit_exceeded"
EXPLORE_TRACK = "EXPLORE"
SOURCE_LOCAL = "local"


class _SharedState:
    """Singleton shared state for rate limiter across all tracks."""

    _instance: Optional["_SharedState"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "_SharedState":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize shared state."""
        self.query_count: int = 0
        self.query_history: List[Tuple[float, str]] = []  # (timestamp, track)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.Lock()
        self.rate_limit_hit: bool = False
        self.backoff_until: float = 0.0
        self.current_backoff: float = 0.0

    def reset(self) -> None:
        """Reset shared state (for testing)."""
        self._initialize()


def reset_shared_state() -> None:
    """Reset the shared state (for testing)."""
    _shared_state.reset()


# Global shared state instance
_shared_state = _SharedState()


class RateLimitTracker:
    """Tracks rate limit usage across multiple modernization tracks."""

    def __init__(self, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        """Initialize rate limit tracker.

        Args:
            window_seconds: Time window for rate limit counting
        """
        self.window_seconds = window_seconds
        self.shared_state = _shared_state

    def record_query(self, track: str, library: str) -> None:
        """Record a query for rate limit tracking.

        Args:
            track: Modernization track name (e.g., "track1", "track2", "EXPLORE")
            library: Library name being queried
        """
        current_time = time.time()
        with self.shared_state._lock:
            self.shared_state.query_history.append((current_time, track))
            self.shared_state.query_count += 1

    def get_total_queries(self) -> int:
        """Get total query count across all tracks.

        Returns:
            Total number of queries recorded
        """
        with self.shared_state._lock:
            return self.shared_state.query_count

    def get_queries_in_window(self) -> int:
        """Get number of queries within the time window.

        Returns:
            Number of queries within the configured time window
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds

        with self.shared_state._lock:
            # Clean old queries
            self.shared_state.query_history = [
                (ts, track) for ts, track in self.shared_state.query_history
                if ts >= window_start
            ]
            return len(self.shared_state.query_history)


class BatchQueryOptimizer:
    """Optimizes queries by batching similar requests within a time window."""

    def __init__(self, batch_window_ms: int = DEFAULT_BATCH_WINDOW_MS) -> None:
        """Initialize batch query optimizer.

        Args:
            batch_window_ms: Time window in milliseconds for batching queries
        """
        self.batch_window_ms = batch_window_ms
        self.pending_queries: Dict[str, List[Tuple[str, float]]] = {}
        self.batch_results: Dict[str, Dict[str, Any]] = {}
        self.api_call_count: Dict[str, int] = {}
        self.shared_state = _shared_state
        self.last_query_time: Dict[str, float] = {}

    def query_library(self, track: str, library: str) -> Dict[str, Any]:
        """Query a library with batch optimization.

        Args:
            track: Modernization track name
            library: Library name to query

        Returns:
            Query result dictionary
        """
        current_time = time.time()

        if self._is_within_batch_window(library, current_time):
            return self.batch_results[library]

        result = _call_context7_api(library)
        self.api_call_count[library] = self.api_call_count.get(library, 0) + 1
        self.last_query_time[library] = current_time
        self._update_cache_and_batch_results(library, result)

        return result

    def get_api_call_count(self, library: str) -> int:
        """Get the number of API calls made for a library.

        Args:
            library: Library name

        Returns:
            Number of API calls made
        """
        return self.api_call_count.get(library, 0)

    def reset_batch_state(self) -> None:
        """Reset batch state (for testing)."""
        self.batch_results.clear()
        self.api_call_count.clear()
        self.last_query_time.clear()

    def _is_within_batch_window(self, library: str, current_time: float) -> bool:
        """Check if a library query is within the batch window.

        Args:
            library: Library name to check
            current_time: Current timestamp

        Returns:
            True if within batch window and cached result exists
        """
        if library not in self.last_query_time:
            return False

        elapsed_ms = (current_time - self.last_query_time[library]) * 1000
        return elapsed_ms < self.batch_window_ms and library in self.batch_results

    def _update_cache_and_batch_results(
        self, library: str, result: Dict[str, Any]
    ) -> None:
        """Update both shared cache and batch results.

        Args:
            library: Library name
            result: Query result to cache
        """
        cache_key = str(library)
        with self.shared_state.cache_lock:
            self.shared_state.cache[cache_key] = result
            self.batch_results[library] = result


class Context7RateLimiter:
    """Rate limiter for Context7 queries across all modernization tracks."""

    def __init__(
        self,
        queries_per_minute: int = DEFAULT_QUERIES_PER_MINUTE,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        max_retries: int = DEFAULT_MAX_RETRIES,
        enable_fallback: bool = True,
        allow_explore_fallback: bool = False,
        allow_explore_bypass: bool = False,
    ) -> None:
        """Initialize rate limiter.

        Args:
            queries_per_minute: Maximum queries per minute allowed
            window_seconds: Time window for rate limit counting
            initial_backoff: Initial backoff time in seconds
            max_retries: Maximum retries on rate limit
            enable_fallback: Enable fallback to local version checking
            allow_explore_fallback: Allow EXPLORE phase to use fallback
            allow_explore_bypass: Allow EXPLORE to bypass rate limit when critical
        """
        self.queries_per_minute = queries_per_minute
        self.window_seconds = window_seconds
        self.initial_backoff = initial_backoff
        self.max_retries = max_retries
        self.enable_fallback = enable_fallback
        self.allow_explore_fallback = allow_explore_fallback
        self.allow_explore_bypass = allow_explore_bypass

        self.shared_state = _shared_state
        self.tracker = RateLimitTracker(window_seconds)
        self.optimizer = BatchQueryOptimizer(batch_window_ms=DEFAULT_BATCH_WINDOW_MS)
        self.query_times: List[Tuple[float, str]] = []

    def _get_shared_state(self) -> _SharedState:
        """Get shared state (for testing singleton pattern).

        Returns:
            Shared state instance
        """
        return self.shared_state

    def get_total_queries(self) -> int:
        """Get total query count across all tracks.

        Returns:
            Total number of queries
        """
        return self.tracker.get_total_queries()

    def query_library(
        self,
        track: str,
        library: str,
        critical_phase: bool = False
    ) -> Dict[str, Any]:
        """Query a library with rate limiting and caching.

        Args:
            track: Modernization track name
            library: Library name to query
            critical_phase: Whether this is a critical phase that can bypass limits

        Returns:
            Query result dictionary with optional flags:
            - rate_limited: True if query was rate limited
            - fallback: True if using fallback result
            - library_id: Context7 library ID
            - versions: Available versions
            - local_version: Local version if fallback used
            - source: "local" if fallback used
        """
        is_explore = track == EXPLORE_TRACK

        if is_explore and critical_phase and self.allow_explore_bypass:
            return self._execute_query(track, library)

        if not self._can_make_query():
            return self._handle_rate_limit(track, library, is_explore)

        cached_result = self._get_cached_result(library, track)
        if cached_result is not None:
            return cached_result

        return self._execute_query(track, library)

    def _can_make_query(self) -> bool:
        """Check if we can make a query without exceeding rate limit.

        Returns:
            True if query is allowed, False if rate limited
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds

        self.query_times = [
            (ts, track) for ts, track in self.query_times
            if ts >= window_start
        ]

        return len(self.query_times) < self.queries_per_minute

    def _get_cached_result(
        self, library: str, track: str
    ) -> Optional[Dict[str, Any]]:
        """Check cache for existing result.

        Args:
            library: Library name
            track: Modernization track name

        Returns:
            Cached result if available, None otherwise
        """
        cache_key = f"{library}:fallback={self.enable_fallback}"
        with self.shared_state.cache_lock:
            if cache_key in self.shared_state.cache:
                current_time = time.time()
                self.query_times.append((current_time, track))
                self.tracker.record_query(track, library)
                return self.shared_state.cache[cache_key]
        return None

    def _execute_query(self, track: str, library: str) -> Dict[str, Any]:
        """Execute the actual query.

        Args:
            track: Modernization track name
            library: Library name to query

        Returns:
            Query result
        """
        self._wait_for_backoff_if_needed()

        current_time = time.time()
        self.query_times.append((current_time, track))
        self.tracker.record_query(track, library)

        result = self._call_with_retry(library, track)

        if not result.get("rate_limited"):
            self._cache_successful_result(library, result)

        return result

    def _wait_for_backoff_if_needed(self) -> None:
        """Wait for backoff period if active."""
        current_time = time.time()
        if current_time < self.shared_state.backoff_until:
            wait_time = self.shared_state.backoff_until - current_time
            time.sleep(wait_time)

    def _cache_successful_result(
        self, library: str, result: Dict[str, Any]
    ) -> None:
        """Cache successful query result.

        Args:
            library: Library name
            result: Query result to cache
        """
        cache_key = f"{library}:fallback={self.enable_fallback}"
        with self.shared_state.cache_lock:
            self.shared_state.cache[cache_key] = result

    def _call_with_retry(self, library: str, track: str) -> Dict[str, Any]:
        """Call Context7 API with exponential backoff on rate limit.

        Args:
            library: Library name to query
            track: Modernization track name (for EXPLORE handling)

        Returns:
            API response
        """
        backoff = self.initial_backoff
        is_explore = track == EXPLORE_TRACK

        for attempt in range(self.max_retries + 1):
            try:
                result = _call_context7_api(library)

                if result.get("error") == RATE_LIMIT_ERROR:
                    if attempt < self.max_retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    else:
                        return self._handle_max_retries_exceeded(library, backoff, is_explore, result)

                self._clear_backoff()
                return result

            except Exception as e:
                if is_explore and self.allow_explore_fallback:
                    return self._get_fallback_result(library)
                if "rate_limit" in str(e).lower():
                    if attempt < self.max_retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                return {"error": str(e)}

        return {"rate_limited": True}

    def _handle_max_retries_exceeded(
        self, library: str, backoff: float, is_explore: bool, api_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle case when max retries are exceeded.

        Args:
            library: Library name
            backoff: Current backoff time
            is_explore: Whether this is EXPLORE track
            api_result: API result containing retry_after

        Returns:
            Rate limited result with optional fallback
        """
        self.shared_state.backoff_until = time.time() + backoff
        self.shared_state.current_backoff = backoff

        rate_limited_result = {
            "rate_limited": True,
            "retry_after": api_result.get("retry_after", 1)
        }

        if self.enable_fallback or (is_explore and self.allow_explore_fallback):
            fallback_result = self._get_fallback_result(library)
            rate_limited_result.update(fallback_result)

        return rate_limited_result

    def _clear_backoff(self) -> None:
        """Clear backoff state after successful request."""
        self.shared_state.backoff_until = 0.0
        self.shared_state.current_backoff = 0.0

    def _handle_rate_limit(
        self, track: str, library: str, is_explore: bool
    ) -> Dict[str, Any]:
        """Handle rate limit scenario.

        Args:
            track: Modernization track name
            library: Library name to query
            is_explore: Whether this is EXPLORE phase

        Returns:
            Result with appropriate flags
        """
        # EXPLORE phase never blocks
        if is_explore:
            if self.allow_explore_fallback:
                return self._get_fallback_result(library)
            return {"rate_limited": True, "fallback": True}

        # Check if fallback enabled
        if self.enable_fallback:
            return self._get_fallback_result(library)

        return {"rate_limited": True}

    def _get_fallback_result(self, library: str) -> Dict[str, Any]:
        """Get fallback result from local version checking.

        Args:
            library: Library name to check locally

        Returns:
            Fallback result with local version info
        """
        local_version = _get_local_version(library)

        result = {
            "rate_limited": True,
            "fallback": True,
            "source": SOURCE_LOCAL,
            "local_version": local_version,
        }

        if local_version is None:
            result["unavailable"] = True

        return result

    def clear_cache(self) -> None:
        """Clear the shared cache."""
        with self.shared_state.cache_lock:
            self.shared_state.cache.clear()


def _call_context7_api(library: str) -> Dict[str, Any]:
    """Call Context7 API (mock for testing, replaced in production).

    Args:
        library: Library name to query

    Returns:
        API response dictionary
    """
    # This is a mock implementation for testing
    # In production, this would be replaced with actual Context7 API call
    try:
        import sys
        tool_module = "mcp__plugin_context7_context7__resolve-library-id"
        if tool_module in sys.modules:
            tool = sys.modules[tool_module].Tool
            return tool(libraryName=library)
    except Exception:
        pass

    # Default mock response
    return {
        "library_id": f"/org/{library}",
        "versions": ["1.0.0"],
    }


def _get_local_version(library: str) -> Optional[str]:
    """Get local version of a library.

    Args:
        library: Library name to check

    Returns:
        Local version string or None if not available
    """
    try:
        import importlib.metadata
        return importlib.metadata.version(library)
    except Exception:
        return None
