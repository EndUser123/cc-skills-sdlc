"""Tests for core.context_analyzer module - Execution context analysis.

These tests verify context extraction, environment variable capture,
stack trace analysis, and call chain reconstruction functionality.
"""

import os

from rca.core.context_analyzer import ContextAnalyzer


class TestContextAnalyzerExtractContext:
    """Test context extraction from execution."""

    def test_extract_context_from_execution_state(self):
        """
        Test that extract_context captures execution state.

        Given: An execution state with variables and call stack
        When: extract_context is called
        Then: Context should contain captured state information
        """
        analyzer = ContextAnalyzer()
        execution_state = {
            "variables": {"x": 10, "y": 20},
            "function": "process_data",
            "line_number": 42,
        }

        # This feature doesn't exist yet - test will fail
        context = analyzer.extract_context(execution_state)

        assert context is not None
        assert "variables" in context
        assert context["variables"]["x"] == 10
        assert context["function"] == "process_data"

    def test_extract_context_with_empty_state(self):
        """
        Test that extract_context handles empty execution state.

        Given: An empty execution state
        When: extract_context is called
        Then: Should return minimal valid context
        """
        analyzer = ContextAnalyzer()
        execution_state = {}

        context = analyzer.extract_context(execution_state)

        assert context is not None
        assert "timestamp" in context


class TestContextAnalyzerEnvironmentVariables:
    """Test environment variable capture."""

    def test_capture_environment_variables(self):
        """
        Test that capture_environment captures relevant environment variables.

        Given: Environment variables are set
        When: capture_environment is called
        Then: Should capture relevant debug-related environment variables
        """
        analyzer = ContextAnalyzer()

        # Set test environment variables
        os.environ["TEST_VAR"] = "test_value"
        os.environ["PATH"] = "/usr/bin:/bin"

        # This feature doesn't exist yet - test will fail
        env_context = analyzer.capture_environment()

        assert env_context is not None
        assert isinstance(env_context, dict)
        assert "TEST_VAR" in env_context
        assert env_context["TEST_VAR"] == "test_value"

    def test_capture_environment_filters_sensitive_data(self):
        """
        Test that capture_environment filters sensitive environment variables.

        Given: Environment contains sensitive variables (passwords, tokens)
        When: capture_environment is called
        Then: Should redact or exclude sensitive variables
        """
        analyzer = ContextAnalyzer()

        os.environ["SECRET_KEY"] = "super_secret_value"
        os.environ["API_TOKEN"] = "api_token_value"
        os.environ["NORMAL_VAR"] = "normal_value"

        env_context = analyzer.capture_environment()

        # Sensitive data should be redacted
        assert "SECRET_KEY" not in env_context or env_context["SECRET_KEY"] == "***REDACTED***"
        assert "API_TOKEN" not in env_context or env_context["API_TOKEN"] == "***REDACTED***"
        # Normal variables should be captured
        assert env_context.get("NORMAL_VAR") == "normal_value"

    def test_capture_environment_with_prefix_filter(self):
        """
        Test that capture_environment can filter by variable prefix.

        Given: Environment variables with different prefixes
        When: capture_environment is called with prefix filter
        Then: Should only capture variables matching the prefix
        """
        analyzer = ContextAnalyzer()

        os.environ["APP_DEBUG"] = "true"
        os.environ["APP_VERSION"] = "1.0"
        os.environ["SYSTEM_VAR"] = "value"

        env_context = analyzer.capture_environment(prefix="APP_")

        assert "APP_DEBUG" in env_context
        assert "APP_VERSION" in env_context
        assert "SYSTEM_VAR" not in env_context


class TestContextAnalyzerStackTraceAnalysis:
    """Test stack trace analysis functionality."""

    def test_analyze_stack_trace_parsing(self):
        """
        Test that analyze_stack_trace parses Python stack traces.

        Given: A Python stack trace string
        When: analyze_stack_trace is called
        Then: Should extract frames, files, line numbers, and functions
        """
        analyzer = ContextAnalyzer()
        stack_trace = """
Traceback (most recent call last):
  File "src/handler.py", line 42, in process_request
    raise ValueError("Invalid data")
  File "src/processor.py", line 15, in validate
    validate_data(data)
ValueError: Invalid data
"""

        # This feature doesn't exist yet - test will fail
        analysis = analyzer.analyze_stack_trace(stack_trace)

        assert analysis is not None
        assert "frames" in analysis
        assert len(analysis["frames"]) >= 1
        assert analysis["frames"][0]["file"] == "src/handler.py"
        assert analysis["frames"][0]["line"] == 42
        assert analysis["frames"][0]["function"] == "process_request"
        assert analysis["exception_type"] == "ValueError"

    def test_analyze_stack_trace_extract_locals(self):
        """
        Test that analyze_stack_trace can extract local variables from frames.

        Given: A stack trace with local variable information
        When: analyze_stack_trace is called with locals enabled
        Then: Should capture local variables from each frame
        """
        analyzer = ContextAnalyzer()
        stack_trace_with_locals = """
Traceback (most recent call last):
  File "test.py", line 10, in <module>
    x = 1 / 0
ZeroDivisionError: division by zero
"""

        analysis = analyzer.analyze_stack_trace(stack_trace_with_locals, include_locals=True)

        assert "locals" in analysis
        assert isinstance(analysis["locals"], dict)

    def test_analyze_stack_trace_malformed_input(self):
        """
        Test that analyze_stack_trace handles malformed input gracefully.

        Given: A malformed or incomplete stack trace
        When: analyze_stack_trace is called
        Then: Should return analysis with error information
        """
        analyzer = ContextAnalyzer()
        malformed_trace = "This is not a valid stack trace"

        analysis = analyzer.analyze_stack_trace(malformed_trace)

        assert analysis is not None
        assert "error" in analysis or "frames" in analysis


class TestContextAnalyzerCallChainReconstruction:
    """Test call chain reconstruction functionality."""

    def test_reconstruct_call_chain_from_stack_trace(self):
        """
        Test that reconstruct_call_chain builds execution flow from stack trace.

        Given: A stack trace with multiple frames
        When: reconstruct_call_chain is called
        Then: Should reconstruct the call chain in execution order
        """
        analyzer = ContextAnalyzer()
        stack_trace = """
Traceback (most recent call last):
  File "src/main.py", line 50, in main
    result = handler.process(data)
  File "src/handler.py", line 30, in process
    validated = validator.validate(data)
  File "src/validator.py", line 15, in validate
    raise ValueError("Invalid")
ValueError: Invalid
"""

        # This feature doesn't exist yet - test will fail
        call_chain = analyzer.reconstruct_call_chain(stack_trace)

        assert call_chain is not None
        assert len(call_chain) == 3
        # Check order (main -> handler -> validator)
        assert call_chain[0]["function"] == "main"
        assert call_chain[1]["function"] == "process"
        assert call_chain[2]["function"] == "validate"

    def test_reconstruct_call_chain_with_context(self):
        """
        Test that reconstruct_call_chain includes context for each call.

        Given: A stack trace with detailed frame information
        When: reconstruct_call_chain is called with context enabled
        Then: Should include arguments and return values in call chain
        """
        analyzer = ContextAnalyzer()
        stack_trace = """
Traceback (most recent call last):
  File "app.py", line 10, in <module>
    process(user_id=123)
  File "app.py", line 5, in process
    validate(user_id)
TypeError: 'NoneType' object is not callable
"""

        call_chain = analyzer.reconstruct_call_chain(stack_trace, include_context=True)

        assert call_chain is not None
        assert "context" in call_chain[0] or "args" in call_chain[0]

    def test_reconstruct_call_chain_detects_recursion(self):
        """
        Test that reconstruct_call_chain detects recursive calls.

        Given: A stack trace with recursive function calls
        When: reconstruct_call_chain is called
        Then: Should identify and mark recursive patterns
        """
        analyzer = ContextAnalyzer()
        recursive_trace = """
Traceback (most recent call last):
  File "recursive.py", line 10, in factorial
    return n * factorial(n - 1)
  File "recursive.py", line 10, in factorial
    return n * factorial(n - 1)
  File "recursive.py", line 10, in factorial
    return n * factorial(n - 1)
RecursionError: maximum recursion depth exceeded
"""

        call_chain = analyzer.reconstruct_call_chain(recursive_trace)

        assert call_chain is not None
        assert "recursion_detected" in call_chain or len(call_chain) > 2

    def test_reconstruct_call_chain_empty_input(self):
        """
        Test that reconstruct_call_chain handles empty input.

        Given: An empty or None stack trace
        When: reconstruct_call_chain is called
        Then: Should return empty call chain
        """
        analyzer = ContextAnalyzer()

        call_chain = analyzer.reconstruct_call_chain("")

        assert call_chain is not None
        assert len(call_chain) == 0
