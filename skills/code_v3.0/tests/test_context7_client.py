#!/usr/bin/env python3
"""Unit tests for context7_client.py module.

This test suite verifies the Context7 client wrapper which provides:
- Library name to Context7 ID resolution
- Breaking change detection from changelogs
- Rate limit handling with exponential backoff
- Result caching to avoid duplicate queries

Run with: pytest P:/.claude/skills/code/tests/test_context7_client.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import time
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.context7_client import (
    Context7Resolver,
    BreakingChangeDetector,
    Context7RateLimitError,
)


class TestContext7ResolverBasicResolution:
    """Tests for basic library name resolution."""

    @pytest.fixture
    def mock_mcp_tool(self):
        """Create mock MCP tool for resolve-library-id."""
        mock_tool = MagicMock()
        mock_tool.return_value = {
            "library_id": "/org/pandas",
            "versions": ["1.5.0", "1.5.1", "1.5.2", "2.0.0"],
            "source_reputation": "official"
        }
        return mock_tool

    def test_resolve_library_name_returns_library_id(self, mock_mcp_tool):
        """
        Test that Context7Resolver resolves library names to Context7 IDs.

        Given: A library name "pandas"
        When: resolve_library_name() is called
        Then: Returns library_id and versions
        """
        # Arrange
        import sys
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_mcp_tool
        resolver = Context7Resolver()

        # Act
        result = resolver.resolve_library_name("pandas")

        # Assert
        assert result["library_id"] == "/org/pandas"
        assert "1.5.0" in result["versions"]
        assert "2.0.0" in result["versions"]
        assert result["source_reputation"] == "official"

    def test_resolve_library_name_with_query(self, mock_mcp_tool):
        """
        Test that resolver passes query parameter to Context7.

        Given: A library name and search query
        When: resolve_library_name() is called with query
        Then: Query is passed to MCP tool
        """
        # Arrange
        import sys
        mock_mcp_tool.return_value = {
            "library_id": "/org/numpy",
            "versions": ["1.24.0", "1.25.0"],
            "source_reputation": "official"
        }
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_mcp_tool
        resolver = Context7Resolver()

        # Act
        result = resolver.resolve_library_name("numpy", query="numerical computing")

        # Assert
        mock_mcp_tool.assert_called_once()
        call_args = mock_mcp_tool.call_args
        assert call_args[1]["libraryName"] == "numpy"
        assert call_args[1]["query"] == "numerical computing"
        assert result["library_id"] == "/org/numpy"


class TestBreakingChangeDetectorBasicQueries:
    """Tests for breaking change detection."""

    @pytest.fixture
    def mock_query_docs(self):
        """Create mock MCP tool for query-docs."""
        mock_tool = MagicMock()
        mock_tool.return_value = {
            "results": [
                {
                    "title": "Breaking Changes in pandas 2.0.0",
                    "content": "Deprecated DataFrame.append() method removed",
                    "url": "https://context7.org/org/pandas/changelog#2.0.0"
                }
            ]
        }
        return mock_tool

    def test_query_breaking_changes_queries_context7(self, mock_query_docs):
        """
        Test that BreakingChangeDetector queries Context7 for breaking changes.

        Given: A library_id and version range
        When: query_breaking_changes() is called
        Then: Returns structured breaking change data
        """
        # Arrange
        import sys
        sys.modules["mcp__plugin_context7_context7__query-docs"].Tool = mock_query_docs
        detector = BreakingChangeDetector()

        # Act
        result = detector.query_breaking_changes(
            library_id="/org/pandas",
            version="2.0.0"
        )

        # Assert
        assert len(result["breaking_changes"]) > 0
        assert "DataFrame.append()" in result["breaking_changes"][0]["content"]
        assert result["breaking_changes"][0]["url"] is not None

    def test_query_breaking_changes_filters_changelog_content(self, mock_query_docs):
        """
        Test that detector filters for changelog content only.

        Given: Context7 returns various documentation types
        When: query_breaking_changes() is called
        Then: Only changelog entries are returned
        """
        # Arrange
        import sys
        mock_query_docs.return_value = {
            "results": [
                {
                    "title": "API Reference",
                    "content": "DataFrame API documentation",
                    "url": "https://context7.org/org/pandas/api"
                },
                {
                    "title": "Release Notes 2.0.0",
                    "content": "Breaking: append() method removed",
                    "url": "https://context7.org/org/pandas/changelog#2.0.0"
                }
            ]
        }
        sys.modules["mcp__plugin_context7_context7__query-docs"].Tool = mock_query_docs
        detector = BreakingChangeDetector()

        # Act
        result = detector.query_breaking_changes(
            library_id="/org/pandas",
            version="2.0.0"
        )

        # Assert
        # Should only include changelog content, not API reference
        assert len(result["breaking_changes"]) == 1
        assert "append() method removed" in result["breaking_changes"][0]["content"]


class TestRateLimitHandling:
    """Tests for rate limit handling with exponential backoff."""

    @pytest.fixture
    def mock_mcp_with_rate_limit(self):
        """Create mock that simulates rate limit then success."""
        mock_tool = MagicMock()
        # First call hits rate limit, second succeeds
        mock_tool.side_effect = [
            {"error": "rate_limit_exceeded", "retry_after": 1},
            {
                "library_id": "/org/requests",
                "versions": ["2.28.0", "2.29.0"],
                "source_reputation": "official"
            }
        ]
        return mock_tool

    def test_rate_limit_triggers_exponential_backoff(self, mock_mcp_with_rate_limit):
        """
        Test that rate limit triggers exponential backoff retry.

        Given: Context7 returns rate limit error
        When: resolve_library_name() is called
        Then: Retries with exponential backoff and eventually succeeds
        """
        # Arrange
        import sys
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_mcp_with_rate_limit
        resolver = Context7Resolver(max_retries=2, initial_backoff=0.1)

        # Act
        start_time = time.time()
        result = resolver.resolve_library_name("requests")
        elapsed_time = time.time() - start_time

        # Assert
        # Should have succeeded after retry
        assert result["library_id"] == "/org/requests"
        # Should have taken at least initial_backoff time due to retry
        assert elapsed_time >= 0.1
        # Should have called tool twice (initial + 1 retry)
        assert mock_mcp_with_rate_limit.call_count == 2

    def test_rate_limit_respects_max_retries(self):
        """
        Test that resolver respects max_retries limit.

        Given: Context7 consistently returns rate limit errors
        When: resolve_library_name() is called with max_retries=2
        Then: Raises Context7RateLimitError after max retries exceeded
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {"error": "rate_limit_exceeded", "retry_after": 1}
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver(max_retries=2, initial_backoff=0.01)

        # Act & Assert
        with pytest.raises(Context7RateLimitError) as exc_info:
            resolver.resolve_library_name("library-name")

        # Should have tried max_retries + 1 times (initial + retries)
        assert mock_tool.call_count == 3
        assert "max retries" in str(exc_info.value).lower() and "exceeded" in str(exc_info.value).lower()

    def test_exponential_backoff_increments_properly(self):
        """
        Test that backoff time increases exponentially.

        Given: Multiple rate limit errors
        When: resolver retries
        Then: Backoff time doubles each retry (0.1s, 0.2s, 0.4s...)
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.side_effect = [
            {"error": "rate_limit_exceeded", "retry_after": 0.05},
            {"error": "rate_limit_exceeded", "retry_after": 0.05},
            {
                "library_id": "/org/test",
                "versions": ["1.0.0"],
                "source_reputation": "official"
            }
        ]
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver(max_retries=3, initial_backoff=0.05)

        # Act
        start_time = time.time()
        result = resolver.resolve_library_name("test")
        elapsed_time = time.time() - start_time

        # Assert
        assert result["library_id"] == "/org/test"
        # Should have waited: 0.05 + 0.1 = 0.15s minimum
        assert elapsed_time >= 0.15


class TestResultCaching:
    """Tests for result caching to avoid duplicate queries."""

    def test_duplicate_queries_use_cache(self):
        """
        Test that duplicate queries use cached results.

        Given: Same library queried twice
        When: resolve_library_name() is called twice for same library
        Then: Second call uses cache, doesn't call MCP tool
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {
            "library_id": "/org/cached-lib",
            "versions": ["1.0.0"],
            "source_reputation": "official"
        }
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver()

        # Act
        result1 = resolver.resolve_library_name("cached-lib")
        result2 = resolver.resolve_library_name("cached-lib")

        # Assert
        # Should only call MCP tool once (second call uses cache)
        assert mock_tool.call_count == 1
        assert result1 == result2

    def test_cache_key_includes_query_parameter(self):
        """
        Test that cache key includes query parameter.

        Given: Same library with different queries
        When: resolve_library_name() is called with different queries
        Then: Each query combination is cached separately
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {
            "library_id": "/org/test",
            "versions": ["1.0.0"],
            "source_reputation": "official"
        }
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver()

        # Act
        resolver.resolve_library_name("test", query="query1")
        resolver.resolve_library_name("test", query="query2")
        resolver.resolve_library_name("test", query="query1")  # Should use cache

        # Assert
        # Should call MCP tool twice (query1 cached, query2 cached, query1 reused)
        assert mock_tool.call_count == 2

    def test_cache_can_be_cleared(self):
        """
        Test that cache can be cleared explicitly.

        Given: Cached results exist
        When: clear_cache() is called
        Then: Next query calls MCP tool again
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {
            "library_id": "/org/test",
            "versions": ["1.0.0"],
            "source_reputation": "official"
        }
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver()

        # Act
        resolver.resolve_library_name("test")  # First call - cache miss
        resolver.resolve_library_name("test")  # Second call - cache hit
        resolver.clear_cache()
        resolver.resolve_library_name("test")  # Third call - cache miss again

        # Assert
        # Should call MCP tool twice (before and after cache clear)
        assert mock_tool.call_count == 2


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_unknown_library_returns_empty_result(self):
        """
        Test that unknown library returns empty result, not exception.

        Given: Library name not found in Context7
        When: resolve_library_name() is called
        Then: Returns empty dict with library_not_found flag
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {"error": "library_not_found"}
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver()

        # Act
        result = resolver.resolve_library_name("nonexistent-library-xyz")

        # Assert
        assert result.get("library_not_found") is True
        assert "library_id" not in result

    def test_service_unavailable_raises_error(self):
        """
        Test that service unavailable error is raised.

        Given: Context7 service is down
        When: resolve_library_name() is called
        Then: Raises Context7RateLimitError or similar
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {"error": "service_unavailable"}
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver(max_retries=0)  # No retries for faster test

        # Act & Assert
        with pytest.raises((Context7RateLimitError, Exception)):
            resolver.resolve_library_name("test-library")

    def test_malformed_response_handling(self):
        """
        Test that malformed response is handled gracefully.

        Given: Context7 returns malformed response (missing required fields)
        When: resolve_library_name() is called
        Then: Returns partial result or raises clear error
        """
        # Arrange
        import sys
        mock_tool = MagicMock()
        mock_tool.return_value = {"incomplete": "response"}  # Missing library_id
        sys.modules["mcp__plugin_context7_context7__resolve-library-id"].Tool = mock_tool
        resolver = Context7Resolver()

        # Act & Assert
        # Should handle gracefully - either return partial or raise clear error
        try:
            result = resolver.resolve_library_name("test")
            # If no error, should have error flag
            assert result.get("parse_error") is True or "error" in result
        except (ValueError, KeyError) as e:
            # Or raise clear error about malformed response
            assert "library_id" in str(e).lower() or "malformed" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
