"""
Performance tests for template content caching.

These tests verify that load_template_content() implements caching
to improve performance when loading templates multiple times.

Test scenarios:
1. test_template_content_caching - load_template_content() should cache results
2. test_cache_invalidation - cache should clear when file changes
3. test_duplicate_read_detection - detect when same file loaded twice
4. test_performance_improvement - cached loads should be faster than uncached
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


class TestTemplateContentCaching:
    """Tests for template content caching behavior."""

    @pytest.fixture
    def temp_template_file(self, tmp_path: Path) -> Path:
        """Create a temporary template file for testing."""
        template_file = tmp_path / "test_template.md"
        template_file.write_text("# Test Template\n\nSome content here.")
        return template_file

    def test_template_content_caching(self, temp_template_file: Path):
        """
        Test that load_template_content() caches results.

        Given: A template file exists
        When: The same file is loaded twice via load_template_content()
        Then: The file should only be read once from disk (cached on second load)
        """
        # Arrange - Import the cached function to verify caching behavior
        from validate_templates import _load_template_content_cached

        _load_template_content_cached.cache_clear()
        cache_info_before = _load_template_content_cached.cache_info()

        # Act - Load content twice
        content1 = load_template_content(temp_template_file)
        cache_info_after_first = _load_template_content_cached.cache_info()

        content2 = load_template_content(temp_template_file)
        cache_info_after_second = _load_template_content_cached.cache_info()

        # Assert - Verify content is correct
        assert content1 == content2 == "# Test Template\n\nSome content here."

        # First load should be a cache miss
        misses_after_first = cache_info_after_first.misses - cache_info_before.misses
        assert misses_after_first == 1, (
            f"First load should be a cache miss, got {misses_after_first} misses"
        )

        # Second load should be a cache hit (not read from disk again)
        hits_after_second = cache_info_after_second.hits - cache_info_after_first.hits
        assert hits_after_second == 1, (
            f"Second load should be a cache hit (cached), got {hits_after_second} hits. "
            f"Cache info: {cache_info_after_second}"
        )

    def test_cache_invalidation(self, temp_template_file: Path):
        """
        Test that cache clears when file changes.

        Given: A template file is loaded and cached
        When: The file is modified on disk and loaded again
        Then: The cache should be invalidated and new content loaded
        """
        # Arrange
        original_content = load_template_content(temp_template_file)
        assert original_content == "# Test Template\n\nSome content here."

        # Act - Modify the file
        temp_template_file.write_text("# Updated Template\n\nNew content here.")
        updated_content = load_template_content(temp_template_file)

        # Assert
        assert updated_content == "# Updated Template\n\nNew content here.", (
            "Cache should be invalidated when file changes, "
            "but old content was returned"
        )
        assert updated_content != original_content

    def test_duplicate_read_detection(self, temp_template_file: Path):
        """
        Test detection of duplicate file reads.

        Given: A function that loads templates multiple times
        When: The same file path is loaded multiple times
        Then: Duplicate reads should be detectable via cache metrics
        """
        # This test requires the module to expose cache statistics
        # For now, we'll test the behavior that should exist

        # Arrange & Act
        content1 = load_template_content(temp_template_file)
        content2 = load_template_content(temp_template_file)
        content3 = load_template_content(temp_template_file)

        # Assert - All returns should be identical
        assert content1 == content2 == content3

        # Check if cache statistics are available
        # (This will fail initially since cache doesn't exist yet)
        if hasattr(load_template_content, "cache_info"):
            cache_info = load_template_content.cache_info()
            assert cache_info.hits >= 2, "Expected at least 2 cache hits"
        else:
            pytest.fail(
                "load_template_content should expose cache_info() method "
                "to track cache hits/misses, but it doesn't exist yet"
            )

    def test_performance_improvement(self, temp_template_file: Path):
        """
        Test that cached loads are verified via cache_info() statistics.

        Given: A template file
        When: Loading the file multiple times
        Then: Cache should show hits, indicating caching is working

        This is a deterministic replacement for timing-dependent tests.
        Instead of measuring elapsed time (which is flaky due to system load,
        OS caching, SSD caching, etc.), we verify caching behavior through
        cache_info() statistics.
        """
        # Arrange - Make file large enough to measure difference
        large_content = "\n".join([f"Line {i}" for i in range(1000)])
        temp_template_file.write_text(large_content)

        # Act - Load content twice
        content1 = load_template_content(temp_template_file)
        content2 = load_template_content(temp_template_file)

        # Assert - Content should be identical
        assert content1 == content2

        # Assert - CRITICAL: Verify caching via cache_info()
        # This is the primary assertion - timing is just for demonstration
        assert hasattr(load_template_content, "cache_info"), (
            "load_template_content must expose cache_info() method"
        )
        cache_info = load_template_content.cache_info()
        assert cache_info.hits >= 1, (
            f"Expected at least 1 cache hit, got {cache_info.hits}. "
            "This verifies caching actually happened."
        )
        assert cache_info.misses >= 1, (
            f"Expected at least 1 cache miss, got {cache_info.misses}. "
            "First load should be a miss."
        )


class TestCacheImplementation:
    """Tests for specific cache implementation details."""

    @pytest.fixture
    def clear_cache(self):
        """Clear cache before each test."""
        # This will fail initially since cache doesn't exist
        if hasattr(load_template_content, "cache_clear"):
            load_template_content.cache_clear()
        yield
        if hasattr(load_template_content, "cache_clear"):
            load_template_content.cache_clear()

    def test_cache_clear_method_exists(self):
        """
        Test that cache_clear() method is available.

        Given: The load_template_content function with caching
        When: Calling cache_clear() to reset the cache
        Then: The method should exist and work without errors
        """
        # Assert - This will fail since cache doesn't exist yet
        assert hasattr(load_template_content, "cache_clear"), (
            "load_template_content should have a cache_clear() method "
            "to manually clear the cache"
        )

    def test_cache_info_method_exists(self):
        """
        Test that cache_info() method is available.

        Given: The load_template_content function with caching
        When: Calling cache_info() to get statistics
        Then: The method should exist and return cache statistics
        """
        # Assert - This will fail since cache doesn't exist yet
        assert hasattr(load_template_content, "cache_info"), (
            "load_template_content should have a cache_info() method "
            "to return cache statistics (hits, misses, size)"
        )

    def test_cache_max_size_setting(self):
        """
        Test that cache has a maximum size configured.

        Given: The load_template_content function with caching
        When: Checking cache configuration
        Then: Cache should have a reasonable max size to prevent memory issues
        """
        # This test verifies cache is properly bounded
        # Implementation should use @lru_cache or similar

        # Assert - This will fail initially
        if hasattr(load_template_content, "cache_info"):
            cache_info = load_template_content.cache_info()
            assert cache_info.maxsize > 0, "Cache should have a maxsize configured"
            assert cache_info.maxsize <= 128, (
                "Cache maxsize should be reasonable (<= 128)"
            )
        else:
            pytest.fail("Cache implementation missing - no cache_info() available")
