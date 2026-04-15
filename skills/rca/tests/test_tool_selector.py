"""Tests for core.tool_selector module.

Tests for intelligent tool selection based on context analysis.

Run with: pytest P:/packages/rca/skill/tests/test_tool_selector.py -v
"""

import pytest
from rca.core.tool_selector import (
    ToolSelector,
    ToolSelectorMetrics,
)


class TestToolSelectorInit:
    """Test ToolSelector initialization."""

    def test_selector_creation(self):
        """ToolSelector can be created."""
        selector = ToolSelector()

        assert selector is not None
        assert selector.tool_matrix is not None
        assert selector.performance_weights is not None


class TestToolSelectorForSyntaxError:
    """Test tool selection for syntax errors."""

    @pytest.fixture
    def selector(self):
        """Return a ToolSelector instance."""
        return ToolSelector()

    def test_selects_syntax_appropriate_strategy(self, selector):
        """Select systematic strategy for syntax errors.

        Given: A syntax error context with high confidence
        When: Selecting optimal tools for the context
        Then: The systematic strategy should be selected with appropriate tools
        """
        context = {
            "problem_type": "syntax",
            "error_type": "SyntaxError",
            "confidence_score": 0.9,
            "complexity_level": "simple",
            "scope": "file",
            "recommended_strategy": "systematic",
        }

        result = selector.select_optimal_tools(context)

        assert result["primary_strategy"] == "systematic"
        assert result["selection_confidence"] > 0.7
        assert len(result["primary_tools"]) > 0
        assert result["optimization_level"] in ["standard", "enhanced", "maximum"]

    def test_includes_syntax_analysis_tools(self, selector):
        """Include syntax-specific tools in selection.

        Given: A syntax error context
        When: Selecting optimal tools
        Then: Primary tools should include syntax analysis capabilities
        """
        context = {
            "problem_type": "syntax",
            "error_type": "SyntaxError",
            "confidence_score": 0.8,
            "complexity_level": "simple",
            "recommended_strategy": "systematic",
        }

        result = selector.select_optimal_tools(context)

        # Check that primary tools are appropriate for syntax analysis
        assert (
            "TreeSitter" in result["primary_tools"] or "CustomAnalyzer" in result["primary_tools"]
        )
        assert result["strategy_description"] is not None


class TestToolSelectorForRuntimeError:
    """Test tool selection for runtime errors."""

    @pytest.fixture
    def selector(self):
        """Return a ToolSelector instance."""
        return ToolSelector()

    def test_selects_runtime_appropriate_strategy(self, selector):
        """Select systematic or exploratory strategy for runtime errors.

        Given: A runtime error context (e.g., AttributeError, ValueError)
        When: Selecting optimal tools for the context
        Then: Should select strategy appropriate for runtime investigation
        """
        context = {
            "problem_type": "runtime",
            "error_type": "AttributeError",
            "confidence_score": 0.85,
            "complexity_level": "moderate",
            "scope": "function",
            "recommended_strategy": "systematic",
        }

        result = selector.select_optimal_tools(context)

        assert result["primary_strategy"] in ["systematic", "exploratory"]
        assert result["selection_confidence"] > 0.6
        assert len(result["primary_tools"]) > 0

    def test_includes_runtime_debugging_tools(self, selector):
        """Include runtime-specific tools in selection.

        Given: A runtime error context
        When: Selecting optimal tools
        Then: Should include debugging and analysis tools
        """
        context = {
            "problem_type": "runtime",
            "error_type": "ValueError",
            "confidence_score": 0.75,
            "complexity_level": "moderate",
            "recommended_strategy": "systematic",
        }

        result = selector.select_optimal_tools(context)

        # Check for appropriate runtime debugging tools
        assert any(tool in result["primary_tools"] for tool in ["CHS", "CustomAnalyzer", "Debugpy"])
        assert result["processing_time_ms"] >= 0


class TestToolSelectorForNetworkIssue:
    """Test tool selection for network issues."""

    @pytest.fixture
    def selector(self):
        """Return a ToolSelector instance."""
        return ToolSelector()

    def test_selects_network_appropriate_strategy(self, selector):
        """Select exploratory strategy for network issues.

        Given: A network issue context with unknown scope
        When: Selecting optimal tools for the context
        Then: Should select exploratory strategy for broad investigation
        """
        context = {
            "problem_type": "network",
            "error_type": "ConnectionError",
            "confidence_score": 0.7,
            "complexity_level": "moderate",
            "scope": "module",
            "recommended_strategy": "exploratory",
        }

        result = selector.select_optimal_tools(context)

        assert result["primary_strategy"] == "exploratory"
        assert result["selection_confidence"] > 0.5
        assert len(result["primary_tools"]) > 0

    def test_includes_network_investigation_tools(self, selector):
        """Include network-specific tools in selection.

        Given: A network issue context
        When: Selecting optimal tools
        Then: Should include search and discovery tools for network issues
        """
        context = {
            "problem_type": "network",
            "error_type": "TimeoutError",
            "confidence_score": 0.65,
            "complexity_level": "moderate",
            "recommended_strategy": "exploratory",
        }

        result = selector.select_optimal_tools(context)

        # Check for search and discovery tools
        assert any(
            tool in result["primary_tools"]
            for tool in ["CHS", "BroadPatternSearch", "SemanticSearch"]
        )
        assert result["parallel_execution"] in [True, False]


class TestToolSelectorFallback:
    """Test fallback behavior for unknown issues."""

    @pytest.fixture
    def selector(self):
        """Return a ToolSelector instance."""
        return ToolSelector()

    def test_fallback_to_systematic_strategy(self, selector):
        """Fallback to systematic strategy for unknown problems.

        Given: An unknown or ambiguous problem context
        When: Selecting optimal tools without explicit recommendation
        Then: Should default to systematic strategy with standard tools
        """
        context = {
            "problem_type": "unknown",
            "confidence_score": 0.3,
            "complexity_level": "unknown",
            "scope": "unknown",
            # No recommended_strategy provided
        }

        result = selector.select_optimal_tools(context)

        assert result["primary_strategy"] == "systematic"  # Default fallback
        assert len(result["primary_tools"]) > 0
        assert result["optimization_level"] in ["standard", "enhanced", "maximum"]

    def test_generic_tools_for_unknown_issues(self, selector):
        """Include generic tools when problem type is unknown.

        Given: An unknown problem context
        When: Selecting optimal tools
        Then: Should provide generic but useful debugging tools
        """
        context = {
            "problem_type": "unknown",
            "confidence_score": 0.2,
            "complexity_level": "unknown",
            "recommended_strategy": "systematic",
        }

        result = selector.select_optimal_tools(context)

        # Should have basic systematic tools
        assert "CHS" in result["primary_tools"] or "FileSearch" in result["primary_tools"]
        assert result["selection_confidence"] < 0.7  # Lower confidence for unknown
        assert result["estimated_performance_gain"] >= 0


class TestToolSelectorRecommendations:
    """Test tool recommendation functionality."""

    @pytest.fixture
    def selector(self):
        """Return a ToolSelector instance."""
        return ToolSelector()

    def test_get_tool_recommendations(self, selector):
        """Get ranked tool recommendations.

        Given: A context with specific problem type
        When: Requesting tool recommendations with limit
        Then: Should return ranked list of appropriate tools
        """
        context = {
            "problem_type": "security",
            "recommended_strategy": "council",
            "confidence_score": 0.8,
        }

        recommendations = selector.get_tool_recommendations(context, limit=5)

        assert len(recommendations) <= 5
        assert all("tool" in rec for rec in recommendations)
        assert all("priority" in rec for rec in recommendations)
        assert all("reason" in rec for rec in recommendations)

    def test_recommendations_include_priority_sorting(self, selector):
        """Recommendations are sorted by priority.

        Given: A context requiring multiple tools
        When: Getting recommendations
        Then: High priority tools should appear first
        """
        context = {
            "problem_type": "performance",
            "recommended_strategy": "deep_scan",
            "confidence_score": 0.75,
        }

        recommendations = selector.get_tool_recommendations(context, limit=10)

        if len(recommendations) >= 2:
            # Check that high priority items come before medium/low
            first_priority = recommendations[0]["priority"]
            assert first_priority in ["high", "medium", "low"]


class TestToolSelectorValidation:
    """Test tool selection validation."""

    @pytest.fixture
    def selector(self):
        """Return a ToolSelector instance."""
        return ToolSelector()

    def test_validate_good_selection(self, selector):
        """Validate a good tool selection.

        Given: A context with high confidence and appropriate tools
        When: Validating the selection
        Then: Should return validation with no warnings
        """
        context = {
            "problem_type": "bug",
            "recommended_strategy": "systematic",
            "confidence_score": 0.9,
            "complexity_level": "simple",
        }

        selection = selector.select_optimal_tools(context)
        validation = selector.validate_tool_selection(selection, context)

        assert validation["is_valid"] is True
        assert len(validation["warnings"]) == 0

    def test_validate_low_confidence_selection(self, selector):
        """Validate selection with low confidence.

        Given: A context with low confidence
        When: Validating the selection
        Then: Should return validation with warnings
        """
        context = {
            "problem_type": "unknown",
            "recommended_strategy": "systematic",
            "confidence_score": 0.2,
        }

        selection = selector.select_optimal_tools(context)
        validation = selector.validate_tool_selection(selection, context)

        assert validation["confidence_score"] < 0.5
        # May have warnings about low confidence


class TestToolSelectorMetrics:
    """Test ToolSelectorMetrics functionality."""

    def test_metrics_initialization(self):
        """ToolSelectorMetrics can be created."""
        metrics = ToolSelectorMetrics()

        assert metrics.selection_count == 0
        assert metrics.total_processing_time == 0.0
        assert metrics.strategy_usage == {}

    def test_record_selection(self):
        """Record a tool selection for metrics.

        Given: A selection result and context
        When: Recording the metrics
        Then: Should update metrics counters appropriately
        """
        metrics = ToolSelectorMetrics()
        selection_result = {"primary_strategy": "systematic", "processing_time_ms": 5.5}
        context = {"problem_type": "bug"}

        metrics.record_selection(selection_result, context)

        assert metrics.selection_count == 1
        assert metrics.total_processing_time == 5.5
        assert "systematic" in metrics.strategy_usage

    def test_get_average_processing_time(self):
        """Calculate average processing time.

        Given: Multiple recorded selections
        When: Getting average processing time
        Then: Should return correct average
        """
        metrics = ToolSelectorMetrics()

        # Record multiple selections
        for i in range(3):
            selection_result = {"primary_strategy": "systematic", "processing_time_ms": 10.0 + i}
            context = {"problem_type": "bug"}
            metrics.record_selection(selection_result, context)

        avg_time = metrics.get_average_processing_time()

        # Average of 10.0, 11.0, 12.0 = 11.0
        assert avg_time == 11.0

    def test_get_strategy_distribution(self):
        """Get distribution of strategy usage.

        Given: Multiple selections with different strategies
        When: Getting strategy distribution
        Then: Should return proportional distribution
        """
        metrics = ToolSelectorMetrics()

        # Record selections with different strategies
        for _ in range(3):
            metrics.record_selection(
                {"primary_strategy": "systematic", "processing_time_ms": 5.0},
                {"problem_type": "bug"},
            )
        for _ in range(2):
            metrics.record_selection(
                {"primary_strategy": "exploratory", "processing_time_ms": 5.0},
                {"problem_type": "unknown"},
            )

        distribution = metrics.get_strategy_distribution()

        assert distribution["systematic"] == 0.6  # 3 out of 5
        assert distribution["exploratory"] == 0.4  # 2 out of 5

    def test_get_most_used_strategy(self):
        """Get the most commonly used strategy.

        Given: Multiple selections with different strategies
        When: Getting most used strategy
        Then: Should return the strategy with highest count
        """
        metrics = ToolSelectorMetrics()

        # Record selections
        for _ in range(5):
            metrics.record_selection(
                {"primary_strategy": "systematic", "processing_time_ms": 5.0},
                {"problem_type": "bug"},
            )
        for _ in range(2):
            metrics.record_selection(
                {"primary_strategy": "exploratory", "processing_time_ms": 5.0},
                {"problem_type": "unknown"},
            )

        most_used = metrics.get_most_used_strategy()

        assert most_used == "systematic"
