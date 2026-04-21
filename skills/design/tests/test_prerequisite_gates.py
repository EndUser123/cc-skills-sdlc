"""Tests for prerequisite gate false positive prevention in arch skill.

These tests verify that the semantic analysis in Stage 0 (Pre-Flight Checks)
correctly distinguishes optimization queries from genuine prerequisite needs.

Run with: pytest P:/.claude/skills/arch/tests/test_prerequisite_gates.py -v

TDD RED Phase: These tests FAIL because prerequisite_analyzer module doesn't exist yet.
"""

import pytest

# This module will be implemented in GREEN phase
# For RED phase, the import will fail and tests will fail as expected
PREREQUISITE_ANALYZER_EXISTS = False
PrerequisiteAnalyzer = None

try:
    from ..prerequisite_analyzer import PrerequisiteAnalyzer

    PREREQUISITE_ANALYZER_EXISTS = True
except (ImportError, ValueError):
    # Module doesn't exist yet - this is RED phase, tests should fail
    PREREQUISITE_ANALYZER_EXISTS = False
    PrerequisiteAnalyzer = None


@pytest.fixture(autouse=True)
def skip_if_not_implemented():
    """Skip tests with a clear message if prerequisite_analyzer doesn't exist.

    For proper TDD RED phase, we want tests to FAIL, not skip.
    But pytest will error before tests run if PrerequisiteAnalyzer is None.
    This fixture provides a clear failure message.
    """
    if not PREREQUISITE_ANALYZER_EXISTS:
        pytest.fail(
            "RED PHASE: prerequisite_analyzer module not implemented yet. "
            "Create P:/.claude/skills/arch/prerequisite_analyzer.py with "
            "PrerequisiteAnalyzer class to proceed to GREEN phase."
        )


class TestOptimizationQueriesDoNotTriggerPrerequisiteGates:
    """Tests that optimization/improvement queries proceed directly to architecture.

    These tests verify FALSE POSITIVE PREVENTION - queries like "improve X",
    "optimize Y", "harden Z" should NOT trigger prerequisite gates because the
    user has clear context and intent.
    """

    def test_improve_memory_system_does_not_trigger_prerequisite_gate(self):
        """Test that "improve memory system" does NOT trigger prerequisite gate.

        Given: Query "improve memory system"
        When: Analyzed for prerequisite gates
        Then: No gate should trigger (should proceed to architecture)
        And: Query should be identified as optimization
        """
        # Arrange
        query = "improve memory system"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is False, (
            f"Optimization query should NOT trigger prerequisite gate. "
            f"Got gate_type: {result['gate_type']}, reason: {result['reason']}"
        )
        assert result["gate_type"] is None
        assert result["is_optimization"] is True

    def test_optimize_x_proceeds_directly_to_architecture(self):
        """Test that "optimize X" queries proceed directly to architecture.

        Given: Query "optimize caching layer"
        When: Analyzed for prerequisite gates
        Then: No gate should trigger
        And: Query should be identified as optimization
        """
        # Arrange
        query = "optimize caching layer"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is False, (
            f'"optimize X" query should NOT trigger prerequisite gate. '
            f"Got gate_type: {result['gate_type']}, reason: {result['reason']}"
        )
        assert result["gate_type"] is None
        assert result["is_optimization"] is True

    def test_harden_y_does_not_trigger_prd_gate(self):
        """Test that "harden Y" queries do not trigger /prd gate.

        Given: Query "harden security layer"
        When: Analyzed for prerequisite gates
        Then: No gate should trigger
        And: Query should be identified as optimization
        """
        # Arrange
        query = "harden security layer"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is False, (
            f'"harden Y" query should NOT trigger /prd gate. '
            f"Got gate_type: {result['gate_type']}, reason: {result['reason']}"
        )
        assert result["gate_type"] is None
        assert result["is_optimization"] is True

    def test_enhance_query_does_not_trigger_gate(self):
        """Test that "enhance X" queries do not trigger prerequisite gates.

        Given: Query "enhance error handling"
        When: Analyzed for prerequisite gates
        Then: No gate should trigger
        """
        # Arrange
        query = "enhance error handling"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is False
        assert result["gate_type"] is None
        assert result["is_optimization"] is True

    def test_stabilize_query_does_not_trigger_gate(self):
        """Test that "stabilize X" queries do not trigger prerequisite gates.

        Given: Query "stabilize connection pool"
        When: Analyzed for prerequisite gates
        Then: No gate should trigger
        """
        # Arrange
        query = "stabilize connection pool"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is False
        assert result["gate_type"] is None
        assert result["is_optimization"] is True


class TestGenuinePrerequisiteNeedsTriggerGates:
    """Tests that genuine prerequisite needs DO trigger appropriate gates.

    These tests verify POSITIVE CASES - queries that explicitly indicate
    missing prerequisites should trigger the appropriate gates.
    """

    def test_from_requirements_triggers_prd_gate(self):
        """Test that "from requirements" DOES trigger prerequisite gate.

        Given: Query containing "from requirements"
        When: Analyzed for prerequisite gates
        Then: /prd gate should trigger
        """
        # Arrange
        query = "design api from requirements"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is True, (
            f"Query with 'from requirements' SHOULD trigger /prd gate. "
            f"Got should_trigger_gate: {result['should_trigger_gate']}"
        )
        assert result["gate_type"] == "/prd"
        assert result["reason"] is not None

    def test_how_is_x_structured_triggers_discover_gate(self):
        """Test that "how is X structured" DOES trigger /discover gate.

        Given: Query "how is X structured"
        When: Analyzed for prerequisite gates
        Then: /discover gate should trigger
        """
        # Arrange
        query = "how is x structured"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is True, (
            f"Query 'how is X structured' SHOULD trigger /discover gate. "
            f"Got should_trigger_gate: {result['should_trigger_gate']}"
        )
        assert result["gate_type"] == "/discover"
        assert result["reason"] is not None
        assert result["is_optimization"] is False

    def test_why_failing_triggers_debug_gate(self):
        """Test that "why failing" DOES trigger /debug gate.

        Given: Query "why failing"
        When: Analyzed for prerequisite gates
        Then: /debug gate should trigger
        """
        # Arrange
        query = "why failing"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is True, (
            f"Query 'why failing' SHOULD trigger /debug gate. "
            f"Got should_trigger_gate: {result['should_trigger_gate']}"
        )
        assert result["gate_type"] == "/debug"
        assert result["reason"] is not None
        assert result["is_optimization"] is False

    def test_explicit_prd_request_triggers_gate(self):
        """Test that explicit PRD requests trigger /prd gate.

        Given: Query "PRD needed for architecture"
        When: Analyzed for prerequisite gates
        Then: /prd gate should trigger
        """
        # Arrange
        query = "PRD needed for architecture"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is True
        assert result["gate_type"] == "/prd"

    def test_where_are_requirements_triggers_prd_gate(self):
        """Test that "where are requirements" triggers /prd gate.

        Given: Query "where are requirements"
        When: Analyzed for prerequisite gates
        Then: /prd gate should trigger
        """
        # Arrange
        query = "where are requirements"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is True
        assert result["gate_type"] == "/prd"


class TestSemanticAnalysisDistinguishesOptimizationFromPrerequisites:
    """Tests that semantic analysis correctly distinguishes query types.

    These tests verify that the analyzer understands the difference between:
    - "improve X" (optimization, no gate)
    - "improve X from requirements" (optimization + explicit request, gate)
    """

    def test_optimization_without_requirements_proceeds(self):
        """Test optimization query without "from requirements" proceeds.

        This is a key distinction - "improve X" should proceed,
        but "design X from requirements" should trigger /prd.
        """
        # Arrange
        query = "improve authentication system"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is False
        assert result["is_optimization"] is True

    def test_optimization_with_requirements_triggers_prd(self):
        """Test that optimization + explicit "from requirements" triggers /prd.

        Even though it's an optimization query, if it explicitly references
        requirements, it should still trigger the PRD gate.
        """
        # Arrange
        query = "improve authentication from requirements"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert result["should_trigger_gate"] is True, (
            f"Optimization query with 'from requirements' should trigger /prd"
        )
        assert result["gate_type"] == "/prd"
        assert result["is_optimization"] is True

    def test_case_insensitive_pattern_matching(self):
        """Test that pattern matching is case-insensitive.

        Given: Queries with varying case
        When: Analyzed for prerequisite gates
        Then: Patterns should match regardless of case
        """
        # Test that case variations work
        test_cases = [
            ("IMPROVE memory system", False, "optimization in all caps"),
            ("Improve Memory System", False, "title case"),
            ("Why FAILING", True, "debug in all caps"),
            ("HOW IS X STRUCTURED", True, "discover in all caps"),
            ("From Requirements", True, "prd in title case"),
        ]

        for query, expected_trigger, description in test_cases:
            result = PrerequisiteAnalyzer.analyze(query)
            assert result["should_trigger_gate"] == expected_trigger, (
                f"Failed for {description}: query='{query}', "
                f"expected trigger={expected_trigger}, got {result['should_trigger_gate']}"
            )

    def test_whitespace_handling(self):
        """Test that queries with extra whitespace are handled correctly.

        Given: Queries with irregular whitespace
        When: Analyzed for prerequisite gates
        Then: Should match patterns correctly
        """
        test_cases = [
            ("  improve memory system  ", False),
            ("\toptimize caching\t", False),
            ("\n\nharden security\n\n", False),
            ("  why failing  ", True),
        ]

        for query, expected_trigger in test_cases:
            result = PrerequisiteAnalyzer.analyze(query)
            assert result["should_trigger_gate"] == expected_trigger, (
                f"Failed for query with irregular whitespace: '{query}'"
            )
