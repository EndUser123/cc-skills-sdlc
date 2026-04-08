"""Prerequisite analyzer for arch skill.

Distinguishes optimization queries from genuine prerequisite needs.

This module provides semantic analysis to prevent false positives in
prerequisite gate detection. It identifies whether a user query is an
optimization request (which should proceed directly to architecture) or
a genuine prerequisite need (which should trigger a gate).

Gate Types:
    /prd: Triggered when user references requirements/PRD documents
    /discover: Triggered when user asks about structure/organization
    /debug: Triggered when user indicates debugging/diagnosis needed

Example:
    >>> result = PrerequisiteAnalyzer.analyze("improve memory system")
    >>> result["should_trigger_gate"]
    False
    >>> result["is_optimization"]
    True
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TypedDict

__all__ = ["PrerequisiteAnalyzer", "AnalysisResult"]


class AnalysisResult(TypedDict, total=True):
    """Result of prerequisite analysis.

    Attributes:
        should_trigger_gate: Whether a prerequisite gate should trigger
        gate_type: Type of gate to trigger ("/prd", "/discover", "/debug") or None
        reason: Human-readable explanation of the decision, or None
        is_optimization: Whether the query is an optimization request
    """

    should_trigger_gate: bool
    gate_type: str | None
    reason: str | None
    is_optimization: bool


# =============================================================================
# Module-level Pattern Constants
# =============================================================================

# Optimization patterns that should NOT trigger prerequisite gates.
# These patterns indicate the user has clear context and intent to improve
# existing functionality, so they should proceed directly to architecture.
#
# Examples:
#   - "improve memory system" -> no gate (user knows what to improve)
#   - "optimize caching layer" -> no gate (user knows what to optimize)
#   - "harden security layer" -> no gate (user has clear security context)
OPTIMIZATION_PATTERNS: tuple[str, ...] = (
    r"\bimprove\b",
    r"\boptimize\b",
    r"\bharden\b",
    r"\benhance\b",
    r"\bstabilize\b",
    r"\brefactor\b",
    r"\bspeed\s+up\b",
    r"\bfix\s+performance\b",
)

# PRD (Product Requirements Document) gate patterns.
# These patterns trigger when the user explicitly references requirements
# or indicates they need PRD information to proceed.
#
# Examples:
#   - "design API from requirements" -> triggers /prd
#   - "where are requirements" -> triggers /prd
#   - "need PRD for architecture" -> triggers /prd
PRD_PATTERNS: tuple[str, ...] = (
    r"\bfrom\s+requirements\b",
    r"\bwhere\s+are\s+requirements\b",
    r"\bprd\s+needed\b",
    r"\bneed\s+prd\b",
    r"\brequirements\s+for\b",
)

# Discover gate patterns.
# These patterns trigger when the user asks about codebase structure,
# organization, or needs foundational understanding before proceeding.
#
# Examples:
#   - "how is X structured" -> triggers /discover
#   - "what is the structure of Y" -> triggers /discover
#   - "understand the structure of Z" -> triggers /discover
DISCOVER_PATTERNS: tuple[str, ...] = (
    r"\bhow\s+is\s+\w+\s+structured\b",
    r"\bhow\s+is\s+\w+\s+organized\b",
    r"\bwhat\s+is\s+the\s+structure\b",
    r"\bunderstand\s+the\s+structure\b",
)

# Debug gate patterns.
# These patterns trigger when the user indicates something is failing
# and they need diagnostic help before proceeding.
#
# Examples:
#   - "why failing" -> triggers /debug
#   - "debug authentication" -> triggers /debug
#   - "what's wrong with X" -> triggers /debug
DEBUG_PATTERNS: tuple[str, ...] = (
    r"\bwhy\s+failing\b",
    r"\bwhy\s+is\s+it\s+failing\b",
    r"\bdebug\s+\w+\b",
    r"\bwhat's\s+wrong\b",
    r"\bdiagnose\b",
)


class PrerequisiteAnalyzer:
    """Analyzes queries to determine if prerequisite gates should trigger.

    This class implements semantic analysis to prevent false positives in
    prerequisite gate detection. It distinguishes between:

    - **Optimization queries**: "improve X", "optimize Y", "harden Z"
      These indicate the user has clear context and intent, so they
      should proceed directly to architecture analysis without gates.

    - **Genuine prerequisites**: "from requirements", "how is X structured"
      These indicate missing foundational information, so they should
      trigger the appropriate gate (/prd, /discover, or /debug).

    Pattern matching is case-insensitive and robust to whitespace variations.

    Example:
        >>> result = PrerequisiteAnalyzer.analyze("improve memory system")
        >>> result["should_trigger_gate"]
        False
        >>> result["gate_type"]
        None
        >>> result["is_optimization"]
        True

        >>> result = PrerequisiteAnalyzer.analyze("design API from requirements")
        >>> result["should_trigger_gate"]
        True
        >>> result["gate_type"]
        '/prd'
    """

    # Reference to module-level constants for backward compatibility
    OPTIMIZATION_PATTERNS = OPTIMIZATION_PATTERNS
    PRD_PATTERNS = PRD_PATTERNS
    DISCOVER_PATTERNS = DISCOVER_PATTERNS
    DEBUG_PATTERNS = DEBUG_PATTERNS

    @staticmethod
    def analyze(query: str) -> AnalysisResult:
        """Analyze a query to determine if a prerequisite gate should trigger.

        This method performs semantic analysis on user queries to distinguish
        between optimization requests (which should proceed directly to
        architecture) and genuine prerequisite needs (which should trigger
        the appropriate gate).

        Analysis priority:
            1. PRD gate - triggered by requirements/PRD references
            2. Discover gate - triggered by structure/organization questions
            3. Debug gate - triggered by debugging/diagnosis indicators

        The analysis is case-insensitive and robust to whitespace variations.
        A query can be both an optimization AND trigger a gate if it explicitly
        references prerequisites (e.g., "improve X from requirements").

        Args:
            query: The user query to analyze. Can contain mixed case and
                irregular whitespace.

        Returns:
            AnalysisResult: A dictionary containing:
                - should_trigger_gate (bool): True if a gate should trigger
                - gate_type (str | None): Type of gate ("/prd", "/discover", "/debug") or None
                - reason (str | None): Human-readable explanation of the decision
                - is_optimization (bool): True if query contains optimization patterns

        Examples:
            >>> PrerequisiteAnalyzer.analyze("improve memory system")
            {'should_trigger_gate': False, 'gate_type': None, 'reason': None, 'is_optimization': True}

            >>> PrerequisiteAnalyzer.analyze("design API from requirements")
            {'should_trigger_gate': True, 'gate_type': '/prd', 'reason': 'Query references requirements/PRD', 'is_optimization': False}

            >>> PrerequisiteAnalyzer.analyze("improve authentication from requirements")
            {'should_trigger_gate': True, 'gate_type': '/prd', 'reason': 'Query references requirements/PRD', 'is_optimization': True}
        """
        # Normalize query: strip leading/trailing whitespace and convert to lowercase
        normalized = query.strip().lower()

        # Check for optimization patterns (optimization queries proceed directly to architecture)
        is_optimization = PrerequisiteAnalyzer._matches_optimization(normalized)

        # Check for prerequisite patterns in priority order
        # Priority 1: PRD patterns (requirements/PRD references)
        if PrerequisiteAnalyzer._matches_prd(normalized):
            return AnalysisResult(
                should_trigger_gate=True,
                gate_type="/prd",
                reason="Query references requirements/PRD",
                is_optimization=is_optimization,
            )

        # Priority 2: Discover patterns (structure/organization questions)
        if PrerequisiteAnalyzer._matches_discover(normalized):
            return AnalysisResult(
                should_trigger_gate=True,
                gate_type="/discover",
                reason="Query asks about structure/organization",
                is_optimization=is_optimization,
            )

        # Priority 3: Debug patterns (debugging/diagnosis indicators)
        if PrerequisiteAnalyzer._matches_debug(normalized):
            return AnalysisResult(
                should_trigger_gate=True,
                gate_type="/debug",
                reason="Query indicates debugging/diagnosis needed",
                is_optimization=is_optimization,
            )

        # No prerequisite patterns matched - proceed to architecture
        return AnalysisResult(
            should_trigger_gate=False,
            gate_type=None,
            reason=None,
            is_optimization=is_optimization,
        )

    @staticmethod
    @lru_cache(maxsize=256)
    def _matches_optimization(text: str) -> bool:
        """Check if text matches any optimization pattern (cached by text only)."""
        for pattern in OPTIMIZATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    @lru_cache(maxsize=256)
    def _matches_prd(text: str) -> bool:
        """Check if text matches any PRD pattern (cached by text only)."""
        for pattern in PRD_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    @lru_cache(maxsize=256)
    def _matches_discover(text: str) -> bool:
        """Check if text matches any discover pattern (cached by text only)."""
        for pattern in DISCOVER_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    @lru_cache(maxsize=256)
    def _matches_debug(text: str) -> bool:
        """Check if text matches any debug pattern (cached by text only)."""
        for pattern in DEBUG_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    @lru_cache(maxsize=256)
    def _matches_any_cached(text: str) -> bool:
        """Check if text matches any pattern (cached by text only).

        This internal helper checks text against ALL pattern constants and
        caches the result by text only.
        """
        all_patterns = (
            OPTIMIZATION_PATTERNS + PRD_PATTERNS + DISCOVER_PATTERNS + DEBUG_PATTERNS
        )
        for pattern in all_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        """Check if text matches any of the given regex patterns.

        This method performs case-insensitive regex matching against a tuple
        of patterns. Results are cached using LRU cache keyed only on text
        for efficiency - since patterns are module-level constants.

        Args:
            text: The text to match against (should be lowercase for efficiency).
                While matching is case-insensitive, passing lowercase text
                avoids redundant case conversion.
            patterns: Tuple of regex pattern strings to match against.
                Using a tuple instead of a list enables LRU caching.

        Returns:
            True if any pattern matches the text, False otherwise.

        Note:
            This method uses @lru_cache for performance. The cache key is
            text only (not patterns), since patterns are module-level constants.
            Checking the same text against different pattern types reuses the
            same cache entry.
        """
        # Use the text-only cached helper
        return PrerequisiteAnalyzer._matches_any_cached(text)

    @staticmethod
    def _matches_any_cache_clear() -> None:
        """Clear all caches for pattern matching methods."""
        PrerequisiteAnalyzer._matches_any_cached.cache_clear()
        PrerequisiteAnalyzer._matches_optimization.cache_clear()
        PrerequisiteAnalyzer._matches_prd.cache_clear()
        PrerequisiteAnalyzer._matches_discover.cache_clear()
        PrerequisiteAnalyzer._matches_debug.cache_clear()

    @staticmethod
    def _matches_any_cache_info():
        """Get aggregate cache info from all pattern matching methods."""
        any_info = PrerequisiteAnalyzer._matches_any_cached.cache_info()
        opt_info = PrerequisiteAnalyzer._matches_optimization.cache_info()
        prd_info = PrerequisiteAnalyzer._matches_prd.cache_info()
        disc_info = PrerequisiteAnalyzer._matches_discover.cache_info()
        dbg_info = PrerequisiteAnalyzer._matches_debug.cache_info()

        from collections import namedtuple

        CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])

        return CacheInfo(
            hits=any_info.hits
            + opt_info.hits
            + prd_info.hits
            + disc_info.hits
            + dbg_info.hits,
            misses=any_info.misses
            + opt_info.misses
            + prd_info.misses
            + disc_info.misses
            + dbg_info.misses,
            maxsize=256,  # All caches have maxsize=256
            currsize=any_info.currsize
            + opt_info.currsize
            + prd_info.currsize
            + disc_info.currsize
            + dbg_info.currsize,
        )


# Expose cache methods (type: ignore for mypy compatibility with lru_cache)
PrerequisiteAnalyzer._matches_any.cache_clear = (  # type: ignore[attr-defined]
    PrerequisiteAnalyzer._matches_any_cache_clear
)
PrerequisiteAnalyzer._matches_any.cache_info = (  # type: ignore[attr-defined]
    PrerequisiteAnalyzer._matches_any_cache_info
)
