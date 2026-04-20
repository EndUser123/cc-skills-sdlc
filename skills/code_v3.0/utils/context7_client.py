#!/usr/bin/env python3
"""Context7 client wrapper for library ID resolution and breaking change detection.

This module provides:
- Context7Resolver: Library name to Context7 ID resolution
- BreakingChangeDetector: Query breaking changes from changelogs
- Rate limit handling with exponential backoff
- Result caching to avoid duplicate queries
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple


# Constants
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 1.0
RATE_LIMIT_ERROR = "rate_limit_exceeded"
LIBRARY_NOT_FOUND_ERROR = "library_not_found"
SERVICE_UNAVAILABLE_ERROR = "service_unavailable"
MCP_TOOL_NOT_AVAILABLE_ERROR = "mcp_tool_not_available"
UNKNOWN_ERROR = "unknown_error"

# MCP tool module names
RESOLVE_LIBRARY_TOOL_MODULE = "mcp__plugin_context7_context7__resolve-library-id"
QUERY_DOCS_TOOL_MODULE = "mcp__plugin_context7_context7__query-docs"

# Changelog detection keywords
CHANGELOG_KEYWORDS = [
    "changelog",
    "release notes",
    "release note",
    "breaking change",
    "breaking changes",
    "deprecated",
    "removed",
    "migration",
]


class Context7RateLimitError(Exception):
    """Raised when Context7 rate limit is exceeded after max retries."""

    def __init__(self, message: str, max_retries: int = DEFAULT_MAX_RETRIES):
        """Initialize rate limit error.

        Args:
            message: Error message
            max_retries: Maximum retries attempted
        """
        super().__init__(message)
        self.max_retries = max_retries


class Context7Resolver:
    """Resolves library names to Context7 IDs with caching and rate limit handling."""

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        resolve_tool: Optional[Callable] = None,
    ):
        """Initialize resolver with retry configuration.

        Args:
            max_retries: Maximum number of retries on rate limit (default: 3)
            initial_backoff: Initial backoff time in seconds (default: 1.0)
            resolve_tool: Optional MCP tool function for dependency injection
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self._cache: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
        self._resolve_tool = resolve_tool

    def _generate_cache_key(
        self, library_name: str, query: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """Generate cache key from library name and query.

        Args:
            library_name: Name of the library
            query: Optional search query

        Returns:
            Tuple of (library_name, query) for cache key
        """
        return (library_name, query)

    def _call_with_retry(
        self, tool_func: Callable[..., Dict[str, Any]], **kwargs: Any
    ) -> Dict[str, Any]:
        """Call MCP tool with exponential backoff on rate limit.

        Args:
            tool_func: MCP tool function to call
            **kwargs: Arguments to pass to tool function

        Returns:
            Tool response dictionary

        Raises:
            Context7RateLimitError: If max retries exceeded
        """
        last_error: Optional[Dict[str, Any]] = None
        backoff = self.initial_backoff

        for attempt in range(self.max_retries + 1):
            try:
                response = tool_func(**kwargs)

                # Check for rate limit error
                if (
                    isinstance(response, dict)
                    and response.get("error") == RATE_LIMIT_ERROR
                ):
                    last_error = response
                    if attempt < self.max_retries:
                        time.sleep(backoff)
                        backoff *= 2  # Exponential backoff
                        continue
                    else:
                        raise Context7RateLimitError(
                            f"Max retries ({self.max_retries}) exceeded for rate limit",
                            max_retries=self.max_retries,
                        )

                return response

            except Context7RateLimitError:
                raise
            except Exception as e:
                # For non-rate-limit errors, return immediately
                if "rate_limit" not in str(e).lower():
                    return {"error": str(e)}
                raise

        # Should not reach here, but handle gracefully
        if last_error:
            raise Context7RateLimitError(
                f"Max retries ({self.max_retries}) exceeded for rate limit",
                max_retries=self.max_retries,
            )
        return {"error": UNKNOWN_ERROR}

    def resolve_library_name(
        self, library_name: str, query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolve library name to Context7 ID.

        Args:
            library_name: Name of the library to resolve
            query: Optional search query to disambiguate

        Returns:
            Dictionary with library_id, versions, source_reputation
            or error flags (library_not_found, parse_error)

        Raises:
            RuntimeError: If Context7 service is unavailable
        """
        # Check cache
        cache_key = self._generate_cache_key(library_name, query)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get tool function (injected or imported)
        tool_func = self._resolve_tool
        if tool_func is None:
            tool_func = self._get_mcp_tool(RESOLVE_LIBRARY_TOOL_MODULE)
            if tool_func is None:
                return {"error": MCP_TOOL_NOT_AVAILABLE_ERROR}

        # Call tool with retry
        response = self._call_with_retry(
            tool_func, libraryName=library_name, query=query
        )

        # Handle errors and parse response
        result = self._parse_response(response)

        # Cache result
        self._cache[cache_key] = result
        return result

    def _get_mcp_tool(
        self, module_name: str
    ) -> Optional[Callable[..., Dict[str, Any]]]:
        """Get MCP tool function from sys.modules.

        Args:
            module_name: Name of the MCP tool module

        Returns:
            Tool function or None if not available
        """
        try:
            import sys

            # Tests register mock modules in sys.modules
            if module_name in sys.modules:
                return sys.modules[module_name].Tool
            return None
        except (ImportError, AttributeError, KeyError):
            return None

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse MCP tool response and handle errors.

        Args:
            response: Raw response from MCP tool

        Returns:
            Parsed response with appropriate error flags

        Raises:
            RuntimeError: If service is unavailable
        """
        error = response.get("error")

        if error == LIBRARY_NOT_FOUND_ERROR:
            return {"library_not_found": True}
        elif error == SERVICE_UNAVAILABLE_ERROR:
            raise RuntimeError("Context7 service unavailable")
        elif error:
            # For other errors, try to parse what we have
            if "library_id" in response:
                result = response.copy()
                result["parse_error"] = True
                return result
            else:
                return {"parse_error": True, "error": error}
        elif "library_id" not in response:
            # Malformed response
            return {"parse_error": True, "response": response}
        else:
            return response

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._cache.clear()


class BreakingChangeDetector:
    """Detects breaking changes from Context7 changelogs."""

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        query_tool: Optional[Callable] = None,
    ):
        """Initialize detector with retry configuration.

        Args:
            max_retries: Maximum number of retries on rate limit (default: 3)
            initial_backoff: Initial backoff time in seconds (default: 1.0)
            query_tool: Optional MCP tool function for dependency injection
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self._cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._query_tool = query_tool

    def _generate_cache_key(self, library_id: str, version: str) -> Tuple[str, str]:
        """Generate cache key from library_id and version.

        Args:
            library_id: Context7 library ID
            version: Library version

        Returns:
            Tuple of (library_id, version) for cache key
        """
        return (library_id, version)

    def _call_with_retry(
        self, tool_func: Callable[..., Dict[str, Any]], **kwargs: Any
    ) -> Dict[str, Any]:
        """Call MCP tool with exponential backoff on rate limit.

        Args:
            tool_func: MCP tool function to call
            **kwargs: Arguments to pass to tool function

        Returns:
            Tool response dictionary

        Raises:
            Context7RateLimitError: If max retries exceeded
        """
        last_error: Optional[Dict[str, Any]] = None
        backoff = self.initial_backoff

        for attempt in range(self.max_retries + 1):
            try:
                response = tool_func(**kwargs)

                # Check for rate limit error
                if (
                    isinstance(response, dict)
                    and response.get("error") == RATE_LIMIT_ERROR
                ):
                    last_error = response
                    if attempt < self.max_retries:
                        time.sleep(backoff)
                        backoff *= 2  # Exponential backoff
                        continue
                    else:
                        raise Context7RateLimitError(
                            f"Max retries ({self.max_retries}) exceeded for rate limit",
                            max_retries=self.max_retries,
                        )

                return response

            except Context7RateLimitError:
                raise
            except Exception as e:
                # For non-rate-limit errors, return immediately
                if "rate_limit" not in str(e).lower():
                    return {"error": str(e)}
                raise

        # Should not reach here, but handle gracefully
        if last_error:
            raise Context7RateLimitError(
                f"Max retries ({self.max_retries}) exceeded for rate limit",
                max_retries=self.max_retries,
            )
        return {"error": UNKNOWN_ERROR}

    def _is_changelog_content(self, title: str, content: str) -> bool:
        """Check if content is from changelog/release notes.

        Args:
            title: Title of the document
            content: Content of the document

        Returns:
            True if appears to be changelog content
        """
        title_lower = title.lower()
        content_lower = content.lower()

        # Check if title or content contains changelog indicators
        return any(
            keyword in title_lower or keyword in content_lower
            for keyword in CHANGELOG_KEYWORDS
        )

    def query_breaking_changes(
        self, library_id: str, version: str
    ) -> Dict[str, Any]:
        """Query breaking changes for a specific library version.

        Args:
            library_id: Context7 library ID (e.g., "/org/pandas")
            version: Version to query (e.g., "2.0.0")

        Returns:
            Dictionary with breaking_changes list containing
            title, content, url for each breaking change.
            Returns empty list if MCP tool is unavailable.
        """
        # Check cache
        cache_key = self._generate_cache_key(library_id, version)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get tool function (injected or imported)
        tool_func = self._query_tool
        if tool_func is None:
            tool_func = self._get_mcp_tool(QUERY_DOCS_TOOL_MODULE)
            if tool_func is None:
                return {"breaking_changes": []}

        # Query Context7 for changelog content
        query = f"breaking changes {version} changelog release notes"
        response = self._call_with_retry(
            tool_func, libraryId=library_id, query=query
        )

        # Extract and filter breaking changes
        breaking_changes = self._extract_breaking_changes(response)
        result = {"breaking_changes": breaking_changes}

        # Cache result
        self._cache[cache_key] = result
        return result

    def _get_mcp_tool(
        self, module_name: str
    ) -> Optional[Callable[..., Dict[str, Any]]]:
        """Get MCP tool function from sys.modules.

        Args:
            module_name: Name of the MCP tool module

        Returns:
            Tool function or None if not available
        """
        try:
            import sys

            # Tests register mock modules in sys.modules
            if module_name in sys.modules:
                return sys.modules[module_name].Tool
            return None
        except (ImportError, AttributeError, KeyError):
            return None

    def _extract_breaking_changes(
        self, response: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Extract and filter breaking changes from MCP response.

        Args:
            response: Raw response from MCP tool

        Returns:
            List of breaking change dictionaries with title, content, url
        """
        breaking_changes: List[Dict[str, str]] = []
        results = response.get("results", [])

        for result in results:
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")

            # Filter for changelog content only
            if self._is_changelog_content(title, content):
                breaking_changes.append(
                    {"title": title, "content": content, "url": url}
                )

        return breaking_changes

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._cache.clear()
