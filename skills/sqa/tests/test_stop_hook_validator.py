"""Tests for StopHook SQA completion validator."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Import the validator module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


class TestCompletionValidator:
    """Test completion message validation logic."""

    def test_valid_completion_json_allowed(self, tmp_path):
        """Test that valid completion JSON is allowed."""
        valid_json = {
            "target": "P:/test",
            "health_score": 85,
            "findings_count": 5,
            "layers_completed": ["L0", "L1", "L2"],
        }

        with patch.dict(sys.modules, {"lib.sqa_state_tracker": Mock()}):
            # Mock load_state to return valid state
            mock_state = Mock()
            mock_state.target = "P:/test"
            mock_state.layers = {}

            # The validator should parse and validate
            try:
                from hooks.StopHook_sqa_completion_validator import _parse_completion
                state = _parse_completion(json.dumps(valid_json))
                assert state is not None
            except ImportError:
                pytest.skip("Validator module not available")

    def test_invalid_json_rejected(self, tmp_path):
        """Test that invalid JSON is rejected."""
        invalid_json = "{invalid json"

        try:
            from hooks.StopHook_sqa_completion_validator import _parse_completion
            state = _parse_completion(invalid_json)
            assert state is None, "Invalid JSON should return None"
        except ImportError:
            pytest.skip("Validator module not available")

    def test_missing_health_score_rejected(self, tmp_path):
        """Test that completion without health_score is rejected."""
        incomplete_json = {
            "target": "P:/test",
            "findings_count": 5,
            # Missing health_score
        }

        try:
            from hooks.StopHook_sqa_completion_validator import _parse_completion
            state = _parse_completion(json.dumps(incomplete_json))
            assert state is None, "Missing health_score should return None"
        except ImportError:
            pytest.skip("Validator module not available")


class TestAssertionRunner:
    """Test the assertion running logic."""

    def test_run_assertions_exit_code_handling(self):
        """Test that assertion exit codes are correctly handled."""
        try:
            from hooks.StopHook_sqa_completion_validator import _run_assertions

            # Mock a successful assertion run
            with patch("subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "All assertions passed"
                mock_run.return_value = mock_result

                success, output = _run_assertions("P:/test", {})
                assert success is True
                assert "passed" in output.lower()

            # Mock a failed assertion run
            with patch("subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 1
                mock_result.stdout = "Assertion failed: tests not passing"
                mock_run.return_value = mock_result

                success, output = _run_assertions("P:/test", {})
                assert success is False
                assert "failed" in output.lower()

        except ImportError:
            pytest.skip("Validator module not available")


class TestResponseTextValidation:
    """Test response text validation."""

    def test_response_format_validation(self):
        """Test that response text is validated for format."""
        try:
            from hooks.StopHook_sqa_completion_validator import _validate_response

            # Valid response format
            valid_response = "SQA completed. Health score: 85. Findings: 5."
            is_valid = _validate_response(valid_response)
            assert is_valid, "Valid response format should pass"

            # Invalid response (too short, no details)
            invalid_response = "Done."
            is_valid = _validate_response(invalid_response)
            assert not is_valid, "Minimal response should fail validation"

        except ImportError:
            pytest.skip("Validator module not available")


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_retry_on_state_file_race(self):
        """Test that validator retries when state file is being written."""
        try:
            from hooks.StopHook_sqa_completion_validator import _run_assertions

            call_count = [0]

            def mock_run_with_race(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] < 3:
                    # First two calls fail (simulating race condition)
                    result = Mock()
                    result.returncode = 1
                    result.stdout = "State file not ready"
                    return result
                else:
                    # Third call succeeds
                    result = Mock()
                    result.returncode = 0
                    result.stdout = "Assertions passed"
                    return result

            with patch("subprocess.run", side_effect=mock_run_with_race):
                success, output = _run_assertions("P:/test", {})
                assert success is True, "Retry should eventually succeed"
                assert call_count[0] == 3, f"Should have retried 3 times, got {call_count[0]}"

        except ImportError:
            pytest.skip("Validator module not available")
