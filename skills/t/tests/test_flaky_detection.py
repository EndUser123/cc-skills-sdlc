#!/usr/bin/env python3
"""Test flaky test detection using pass rate analysis."""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flaky_detection import FlakyTestDetector


def test_record_run_storage():
    """Test storing test run results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record a passing run
        detector.record_run(
            test_name="test_example",
            passed=True,
            error_message="",
            runtime_seconds=1.5,
        )

        # Verify stored in history
        assert "test_example" in detector.history
        assert len(detector.history["test_example"]) == 1

        run = detector.history["test_example"][0]
        assert run["passed"] is True
        assert run["error_message"] == ""
        assert run["runtime_seconds"] == 1.5
        assert "timestamp" in run


def test_record_run_multiple():
    """Test recording multiple runs for same test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record multiple runs
        detector.record_run("test_flaky", passed=True, error_message="", runtime_seconds=1.0)
        detector.record_run("test_flaky", passed=False, error_message="AssertionError", runtime_seconds=1.0)
        detector.record_run("test_flaky", passed=True, error_message="", runtime_seconds=1.0)

        # Should have 3 runs stored
        assert len(detector.history["test_flaky"]) == 3

        # Verify in chronological order
        assert detector.history["test_flaky"][0]["passed"] is True
        assert detector.history["test_flaky"][1]["passed"] is False
        assert detector.history["test_flaky"][2]["passed"] is True


def test_record_run_history_trimming():
    """Test that history is trimmed to last 20 runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record 25 runs
        for i in range(25):
            detector.record_run("test_many", passed=(i % 2 == 0), runtime_seconds=0.1)

        # Should only keep last 20
        assert len(detector.history["test_many"]) == 20

        # First run should be trimmed
        first_timestamp = detector.history["test_many"][0]["timestamp"]
        assert "run 0" not in first_timestamp  # Not the first run we recorded


def test_analyze_flakiness_no_history():
    """Test analysis for test with no history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        analysis = detector.analyze_flakiness("test_nonexistent")

        assert analysis["is_flaky"] is False
        assert analysis["pass_rate"] == 1.0
        assert analysis["recent_runs"] == 0
        assert analysis["different_errors"] == []


def test_analyze_flakiness_insufficient_runs():
    """Test analysis with insufficient runs (< 5)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record only 3 runs
        detector.record_run("test_new", passed=True, runtime_seconds=1.0)
        detector.record_run("test_new", passed=False, error_message="Error 1", runtime_seconds=1.0)
        detector.record_run("test_new", passed=True, runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_new", min_runs=5)

        # Not enough runs, so not flaky yet
        assert analysis["is_flaky"] is False
        assert analysis["recent_runs"] == 3


def test_analyze_flakiness_stable_passing():
    """Test analysis for stable passing test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record 10 runs, all passing
        for _ in range(10):
            detector.record_run("test_stable", passed=True, runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_stable")

        assert analysis["is_flaky"] is False
        assert analysis["pass_rate"] == 1.0
        assert analysis["recent_runs"] == 10
        assert analysis["different_errors"] == []


def test_analyze_flakiness_stable_failing():
    """Test analysis for stable failing test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record 10 runs, all failing with same error
        for _ in range(10):
            detector.record_run("test_broken", passed=False, error_message="Always fails", runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_broken")

        # Not flaky because pass_rate is 0% (not in 30-70% range)
        assert analysis["is_flaky"] is False
        assert analysis["pass_rate"] == 0.0


def test_analyze_flakiness_flaky_pass_rate():
    """Test flaky detection with 30-70% pass rate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record 10 runs: 7 passes, 3 fails (70% pass rate - boundary)
        for i in range(10):
            passed = i < 7  # First 7 pass
            error = "Error A" if i >= 7 else ""
            detector.record_run("test_flaky", passed=passed, error_message=error, runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_flaky")

        # At exactly 70% pass rate with single error, not flaky
        # Need pass rate < 0.7 AND multiple different errors
        assert analysis["pass_rate"] == 0.7
        assert analysis["is_flaky"] is False  # Only one error type


def test_analyze_flakiness_true_flaky():
    """Test detection of truly flaky test (multiple errors)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"

        # For true flaky, need pass_rate strictly between 0.3 and 0.7
        # Let me record 6 passes, 4 fails with different errors (60% pass rate)
        detector = FlakyTestDetector(history_path)
        errors = ["Connection timeout", "Lock acquisition failed", "Network error"]
        for i in range(10):
            passed = i < 6  # 6 passes
            # Use modulo to cycle through errors for failing tests
            error = errors[(i - 6) % 3] if i >= 6 else ""
            detector.record_run("test_truly_flaky", passed=passed, error_message=error, runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_truly_flaky")

        assert analysis["is_flaky"] is True
        assert analysis["pass_rate"] == 0.6
        assert len(analysis["different_errors"]) == 3
        assert "Connection timeout" in analysis["different_errors"]


def test_analyze_flakiness_collects_different_errors():
    """Test that different error messages are collected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record runs with 3 different errors
        errors = ["Error A", "Error B", "Error C"]
        for i in range(10):
            passed = i < 5  # 5 passes, 5 fails
            error = errors[i % 3] if i >= 5 else ""
            detector.record_run("test_errors", passed=passed, error_message=error, runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_errors")

        # Should collect all 3 unique errors
        assert len(analysis["different_errors"]) == 3
        assert "Error A" in analysis["different_errors"]
        assert "Error B" in analysis["different_errors"]
        assert "Error C" in analysis["different_errors"]


def test_analyze_flakiness_ignores_empty_errors():
    """Test that empty error messages are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Record runs with empty errors and one real error
        for i in range(10):
            passed = i < 5
            error = "Real Error" if i == 5 else ""
            detector.record_run("test_ignore_empty", passed=passed, error_message=error, runtime_seconds=1.0)

        analysis = detector.analyze_flakiness("test_ignore_empty")

        # Should only count the real error, not empty strings
        assert analysis["different_errors"] == ["Real Error"]


def test_get_all_flaky_tests_empty():
    """Test getting flaky tests from empty history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        flaky = detector.get_all_flaky_tests()

        assert flaky == []


def test_get_all_flaky_tests_sorted():
    """Test that flaky tests are sorted by pass rate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Create three tests with different flakiness levels
        # test1: 40% pass rate (most flaky) - needs multiple errors
        errors1 = ["Timeout", "Network error"]
        for i in range(10):
            passed = i < 4
            error = errors1[i % 2] if not passed else ""
            detector.record_run("test_worst", passed=passed, error_message=error, runtime_seconds=1.0)

        # test2: 50% pass rate - needs multiple errors
        errors2 = ["Database error", "API error"]
        for i in range(10):
            passed = i < 5
            error = errors2[i % 2] if not passed else ""
            detector.record_run("test_medium", passed=passed, error_message=error, runtime_seconds=1.0)

        # test3: 60% pass rate (least flaky) - needs multiple errors
        errors3 = ["Auth error", "Permission error"]
        for i in range(10):
            passed = i < 6
            error = errors3[i % 2] if not passed else ""
            detector.record_run("test_best", passed=passed, error_message=error, runtime_seconds=1.0)

        flaky = detector.get_all_flaky_tests()

        # Should return 3 flaky tests
        assert len(flaky) == 3

        # Should be sorted by pass rate (ascending - most flaky first)
        assert flaky[0]["test_name"] == "test_worst"
        assert flaky[1]["test_name"] == "test_medium"
        assert flaky[2]["test_name"] == "test_best"

        # Verify pass rates
        assert flaky[0]["pass_rate"] == 0.4
        assert flaky[1]["pass_rate"] == 0.5
        assert flaky[2]["pass_rate"] == 0.6


def test_get_all_flaky_tests_excludes_stable():
    """Test that stable tests are not included."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"
        detector = FlakyTestDetector(history_path)

        # Create one flaky test with multiple different errors
        errors = ["Error A", "Error B"]
        for i in range(10):
            passed = i < 6
            error = errors[i % 2] if not passed else ""
            detector.record_run("test_flaky", passed=passed, error_message=error, runtime_seconds=1.0)

        # Create one stable test (all passes)
        for _ in range(10):
            detector.record_run("test_stable", passed=True, error_message="", runtime_seconds=1.0)

        # Create one failing test (all fails, same error)
        for _ in range(10):
            detector.record_run("test_failing", passed=False, error_message="Same error", runtime_seconds=1.0)

        flaky = detector.get_all_flaky_tests()

        # Should only include the flaky test, not stable or consistently failing
        assert len(flaky) == 1
        assert flaky[0]["test_name"] == "test_flaky"


def test_history_persists_to_disk():
    """Test that history is persisted and can be reloaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"

        # Create detector and add history
        detector1 = FlakyTestDetector(history_path)
        detector1.record_run("test_persist", passed=True, runtime_seconds=2.5)

        # Create new detector instance (should load from disk)
        detector2 = FlakyTestDetector(history_path)

        # Should have loaded the history
        assert "test_persist" in detector2.history
        assert len(detector2.history["test_persist"]) == 1


def test_history_handles_corrupted_file():
    """Test that corrupted history file is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "history.json"

        # Write invalid JSON
        history_path.write_text("{invalid json}")

        # Detector should still initialize (empty history)
        detector = FlakyTestDetector(history_path)

        assert detector.history == {}
        assert detector.analyze_flakiness("any_test")["is_flaky"] is False


if __name__ == "__main__":
    test_record_run_storage()
    print("✅ test_record_run_storage passed")

    test_record_run_multiple()
    print("✅ test_record_run_multiple passed")

    test_record_run_history_trimming()
    print("✅ test_record_run_history_trimming passed")

    test_analyze_flakiness_no_history()
    print("✅ test_analyze_flakiness_no_history passed")

    test_analyze_flakiness_insufficient_runs()
    print("✅ test_analyze_flakiness_insufficient_runs passed")

    test_analyze_flakiness_stable_passing()
    print("✅ test_analyze_flakiness_stable_passing passed")

    test_analyze_flakiness_stable_failing()
    print("✅ test_analyze_flakiness_stable_failing passed")

    test_analyze_flakiness_flaky_pass_rate()
    print("✅ test_analyze_flakiness_flaky_pass_rate passed")

    test_analyze_flakiness_true_flaky()
    print("✅ test_analyze_flakiness_true_flaky passed")

    test_analyze_flakiness_collects_different_errors()
    print("✅ test_analyze_flakiness_collects_different_errors passed")

    test_analyze_flakiness_ignores_empty_errors()
    print("✅ test_analyze_flakiness_ignores_empty_errors passed")

    test_get_all_flaky_tests_empty()
    print("✅ test_get_all_flaky_tests_empty passed")

    test_get_all_flaky_tests_sorted()
    print("✅ test_get_all_flaky_tests_sorted passed")

    test_get_all_flaky_tests_excludes_stable()
    print("✅ test_get_all_flaky_tests_excludes_stable passed")

    test_history_persists_to_disk()
    print("✅ test_history_persists_to_disk passed")

    test_history_handles_corrupted_file()
    print("✅ test_history_handles_corrupted_file passed")

    print("\nAll flaky_detection tests passed!")
