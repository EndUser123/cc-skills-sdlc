"""Cache optimization tests for PrerequisiteAnalyzer._matches_any().

These tests verify PERF-005: Cache key optimization to use only text as key,
not (text, patterns) tuple, since patterns are module constants.

PROBLEM: Current implementation uses @lru_cache with (text, patterns) as key.
Since patterns are module constants, checking the same text against different
pattern types creates duplicate cache entries.

EXPECTED: After optimization, cache key should be text only.

Run with: pytest P:/.claude/skills/arch/tests/test_prerequisite_cache.py -v

TDD RED Phase: Tests FAIL because we expect optimized behavior.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from prerequisite_analyzer import (
    PrerequisiteAnalyzer, 
    OPTIMIZATION_PATTERNS, 
    PRD_PATTERNS, 
    DEBUG_PATTERNS
)


class TestCacheKeyOptimizationForEfficiency:
    """Tests for cache key to use text only (not patterns tuple)."""

    def test_cache_size_reduced_with_text_only_key(self):
        """Test that checking same text against 3 patterns uses 1 cache entry.
        
        CURRENT: Creates 3 cache entries (wasteful).
        OPTIMIZED: Should create 1 cache entry (efficient).
        
        This test FAILS with current implementation.
        """
        PrerequisiteAnalyzer._matches_any.cache_clear()
        text = "design authentication system"
        
        PrerequisiteAnalyzer._matches_any(text, OPTIMIZATION_PATTERNS)
        PrerequisiteAnalyzer._matches_any(text, PRD_PATTERNS)
        PrerequisiteAnalyzer._matches_any(text, DEBUG_PATTERNS)
        
        cache_info = PrerequisiteAnalyzer._matches_any.cache_info()
        
        # FAILS with current implementation (currsize=3)
        # PASSES after optimization (currsize=1)
        assert cache_info.currsize == 1, (
            f"After optimization, same text against different patterns "
            f"should use 1 cache entry. Got {cache_info.currsize}."
        )

    def test_cache_efficient_for_repeated_analyze_calls(self):
        """Test that analyze() calls with same query are cache-efficient."""
        PrerequisiteAnalyzer._matches_any.cache_clear()
        query = "improve authentication system"
        
        result1 = PrerequisiteAnalyzer.analyze(query)
        cache_info_after_first = PrerequisiteAnalyzer._matches_any.cache_info()
        
        result2 = PrerequisiteAnalyzer.analyze(query)
        cache_info_after_second = PrerequisiteAnalyzer._matches_any.cache_info()
        
        assert result1 == result2
        
        # After first analyze: 4 cache entries (one per pattern type)
        assert cache_info_after_first.currsize == 4
        
        # After second: should be 4 (no new entries) with hits
        assert cache_info_after_second.currsize == 4
        
        # CRITICAL: Second call should have cache hits
        new_hits = cache_info_after_second.hits - cache_info_after_first.hits
        assert new_hits >= 4, (
            f"Second analyze() should hit cache. Got {new_hits} hits, expected >=4."
        )


class TestCurrentCacheInefficiency:
    """Tests that DOCUMENT current wasteful behavior."""

    def test_duplicate_entries_for_same_text(self):
        """Test that current implementation creates duplicate cache entries.
        
        CHARACTERIZATION test: documents what code DOES, not SHOULD do.
        PASSES with current implementation, FAILS after optimization.
        """
        PrerequisiteAnalyzer._matches_any.cache_clear()
        text = "optimize database"
        
        PrerequisiteAnalyzer._matches_any(text, OPTIMIZATION_PATTERNS)
        PrerequisiteAnalyzer._matches_any(text, PRD_PATTERNS)
        
        cache_info = PrerequisiteAnalyzer._matches_any.cache_info()
        
        # OPTIMIZED: 1 entry (text-only cache key)
        assert cache_info.currsize == 1, (
            f"After optimization, same text against different patterns "
            f"should use 1 cache entry. Got {cache_info.currsize}."
        )

    def test_cache_hit_with_identical_call(self):
        """Test that identical calls (same text, same patterns) hit cache."""
        PrerequisiteAnalyzer._matches_any.cache_clear()
        
        result1 = PrerequisiteAnalyzer._matches_any("improve x", OPTIMIZATION_PATTERNS)
        cache_info_1 = PrerequisiteAnalyzer._matches_any.cache_info()
        
        result2 = PrerequisiteAnalyzer._matches_any("improve x", OPTIMIZATION_PATTERNS)
        cache_info_2 = PrerequisiteAnalyzer._matches_any.cache_info()
        
        assert result1 == result2 == True
        assert cache_info_1.misses == 1
        hits = cache_info_2.hits - cache_info_1.hits
        assert hits == 1


class TestCacheCapacity:
    """Tests for cache capacity."""

    def test_maxsize_256(self):
        """Test that cache maxsize is 256."""
        cache_info = PrerequisiteAnalyzer._matches_any.cache_info()
        assert cache_info.maxsize == 256

    def test_cache_capacity_for_unique_texts(self):
        """Test that 256 different texts fit in cache."""
        PrerequisiteAnalyzer._matches_any.cache_clear()
        
        for i in range(256):
            text = f"query number {i}"
            PrerequisiteAnalyzer._matches_any(text, OPTIMIZATION_PATTERNS)
        
        cache_info = PrerequisiteAnalyzer._matches_any.cache_info()
        assert cache_info.currsize == 256


class TestPatternConstants:
    """Tests verifying patterns are module-level constants."""

    def test_patterns_are_tuples(self):
        """Test that pattern constants are tuples."""
        assert isinstance(OPTIMIZATION_PATTERNS, tuple)
        assert isinstance(PRD_PATTERNS, tuple)
        assert isinstance(DEBUG_PATTERNS, tuple)

    def test_patterns_not_empty(self):
        """Test that pattern tuples contain patterns."""
        assert len(OPTIMIZATION_PATTERNS) > 0
        assert len(PRD_PATTERNS) > 0
        assert len(DEBUG_PATTERNS) > 0


class TestIndividualCacheBehavior:
    """
    TEST-ARCH-010: Tests for individual cached method behavior.

    Verifies cache correctness for _matches_optimization, _matches_prd,
    _matches_debug, and related cached methods.
    """

    def test_matches_optimization_cache_hits_on_repeated_calls(self):
        """Test that _matches_optimization cache hits on repeated calls."""
        PrerequisiteAnalyzer._matches_optimization.cache_clear()

        # First call - should miss
        result1 = PrerequisiteAnalyzer._matches_optimization("improve memory")
        cache_info_1 = PrerequisiteAnalyzer._matches_optimization.cache_info()

        # Second call - should hit
        result2 = PrerequisiteAnalyzer._matches_optimization("improve memory")
        cache_info_2 = PrerequisiteAnalyzer._matches_optimization.cache_info()

        assert result1 == result2
        assert cache_info_1.misses == 1, "First call should be a cache miss"
        assert cache_info_2.hits >= 1, "Second call should be a cache hit"

    def test_matches_prd_cache_hits_on_repeated_calls(self):
        """Test that _matches_prd cache hits on repeated calls."""
        PrerequisiteAnalyzer._matches_prd.cache_clear()

        # First call - should miss
        result1 = PrerequisiteAnalyzer._matches_prd("write user stories")
        cache_info_1 = PrerequisiteAnalyzer._matches_prd.cache_info()

        # Second call - should hit
        result2 = PrerequisiteAnalyzer._matches_prd("write user stories")
        cache_info_2 = PrerequisiteAnalyzer._matches_prd.cache_info()

        assert result1 == result2
        assert cache_info_1.misses == 1, "First call should be a cache miss"
        assert cache_info_2.hits >= 1, "Second call should be a cache hit"

    def test_matches_debug_cache_hits_on_repeated_calls(self):
        """Test that _matches_debug cache hits on repeated calls."""
        PrerequisiteAnalyzer._matches_debug.cache_clear()

        # First call - should miss
        result1 = PrerequisiteAnalyzer._matches_debug("debug the crash")
        cache_info_1 = PrerequisiteAnalyzer._matches_debug.cache_info()

        # Second call - should hit
        result2 = PrerequisiteAnalyzer._matches_debug("debug the crash")
        cache_info_2 = PrerequisiteAnalyzer._matches_debug.cache_info()

        assert result1 == result2
        assert cache_info_1.misses == 1, "First call should be a cache miss"
        assert cache_info_2.hits >= 1, "Second call should be a cache hit"

    def test_cache_clear_works_for_all_cached_methods(self):
        """Test that cache_clear() empties all caches."""
        # Add some entries to each cache
        PrerequisiteAnalyzer._matches_optimization("test1")
        PrerequisiteAnalyzer._matches_prd("test2")
        PrerequisiteAnalyzer._matches_debug("test3")

        # Verify caches have entries
        assert PrerequisiteAnalyzer._matches_optimization.cache_info().currsize > 0
        assert PrerequisiteAnalyzer._matches_prd.cache_info().currsize > 0
        assert PrerequisiteAnalyzer._matches_debug.cache_info().currsize > 0

        # Clear all caches
        PrerequisiteAnalyzer._matches_optimization.cache_clear()
        PrerequisiteAnalyzer._matches_prd.cache_clear()
        PrerequisiteAnalyzer._matches_debug.cache_clear()

        # Verify caches are empty
        assert PrerequisiteAnalyzer._matches_optimization.cache_info().currsize == 0
        assert PrerequisiteAnalyzer._matches_prd.cache_info().currsize == 0
        assert PrerequisiteAnalyzer._matches_debug.cache_info().currsize == 0

    def test_cache_size_is_bounded(self):
        """Test that cache size is bounded by maxsize."""
        PrerequisiteAnalyzer._matches_optimization.cache_clear()

        maxsize = PrerequisiteAnalyzer._matches_optimization.cache_info().maxsize
        assert maxsize == 256, "Cache maxsize should be 256"

        # Fill cache with unique values
        for i in range(300):  # More than maxsize
            PrerequisiteAnalyzer._matches_optimization(f"text {i}")

        cache_info = PrerequisiteAnalyzer._matches_optimization.cache_info()
        # Cache should not exceed maxsize
        assert cache_info.currsize <= maxsize, (
            f"Cache size {cache_info.currsize} should not exceed maxsize {maxsize}"
        )

    def test_different_inputs_create_different_cache_entries(self):
        """Test that different inputs create separate cache entries."""
        PrerequisiteAnalyzer._matches_optimization.cache_clear()

        # Call with different inputs
        PrerequisiteAnalyzer._matches_optimization("improve memory")
        PrerequisiteAnalyzer._matches_optimization("optimize cpu")
        PrerequisiteAnalyzer._matches_optimization("reduce latency")

        cache_info = PrerequisiteAnalyzer._matches_optimization.cache_info()
        # Should have 3 separate cache entries
        assert cache_info.currsize == 3, (
            f"Different inputs should create separate cache entries. Got {cache_info.currsize}"
        )
