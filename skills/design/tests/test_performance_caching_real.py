"""
Real caching verification test for template content loading.

This test properly verifies caching behavior by tracking ACTUAL calls
to the cached function, not manual counters.

The test exposes the flaw in test_performance.py lines 51-59 where manual
counter increment is used instead of real caching verification.

Issue: TEST-002 - Flawed caching assertion in test_performance.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any

# Import the module under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_templates import load_template_content, _load_template_content_cached


class TestOriginalTestFlaw:
    """
    Tests that demonstrate the flaw in the original test_performance.py.

    The original test at lines 51-59 uses manual counter increment:
        read_count['count'] += 1

    This is FUNDAMENTALLY FLAWED because:
    1. The counter is manually incremented, not tracking actual reads
    2. The test passes regardless of whether caching actually works
    3. The assertion expects read_count == 1, but manual counting always == 2
    """

    @pytest.fixture
    def temp_template_file(self, tmp_path: Path) -> Path:
        """Create a temporary template file for testing."""
        template_file = tmp_path / "test_template.md"
        template_file.write_text("# Test Template\n\nSome content here.")
        return template_file

    @pytest.mark.skip(
        reason="Documentation test demonstrating flaw in manual counting approach. "
        "This test is expected to fail to show the problem with the original approach."
    )
    def test_original_test_fails_because_assertion_is_wrong(
        self, temp_template_file: Path
    ):
        """
        This test demonstrates WHY the original test is flawed.

        The original test code (lines 51-59):
            read_count = {"count": 0}
            content1 = load_template_content(temp_template_file)
            read_count["count"] += 1  # Manual increment!

            content2 = load_template_content(temp_template_file)
            read_count["count"] += 1  # Manual increment again!

            assert read_count["count"] == 1  # This will ALWAYS FAIL!

        Problem: Manual counting produces 2, but assertion expects 1.
        This test can NEVER pass, regardless of caching behavior.

        The test SHOULD fail now (RED phase) to expose the flaw.
        """
        # Arrange & Act - EXACT SAME CODE as original test
        read_count = {"count": 0}

        content1 = load_template_content(temp_template_file)
        read_count["count"] += 1

        content2 = load_template_content(temp_template_file)
        read_count["count"] += 1

        # Assert - The original assertion
        # This FAILS because manual counting produces 2, not 1
        assert read_count["count"] == 1, (
            f"Expected read_count == 1 (as in original test), "
            f"but got {read_count['count']}. "
            f"This demonstrates the FLAW: manual counting always produces 2 "
            f"when we call load_template_content() twice, regardless of caching."
        )

    def test_correct_way_to_verify_caching(self, temp_template_file: Path):
        """
        This test shows the CORRECT way to verify caching behavior.

        Instead of manual counting, we use cache_info() to track
        actual cache hits and misses.

        This test PASSES because caching actually works in the implementation.
        """
        # Arrange - Clear cache
        _load_template_content_cached.cache_clear()
        cache_info_before = _load_template_content_cached.cache_info()

        # Act - Load content twice
        content1 = load_template_content(temp_template_file)
        cache_info_after_first = _load_template_content_cached.cache_info()

        content2 = load_template_content(temp_template_file)
        cache_info_after_second = _load_template_content_cached.cache_info()

        # Assert - Verify content
        assert content1 == content2 == "# Test Template\n\nSome content here."

        # First load should be a cache miss
        misses_after_first = cache_info_after_first.misses - cache_info_before.misses
        assert misses_after_first == 1, (
            f"First load should be a cache miss, got {misses_after_first}"
        )

        # Second load should be a cache hit
        hits_after_second = cache_info_after_second.hits - cache_info_after_first.hits
        assert hits_after_second == 1, (
            f"Second load should be a cache hit, got {hits_after_second} hits. "
            f"If this fails, caching is NOT working."
        )


class TestManualCounterDoesNotVerifyCaching:
    """
    Tests demonstrating that manual counters cannot verify caching.
    """

    @pytest.fixture
    def temp_template_file(self, tmp_path: Path) -> Path:
        """Create a temporary template file for testing."""
        template_file = tmp_path / "test_template.md"
        template_file.write_text("# Test Template\n\nSome content here.")
        return template_file

    def test_manual_counter_always_equals_call_count(self, temp_template_file: Path):
        """
        Prove that manual counters only track function calls, not caching.

        No matter how many times we call load_template_content(),
        if we manually increment the counter each time, it will ALWAYS
        equal the number of calls.

        This proves manual counting cannot verify caching.
        """
        # Test with 1 call
        counter1 = {"count": 0}
        load_template_content(temp_template_file)
        counter1["count"] += 1
        assert counter1["count"] == 1

        # Test with 2 calls
        counter2 = {"count": 0}
        load_template_content(temp_template_file)
        counter2["count"] += 1
        load_template_content(temp_template_file)
        counter2["count"] += 1
        assert counter2["count"] == 2  # Always equals number of calls!

        # Test with 3 calls
        counter3 = {"count": 0}
        for _ in range(3):
            load_template_content(temp_template_file)
            counter3["count"] += 1
        assert counter3["count"] == 3  # Always equals number of calls!

        # Conclusion: Manual counting is USELESS for verifying caching

    def test_cache_info_correctly_tracks_caching(self, temp_template_file: Path):
        """
        Prove that cache_info() correctly tracks actual caching behavior.

        Unlike manual counting, cache_info() shows that subsequent calls
        use the cache (hits) instead of reading the file again (misses).
        """
        # Clear cache
        _load_template_content_cached.cache_clear()

        # Load 5 times
        for _ in range(5):
            load_template_content(temp_template_file)

        # Check cache stats
        info = _load_template_content_cached.cache_info()

        # Should have 1 miss (first read) and 4 hits (cached)
        assert info.misses == 1, f"Expected 1 cache miss, got {info.misses}"
        assert info.hits == 4, f"Expected 4 cache hits, got {info.hits}"

        # This PROVES caching works - the file was only read once!


class TestComparisonFlawedVsCorrect:
    """
    Side-by-side comparison of flawed (manual counter) vs correct (cache_info) approaches.
    """

    @pytest.fixture
    def temp_template_file(self, tmp_path: Path) -> Path:
        """Create a temporary template file for testing."""
        template_file = tmp_path / "test_template.md"
        template_file.write_text("# Test Template\n\nSome content here.")
        return template_file

    @pytest.mark.skip(
        reason="Documentation test demonstrating flaw in manual counter approach. "
        "This test is expected to fail to show the problem with manual counting."
    )
    def test_flawed_approach_manual_counter(self, temp_template_file: Path):
        """
        FLAWED APPROACH: Manual counter (from original test_performance.py lines 51-59).

        This approach CANNOT verify caching because it manually counts calls.
        The assertion `assert read_count == 1` will ALWAYS FAIL when we call
        load_template_content() twice, regardless of actual caching behavior.

        This test FAILS (as expected in RED phase) to expose the flaw.
        """
        # FLAWED: Manual counter
        read_count = {"count": 0}

        # Call load_template_content() twice
        load_template_content(temp_template_file)
        read_count["count"] += 1  # Manual: now 1

        load_template_content(temp_template_file)
        read_count["count"] += 1  # Manual: now 2

        # FLAWED ASSERTION: Expects 1, but manual counting always produces 2
        # This will FAIL because we called load_template_content() twice
        assert read_count["count"] == 1, (
            f"FLAWED: This assertion expects 1 but manual counting produces {read_count['count']}. "
            f"Manual counting CANNOT verify caching - it only counts function calls."
        )

    def test_correct_approach_cache_info(self, temp_template_file: Path):
        """
        CORRECT APPROACH: Using cache_info() to track actual caching.

        This approach CAN verify caching because it tracks actual cache hits/misses.

        This test PASSES because caching actually works in the implementation.
        """
        # CORRECT: Use cache_info()
        _load_template_content_cached.cache_clear()

        # Call load_template_content() twice
        load_template_content(temp_template_file)
        load_template_content(temp_template_file)

        # CORRECT ASSERTION: Check cache statistics
        info = _load_template_content_cached.cache_info()
        assert info.misses == 1, (
            f"CORRECT: First call was a miss (file read), got {info.misses} misses"
        )
        assert info.hits == 1, (
            f"CORRECT: Second call was a hit (used cache), got {info.hits} hits"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
