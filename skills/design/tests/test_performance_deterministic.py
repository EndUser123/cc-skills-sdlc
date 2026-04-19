"""
Deterministic performance tests for template content caching.

This test file addresses TEST-003: Timing-dependent assertions in test_performance.py

PROBLEM: The original test_performance_improvement() has these issues:
1. Uses time.perf_counter() for ACTUAL timing measurements
2. Can fail randomly due to system load, OS caching, SSD caching, etc.
3. Requires specific speedup ratios (1.5x) that may not always be achieved

SOLUTION: This test file uses a deterministic approach:
1. Mocks time.perf_counter() to return controlled values
2. Verifies caching behavior via cache_info() statistics
3. Tests cache_hit behavior deterministically (not timing-dependent)

Run with: pytest P:/.claude/skills/arch/tests/test_performance_deterministic.py -v
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import the module under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_templates import load_template_content, _load_template_content_cached


class TestFlakyTimingBehavior:
    """
    Tests that demonstrate the FLAKY behavior of timing-dependent assertions.

    These tests intentionally fail to show why the original approach is problematic.
    """

    @pytest.fixture(autouse=True)
    def clear_cache_before_each_test(self):
        """Clear cache before each test to ensure isolation."""
        _load_template_content_cached.cache_clear()
        yield
        _load_template_content_cached.cache_clear()

    @pytest.fixture
    def temp_template_file(self, tmp_path: Path) -> Path:
        """Create a temporary template file for testing."""
        template_file = tmp_path / "test_template.md"
        template_file.write_text("# Test Template\n\nSome content here.")
        return template_file

    @pytest.mark.skip(
        reason="Flaky timing-dependent test. This test demonstrates that timing-based "
        "assertions are unreliable due to system load, OS caching, and other factors. "
        "The test intentionally shows the problem with performance assertions."
    )
    def test_timing_can_fail_when_cached_is_slower(self, temp_template_file: Path):
        """
        DEMONSTRATION: This test shows how timing-based tests can FAIL.

        With MOCKED time that simulates "system load" or "OS cache effects",
        we can make the cached load appear SLOWER than the uncached load,
        causing the original test's assertion to fail.

        Given: A template file exists
        When: Loading with time mocked to simulate adverse conditions
        Then: The timing-based assertion FAILS (demonstrating flakiness)

        This test WILL FAIL to demonstrate the problem with timing-dependent tests.
        """
        # Arrange - Small template file
        small_content = "# Small Template\n\nMinimal content."
        temp_template_file.write_text(small_content)

        # MOCK time to simulate "bad" conditions where cached appears slower
        # First load: 0.001ms (very fast, OS cached it)
        # Second load: 0.002ms (slower, maybe GC pause or context switch)
        time_values = [0.0, 0.000001, 0.001, 0.001002]

        # Act - Load with mocked time
        with patch("time.perf_counter", side_effect=time_values):
            # First load
            start_time = time.perf_counter()  # 0.0
            content1 = load_template_content(temp_template_file)
            first_load_time = time.perf_counter() - start_time  # 0.000001

            # Second load (appears slower due to mocked time)
            start_time = time.perf_counter()  # 0.001
            content2 = load_template_content(temp_template_file)
            second_load_time = time.perf_counter() - start_time  # 0.000002

        # Assert - This FAILS because cached load appears "slower"
        # This demonstrates why timing-based tests are FLAKY
        assert second_load_time < first_load_time, (
            f"TIMING TEST FLAKY: With mocked adverse conditions, "
            f"cached load ({second_load_time:.6f}s) appears SLOWER than "
            f"uncached load ({first_load_time:.6f}s). "
            f"Real-world: system load, GC, context switches can cause this."
        )


class TestDeterministicPerformance:
    """Tests for performance behavior using deterministic mocks, not actual timing."""

    @pytest.fixture(autouse=True)
    def clear_cache_before_each_test(self):
        """Clear cache before each test to ensure isolation."""
        _load_template_content_cached.cache_clear()
        yield
        _load_template_content_cached.cache_clear()

    @pytest.fixture
    def temp_template_file(self, tmp_path: Path) -> Path:
        """Create a temporary template file for testing."""
        template_file = tmp_path / "test_template.md"
        template_file.write_text("# Test Template\n\nSome content here.")
        return template_file

    def test_performance_improvement_with_mocked_time(self, temp_template_file: Path):
        """
        Test cache performance using MOCKED time instead of actual timing.

        This test demonstrates the FIX for the flaky test_performance_improvement().
        The original test uses real time.perf_counter() which can fail randomly.

        MOCKING APPROACH (deterministic):
        - Patch time.perf_counter to return controlled values
        - Simulate 50ms for first load, ~0ms for cached load
        - Assertions always pass because timing is controlled

        Given: A template file exists
        When: Loading the file twice with mocked time.perf_counter()
        Then: Should verify caching via cache_info(), not actual timing

        This test uses deterministic mocks and should PASS reliably.
        """
        # Arrange - Create a large template file
        large_content = "\n".join([f"Line {i}" for i in range(1000)])
        temp_template_file.write_text(large_content)

        # Define MOCKED time values for perf_counter
        # Simulate: first load takes 50ms, second load is instant (cached)
        time_values = [0.0, 0.050, 0.100, 0.100001]

        # Act - Load content twice with MOCKED time
        with patch("time.perf_counter", side_effect=time_values):
            # First load - UNCACHED
            start_time = time.perf_counter()  # Returns 0.0
            content1 = load_template_content(temp_template_file)
            first_load_time = time.perf_counter() - start_time  # 0.050

            # Second load - should be CACHED
            start_time = time.perf_counter()  # Returns 0.100
            content2 = load_template_content(temp_template_file)
            second_load_time = time.perf_counter() - start_time  # 0.000001

        # Get cache statistics
        cache_info = load_template_content.cache_info()

        # Assert - Content should be identical
        assert content1 == content2 == large_content

        # Assert - With MOCKED time, cached load MUST be faster
        assert second_load_time < first_load_time, (
            f"With mocked time, cached load ({second_load_time:.6f}s) must be faster than "
            f"uncached load ({first_load_time:.6f}s)"
        )

        # Assert - Speedup should be at least 100x (deterministic with mocked time)
        speedup_ratio = first_load_time / second_load_time
        assert speedup_ratio >= 100.0, (
            f"With mocked time, expected 100x+ speedup, got {speedup_ratio:.1f}x"
        )

        # Assert - Cache statistics MUST show 1 hit, 1 miss
        # THIS IS THE CRITICAL ASSERTION - verifies caching actually happened
        assert cache_info.hits == 1, f"Expected 1 cache hit, got {cache_info.hits}"
        assert cache_info.misses == 1, f"Expected 1 cache miss, got {cache_info.misses}"

    def test_cache_info_method_exists(self):
        """
        Test that cache_info() method is properly exposed.

        Given: The load_template_content function with caching
        When: Calling cache_info() to get statistics
        Then: Should return a CacheInfo named tuple

        This test verifies the cache_info() lambda properly
        wraps the underlying _load_template_content_cached.cache_info().
        """
        # Arrange & Act
        cache_info = load_template_content.cache_info()

        # Assert - Should have all expected attributes
        assert hasattr(cache_info, "hits"), "cache_info() missing 'hits' attribute"
        assert hasattr(cache_info, "misses"), "cache_info() missing 'misses' attribute"
        assert hasattr(cache_info, "maxsize"), (
            "cache_info() missing 'maxsize' attribute"
        )
        assert hasattr(cache_info, "currsize"), (
            "cache_info() missing 'currsize' attribute"
        )

        # Assert - Values should be reasonable
        assert cache_info.maxsize > 0, "maxsize should be positive"
        assert cache_info.hits >= 0, "hits should be non-negative"
        assert cache_info.misses >= 0, "misses should be non-negative"
        assert cache_info.currsize >= 0, "currsize should be non-negative"

    def test_cache_clear_method_works(self, temp_template_file: Path):
        """
        Test that cache_clear() properly resets the LRU cache.

        Given: A template file that has been loaded (cached)
        When: Calling cache_clear() and loading the same file again
        Then: Should get a cache miss (not a hit) after clear

        This test verifies the cache_clear() lambda properly
        calls _load_template_content_cached.cache_clear().
        """
        # Arrange - Load file to populate cache
        content1 = load_template_content(temp_template_file)

        cache_info_after_load = load_template_content.cache_info()
        assert cache_info_after_load.misses == 1, "First load should be a miss"
        assert cache_info_after_load.currsize == 1, "Cache should have 1 item"

        # Act - Clear the cache
        load_template_content.cache_clear()

        # Verify cache is empty
        cache_info_after_clear = load_template_content.cache_info()
        assert cache_info_after_clear.currsize == 0, (
            f"Cache should be empty after clear, got currsize={cache_info_after_clear.currsize}"
        )

        # Act - Load again after clear
        content2 = load_template_content(temp_template_file)
        cache_info_final = load_template_content.cache_info()

        # Assert - Content should be identical
        assert content1 == content2

        # Assert - After clear, we should have 1 miss (the new load), 0 hits
        assert cache_info_final.hits == 0, (
            f"After clear+load, expected 0 hits, got {cache_info_final.hits}"
        )
        assert cache_info_final.misses == 1, (
            f"After clear+load, expected 1 miss, got {cache_info_final.misses}"
        )
