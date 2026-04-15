"""Tests for research_with_cache.py module.

These tests verify unified research with cache integration.

Run with: pytest P:/packages/rca/skill/tests/test_research_with_cache.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup import path for rca package
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca import research_with_cache
from rca.auto_research import ResearchTrigger


class TestResearchResult:
    """Tests for ResearchResult dataclass."""

    def test_create_research_result_with_defaults(self):
        """Test creating ResearchResult with default values.

        Given: Creating ResearchResult with minimal args
        When: Initializing with needs_research and trigger
        Then: Should create object with default None values
        """
        trigger = ResearchTrigger(
            should_research=True,
            libraries=[],
            confidence=0.5,
            reason="Test trigger",
            keywords_found=[],
        )
        result = research_with_cache.ResearchResult(needs_research=True, trigger=trigger)

        assert result.needs_research is True
        assert result.cached_doc is None
        assert result.query == ""

    def test_create_research_result_with_cached_doc(self):
        """Test creating ResearchResult with cached documentation.

        Given: Creating ResearchResult with cached doc
        When: Initializing with cached_doc parameter
        Then: Should store cached documentation
        """
        trigger = ResearchTrigger(
            should_research=False,
            libraries=[],
            confidence=0.5,
            reason="Test trigger",
            keywords_found=[],
        )
        result = research_with_cache.ResearchResult(
            needs_research=False, trigger=trigger, cached_doc="Cached documentation content"
        )

        assert result.needs_research is False
        assert result.cached_doc == "Cached documentation content"

    def test_get_cached_content_returns_cached_doc(self):
        """Test that get_cached_content returns cached documentation.

        Given: ResearchResult with cached doc
        When: Calling get_cached_content
        Then: Should return cached documentation
        """
        trigger = ResearchTrigger(
            should_research=False,
            libraries=[],
            confidence=0.5,
            reason="Test trigger",
            keywords_found=[],
        )
        result = research_with_cache.ResearchResult(
            needs_research=False, trigger=trigger, cached_doc="Test cached doc"
        )

        assert result.get_cached_content() == "Test cached doc"

    def test_get_cached_content_returns_none_when_no_cache(self):
        """Test that get_cached_content returns None when no cache.

        Given: ResearchResult without cached doc
        When: Calling get_cached_content
        Then: Should return None
        """
        trigger = ResearchTrigger(
            should_research=False,
            libraries=[],
            confidence=0.5,
            reason="Test trigger",
            keywords_found=[],
        )
        result = research_with_cache.ResearchResult(needs_research=False, trigger=trigger)

        assert result.get_cached_content() is None

    def test_is_fresh_cached_returns_true_when_cached(self):
        """Test that is_fresh_cached returns True when doc is cached.

        Given: ResearchResult with cached doc
        When: Calling is_fresh_cached
        Then: Should return True
        """
        trigger = ResearchTrigger(
            should_research=False,
            libraries=[],
            confidence=0.5,
            reason="Test trigger",
            keywords_found=[],
        )
        result = research_with_cache.ResearchResult(
            needs_research=False, trigger=trigger, cached_doc="Cached content"
        )

        assert result.is_fresh_cached() is True

    def test_is_fresh_cached_returns_false_when_no_cache(self):
        """Test that is_fresh_cached returns False when no cache.

        Given: ResearchResult without cached doc
        When: Calling is_fresh_cached
        Then: Should return False
        """
        trigger = ResearchTrigger(
            should_research=False,
            libraries=[],
            confidence=0.5,
            reason="Test trigger",
            keywords_found=[],
        )
        result = research_with_cache.ResearchResult(needs_research=False, trigger=trigger)

        assert result.is_fresh_cached() is False


class TestResearchLibraryDocs:
    """Tests for research_library_docs function."""

    def test_no_research_needed_for_internal_code(self):
        """Test that internal code doesn't trigger research.

        Given: Problem description is internal code issue
        When: Calling research_library_docs
        Then: Should return needs_research=False
        """
        result = research_with_cache.research_library_docs("my_function returns None")

        assert result.needs_research is False
        assert result.trigger.should_research is False

    def test_research_needed_for_library_error(self):
        """Test that library error triggers research.

        Given: Problem description mentions library import error
        When: Calling research_library_docs
        Then: Should return needs_research=True with query
        """
        result = research_with_cache.research_library_docs("fastapi import error")

        assert result.needs_research is True
        assert len(result.query) > 0
        assert result.trigger.should_research is True

    def test_force_research_overrides_trigger(self):
        """Test that force_research=True forces research even when not needed.

        Given: Internal code issue but force_research=True
        When: Calling research_library_docs
        Then: Should return needs_research=True
        """
        result = research_with_cache.research_library_docs(
            "my_function returns None", force_research=True
        )

        assert result.needs_research is True

    def test_returns_trigger_info(self):
        """Test that trigger info is included in result.

        Given: Any problem description
        When: Calling research_library_docs
        Then: Should include trigger in result
        """
        result = research_with_cache.research_library_docs("test issue")

        assert hasattr(result, "trigger")
        assert isinstance(result.trigger, ResearchTrigger)

    @patch("rca.research_with_cache.get_library_cache")
    def test_cache_hit_returns_cached_content(self, mock_get_cache):
        """Test that cache hit returns cached documentation.

        Given: Library docs are in cache
        When: Calling research_library_docs
        Then: Should return ResearchResult with cached_doc
        """
        # Mock cache with fresh content
        mock_cache = MagicMock()
        mock_cached_entry = MagicMock()
        mock_cached_entry.content = "Cached yt-dlp documentation"
        mock_cached_entry.age_hours = 1.0

        # The code calls cache.get(lib), so we mock that
        mock_cache.get.return_value = mock_cached_entry
        mock_get_cache.return_value = mock_cache

        # Create a trigger with libraries
        with patch("rca.research_with_cache.should_trigger_research") as mock_trigger:
            mock_trigger.return_value = ResearchTrigger(
                should_research=True,
                libraries=["yt-dlp"],
                confidence=0.8,
                reason="Library error detected",
                keywords_found=[],
            )

            result = research_with_cache.research_library_docs(
                "yt-dlp option not found", max_cache_age_hours=24
            )

        assert result.needs_research is False  # Cached, so no immediate research needed
        assert result.cached_doc == "Cached yt-dlp documentation"

    @patch("rca.research_with_cache.get_library_cache")
    def test_cache_miss_returns_needs_research_true(self, mock_get_cache):
        """Test that cache miss returns needs_research=True.

        Given: Library docs not in cache
        When: Calling research_library_docs
        Then: Should return ResearchResult with needs_research=True and query
        """
        # Mock empty cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get_cache.return_value = mock_cache

        with patch("rca.research_with_cache.should_trigger_research") as mock_trigger:
            mock_trigger.return_value = ResearchTrigger(
                should_research=True,
                libraries=["yt-dlp"],
                confidence=0.8,
                reason="Library error detected",
                keywords_found=[],
            )

            result = research_with_cache.research_library_docs(
                "yt-dlp option not found", max_cache_age_hours=24
            )

        assert result.needs_research is True
        assert len(result.query) > 0
        assert result.cached_doc is None

    @patch("rca.research_with_cache.get_library_cache")
    def test_max_cache_age_parameter_passed_to_cache(self, mock_get_cache):
        """Test that max_cache_age_hours is passed to cache.

        Given: Custom max_cache_age_hours value
        When: Calling research_library_docs
        Then: Should pass the value to get_library_cache
        """
        with patch("rca.research_with_cache.should_trigger_research") as mock_trigger:
            mock_trigger.return_value = ResearchTrigger(
                should_research=True,
                libraries=["test-lib"],
                confidence=0.5,
                reason="Test",
                keywords_found=[],
            )
            research_with_cache.research_library_docs("test issue", max_cache_age_hours=48)

            # Verify get_library_cache was called with custom age
            mock_get_cache.assert_called_once_with(max_age_hours=48)


class TestStoreResearchResult:
    """Tests for store_research_result function."""

    @patch("rca.research_with_cache.get_library_cache")
    def test_stores_research_result_in_cache(self, mock_get_cache):
        """Test that research result is stored in cache.

        Given: Library content and sources
        When: Calling store_research_result
        Then: Should call cache.set with correct parameters
        """
        mock_cache = MagicMock()
        mock_cache.set.return_value = True
        mock_get_cache.return_value = mock_cache

        result = research_with_cache.store_research_result(
            library="yt-dlp",
            content="Documentation content",
            sources=["https://example.com/docs"],
            version="2024.12",
        )

        assert result is True
        mock_cache.set.assert_called_once_with(
            "yt-dlp", "Documentation content", ["https://example.com/docs"], "2024.12"
        )

    @patch("rca.research_with_cache.get_library_cache")
    def test_returns_false_on_cache_failure(self, mock_get_cache):
        """Test that cache set failure returns False.

        Given: Cache.set returns False (failure)
        When: Calling store_research_result
        Then: Should return False
        """
        mock_cache = MagicMock()
        mock_cache.set.return_value = False
        mock_get_cache.return_value = mock_cache

        result = research_with_cache.store_research_result(
            library="test-lib", content="content", sources=["url"]
        )

        assert result is False


class TestGetCacheStats:
    """Tests for get_cache_stats function."""

    @patch("rca.research_with_cache.get_library_cache")
    def test_returns_cache_stats_from_cache(self, mock_get_cache):
        """Test that cache stats are retrieved from cache.

        Given: Cache has stats available
        When: Calling get_cache_stats
        Then: Should return stats dict
        """
        mock_cache = MagicMock()
        expected_stats = {"total_entries": 5, "cache_size_mb": 2.3}
        mock_cache.get_stats.return_value = expected_stats
        mock_get_cache.return_value = mock_cache

        stats = research_with_cache.get_cache_stats()

        assert stats == expected_stats
        mock_cache.get_stats.assert_called_once()


class TestClearStaleCache:
    """Tests for clear_stale_cache function."""

    @patch("rca.research_with_cache.get_library_cache")
    def test_clears_stale_entries_from_cache(self, mock_get_cache):
        """Test that stale entries are cleared from cache.

        Given: Cache has stale entries
        When: Calling clear_stale_cache
        Then: Should call cache.clear_stale and return count
        """
        mock_cache = MagicMock()
        mock_cache.clear_stale.return_value = 3
        mock_get_cache.return_value = mock_cache

        result = research_with_cache.clear_stale_cache()

        assert result == 3
        mock_cache.clear_stale.assert_called_once()


class TestIntegration:
    """Integration tests for research_with_cache module."""

    @patch("rca.research_with_cache.should_trigger_research")
    def test_full_research_workflow_with_cache_miss(self, mock_should_trigger):
        """Test complete workflow: trigger -> cache miss -> query built.

        Given: Research is triggered and cache is empty
        When: Calling research_library_docs
        Then: Should return result with query built
        """
        mock_should_trigger.return_value = ResearchTrigger(
            should_research=True,
            libraries=["yt-dlp"],
            confidence=0.8,
            reason="Library error",
            keywords_found=[],
        )

        with patch("rca.research_with_cache.get_library_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None  # Cache miss
            mock_cache.return_value = mock_cache_instance

            result = research_with_cache.research_library_docs("yt-dlp error")

        assert result.needs_research is True
        assert result.query != ""
        assert "yt-dlp" in result.query or "yt dlp" in result.query.lower()

    @patch("rca.research_with_cache.should_trigger_research")
    def test_full_research_workflow_with_cache_hit(self, mock_should_trigger):
        """Test workflow: trigger -> cache hit -> no research needed.

        Given: Research is triggered but cache has fresh content
        When: Calling research_library_docs
        Then: Should return result with cached content
        """
        mock_should_trigger.return_value = ResearchTrigger(
            should_research=True,
            libraries=["yt-dlp"],
            confidence=0.8,
            reason="Library error",
            keywords_found=[],
        )

        with patch("rca.research_with_cache.get_library_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cached_entry = MagicMock()
            mock_cached_entry.content = "Fresh cached docs"
            mock_cached_entry.age_hours = 1.0
            mock_cache_instance.get.return_value = mock_cached_entry
            mock_cache.return_value = mock_cache_instance

            result = research_with_cache.research_library_docs("yt-dlp error")

        assert result.needs_research is False  # Cached, no immediate research
        assert result.cached_doc == "Fresh cached docs"

    @patch("rca.research_with_cache.should_trigger_research")
    def test_no_research_workflow_for_internal_code(self, mock_should_trigger):
        """Test that internal code doesn't trigger full workflow.

        Given: Problem is internal code (no libraries detected)
        When: Calling research_library_docs
        Then: Should return early without checking cache
        """
        mock_should_trigger.return_value = ResearchTrigger(
            should_research=False,
            libraries=[],
            confidence=0.0,
            reason="Internal code",
            keywords_found=[],
        )

        with patch("rca.research_with_cache.get_library_cache") as mock_cache:
            result = research_with_cache.research_library_docs("my function error")

        # Should not check cache if research not needed
        mock_cache.get.assert_not_called()

        assert result.needs_research is False


class TestModuleImports:
    """Tests for module imports and structure."""

    def test_module_exports_research_library_docs(self):
        """Test that main function is exported.

        Given: Importing research_with_cache module
        When: Checking for research_library_docs function
        Then: Should have the function available
        """
        assert hasattr(research_with_cache, "research_library_docs")
        assert callable(research_with_cache.research_library_docs)

    def test_module_exports_store_research_result(self):
        """Test that store_research_result is exported.

        Given: Importing research_with_cache module
        When: Checking for store_research_result function
        Then: Should have the function available
        """
        assert hasattr(research_with_cache, "store_research_result")
        assert callable(research_with_cache.store_research_result)

    def test_module_exports_get_cache_stats(self):
        """Test that get_cache_stats is exported.

        Given: Importing research_with_cache module
        When: Checking for get_cache_stats function
        Then: Should have the function available
        """
        assert hasattr(research_with_cache, "get_cache_stats")
        assert callable(research_with_cache.get_cache_stats)

    def test_module_exports_clear_stale_cache(self):
        """Test that clear_stale_cache is exported.

        Given: Importing research_with_cache module
        When: Checking for clear_stale_cache function
        Then: Should have the function available
        """
        assert hasattr(research_with_cache, "clear_stale_cache")
        assert callable(research_with_cache.clear_stale_cache)

    def test_conditional_imports_work(self):
        """Test that conditional imports for auto_research work.

        Given: Module imports auto_research and library_docs_cache
        When: Importing the module
        Then: Should import successfully (no ImportError)
        """
        # This test passes if the module imports successfully
        assert research_with_cache is not None
