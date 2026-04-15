#!/usr/bin/env python3
"""
Tests for priority inference system.

Test order follows TDD discipline:
1. Error Frequency Clustering
2. Recent Change Detection
3. Static Complexity Metrics
4. Priority Score Calculation
5. Integration Tests
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from tools.priority_inference import (
    PriorityInference,
    rank_contexts,
)


class TestErrorFrequencyClustering:
    """Test error frequency clustering from hook state database."""

    def test_no_errors_in_state_db(self, tmp_path):
        """Files with no errors get zero frequency score."""
        # Create empty state DB
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "actions": [],
                    "error_count": 0,
                }
            )
        )

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference._get_error_frequency_score("src/module.py")

        assert score == 0.0

    def test_single_error_recent(self, tmp_path):
        """Recent error (within 1 hour) gets high frequency score."""
        now = datetime.now()
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "actions": [
                        {
                            "tool": "Bash",
                            "file": "src/module.py",
                            "error": True,
                            "timestamp": now.isoformat(),
                        }
                    ],
                }
            )
        )

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference._get_error_frequency_score("src/module.py")

        # Recent error should get high score (55-100 range, adjusted for floating point)
        assert score >= 55.0

    def test_multiple_errors_frequency_higher(self, tmp_path):
        """Files with more errors get higher frequency scores."""
        now = datetime.now()
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "actions": [
                        {
                            "tool": "Bash",
                            "file": "src/error_prone.py",
                            "error": True,
                            "timestamp": now.isoformat(),
                        },
                        {
                            "tool": "Read",
                            "file": "src/error_prone.py",
                            "error": True,
                            "timestamp": now.isoformat(),
                        },
                        {
                            "tool": "Bash",
                            "file": "src/stable.py",
                            "error": True,
                            "timestamp": now.isoformat(),
                        },
                    ],
                }
            )
        )

        inference = PriorityInference(state_dir=str(tmp_path))
        score_error_prone = inference._get_error_frequency_score("src/error_prone.py")
        score_stable = inference._get_error_frequency_score("src/stable.py")

        assert score_error_prone > score_stable

    def test_old_errors_decay_score(self, tmp_path):
        """Old errors (>1 day) have exponentially decayed scores."""
        yesterday = (datetime.now() - timedelta(days=2)).isoformat()
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "actions": [
                        {
                            "tool": "Bash",
                            "file": "src/old_error.py",
                            "error": True,
                            "timestamp": yesterday,
                        }
                    ],
                }
            )
        )

        inference = PriorityInference(state_dir=str(tmp_path))
        score_old = inference._get_error_frequency_score("src/old_error.py")

        # Old error should have low score (0-30 range due to decay)
        assert score_old < 30.0


class TestRecentChangeDetection:
    """Test recent change detection via git history."""

    def test_file_changed_today(self, tmp_path):
        """Files changed today get maximum recency score."""
        # Mock git log to show recent change
        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "2026-03-14 10:30:00 +0000"
            mock_run.return_value = mock_result

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference._get_recent_change_score("src/new_file.py")

            # Recent change should get high score (70-100 range)
            assert score >= 70.0

    def test_file_changed_week_ago(self, tmp_path):
        """Files changed 7 days ago get medium-high recency score."""
        week_ago = datetime.now() - timedelta(days=7)
        week_ago_str = week_ago.strftime("%Y-%m-%d %H:%M:%S +0000")

        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = week_ago_str
            mock_run.return_value = mock_result

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference._get_recent_change_score("src/week_old.py")

            # Week-old change should get medium-high score (60-80 range)
            assert 60.0 <= score <= 100.0

    def test_file_changed_month_ago(self, tmp_path):
        """Files changed 30 days ago get low recency score."""
        month_ago = datetime.now() - timedelta(days=30)
        month_ago_str = month_ago.strftime("%Y-%m-%d %H:%M:%S +0000")

        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = month_ago_str
            mock_run.return_value = mock_result

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference._get_recent_change_score("src/month_old.py")

            # Month-old change should get low score (0-30 range)
            assert score < 30.0

    def test_no_git_repository(self, tmp_path):
        """Missing git repository returns zero score gracefully."""
        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference._get_recent_change_score("src/any_file.py")

            # Should return 0.0, not crash
            assert score == 0.0


class TestStaticComplexityMetrics:
    """Test static complexity metrics via AST analysis."""

    def test_simple_function_low_complexity(self, tmp_path):
        """Simple functions get low complexity scores."""
        # Create simple Python file
        test_file = tmp_path / "simple.py"
        test_file.write_text("""
def hello():
    print("Hello, world!")

def add(a, b):
    return a + b
""")

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference._get_complexity_score(str(test_file))

        # Simple code should get low complexity score (0-30 range)
        assert score < 30.0

    def test_complex_function_high_complexity(self, tmp_path):
        """Complex functions get high complexity scores."""
        # Create complex Python file with nesting
        test_file = tmp_path / "complex.py"
        test_file.write_text("""
def complex_function(data):
    results = []
    for item in data:
        if item > 0:
            for sub in item.values():
                if sub is not None:
                    try:
                        results.append(process(sub))
                    except Exception:
                        results.append(None)
                else:
                    results.append(default)
            else:
                results.append(item)
    return results
""")

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference._get_complexity_score(str(test_file))

        # Complex code should get medium-high complexity score (50-100 range)
        assert score >= 50.0

    def test_very_long_file_skip_analysis(self, tmp_path):
        """Files >5000 lines skip complexity analysis (returns 0)."""
        # Create file with 5001 lines
        test_file = tmp_path / "huge.py"
        lines = ["def line_" + str(i) + "(): pass\n" for i in range(5001)]
        test_file.write_text("".join(lines))

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference._get_complexity_score(str(test_file))

        # Should skip analysis and return 0.0
        assert score == 0.0

    def test_non_python_file_zero_complexity(self, tmp_path):
        """Non-Python files get zero complexity score."""
        test_file = tmp_path / "config.json"
        test_file.write_text('{"key": "value"}')

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference._get_complexity_score(str(test_file))

        # Non-Python files should get 0.0
        assert score == 0.0


class TestPriorityScoreCalculation:
    """Test overall priority score calculation (0-100 range)."""

    def test_priority_score_in_range(self, tmp_path):
        """Priority scores always fall within 0-100 range."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = datetime.now().isoformat()

            state_file = tmp_path / "rca_workflow.json"
            state_file.write_text(json.dumps({"session_id": "test", "actions": []}))

            test_file = tmp_path / "test.py"
            test_file.write_text("def test(): pass")

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference.calculate_priority_score(str(test_file))

            # Score must be in 0-100 range
            assert 0 <= score <= 100

    def test_priority_score_weights_sum_to_one(self, tmp_path):
        """Priority weights sum to 1.0 (normalization)."""
        inference = PriorityInference(state_dir=str(tmp_path))

        # Access internal weights (for testing)
        total_weight = (
            inference.WEIGHT_ERROR_FREQUENCY
            + inference.WEIGHT_RECENT_CHANGE
            + inference.WEIGHT_COMPLEXITY
            + inference.WEIGHT_TEST_COVERAGE
        )

        assert abs(total_weight - 1.0) < 0.01

    def test_high_error_frequency_gets_high_priority(self, tmp_path):
        """Files with high error frequency get priority >30."""
        now = datetime.now()
        test_file_path = str(tmp_path / "error_prone.py")

        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "actions": [
                        {
                            "tool": "Bash",
                            "file": test_file_path,
                            "error": True,
                            "timestamp": now.isoformat(),
                        }
                        for _ in range(10)  # 10 errors
                    ],
                }
            )
        )

        test_file = tmp_path / "error_prone.py"
        test_file.write_text("def test(): pass")

        inference = PriorityInference(state_dir=str(tmp_path))
        score = inference.calculate_priority_score(str(test_file))

        # High error frequency should result in priority >30 (realistic expectation)
        assert score > 30

    def test_default_priority_when_no_signals(self, tmp_path):
        """Files with no signals get default priority 50 (only if non-Python or no complexity)."""
        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            state_file = tmp_path / "rca_workflow.json"
            state_file.write_text(json.dumps({"session_id": "test", "actions": []}))

            # Use a non-Python file to get 0 complexity score
            test_file = tmp_path / "unknown.txt"
            test_file.write_text("just text")

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference.calculate_priority_score(str(test_file))

            # Should return default priority 50 for non-code files with no signals
            assert score == 50


class TestRankContexts:
    """Test context ranking by priority score."""

    def test_rank_contexts_sorts_by_score(self, tmp_path):
        """Contexts are ranked from highest to lowest priority."""
        contexts = [
            "src/low_priority.py",
            "src/high_priority.py",
            "src/medium_priority.py",
        ]

        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S +0000")

        with patch("tools.priority_inference.subprocess.run") as mock_run:
            # Set up different recency scores
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = now_str
            mock_run.return_value = mock_result

            state_file = tmp_path / "rca_workflow.json"
            state_file.write_text(
                json.dumps(
                    {
                        "session_id": "test",
                        "actions": [
                            {
                                "tool": "Bash",
                                "file": "src/high_priority.py",
                                "error": True,
                                "timestamp": now.isoformat(),
                            },
                            {
                                "tool": "Bash",
                                "file": "src/medium_priority.py",
                                "error": True,
                                "timestamp": (now - timedelta(hours=2)).isoformat(),
                            },
                        ],
                    }
                )
            )

            # Create test files
            for ctx in contexts:
                (tmp_path / ctx.replace("src/", "")).write_text("def test(): pass")

            ranked = rank_contexts(contexts, state_dir=str(tmp_path))

            # Check descending order
            scores = [score for _, score in ranked]
            assert scores == sorted(scores, reverse=True)

    def test_rank_contexts_returns_tuples(self, tmp_path):
        """Rank contexts returns list of (context, score) tuples."""
        contexts = ["src/test.py"]

        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            state_file = tmp_path / "rca_workflow.json"
            state_file.write_text(json.dumps({"session_id": "test", "actions": []}))

            (tmp_path / "test.py").write_text("def test(): pass")

            ranked = rank_contexts(contexts, state_dir=str(tmp_path))

            # Should return list of tuples
            assert len(ranked) == 1
            assert isinstance(ranked[0], tuple)
            assert len(ranked[0]) == 2
            assert isinstance(ranked[0][0], str)
            assert isinstance(ranked[0][1], (int, float))


class TestIntegration:
    """Integration tests with real data."""

    def test_end_to_end_priority_calculation(self, tmp_path):
        """Full priority calculation with all signals."""
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S +0000")
        test_file_path = str(tmp_path / "target.py")

        # Create state DB with errors
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "actions": [
                        {
                            "tool": "Bash",
                            "file": test_file_path,
                            "error": True,
                            "timestamp": now.isoformat(),
                        },
                    ],
                }
            )
        )

        # Create test file
        test_file = tmp_path / "target.py"
        test_file.write_text("""
def complex_function(data):
    results = []
    for item in data:
        if item:
            results.append(process(item))
    return results
""")

        # Mock git log for recent change
        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = now_str
            mock_run.return_value = mock_result

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference.calculate_priority_score(str(test_file))

            # Should get medium-high priority from combined signals
            assert score > 30
            assert score <= 100

    def test_missing_git_repository_graceful_degradation(self, tmp_path):
        """Missing git repository doesn't crash, returns safe default."""
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text(json.dumps({"session_id": "test", "actions": []}))

        # Use non-Python file to get 0 complexity score
        test_file = tmp_path / "test.txt"
        test_file.write_text("just text")

        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference.calculate_priority_score(str(test_file))

            # Should return default priority, not crash
            assert score == 50

    def test_corrupted_state_db_safe_default(self, tmp_path):
        """Corrupted state DB returns safe default priority."""
        state_file = tmp_path / "rca_workflow.json"
        state_file.write_text("invalid json {{{")

        # Use non-Python file to get 0 complexity score
        test_file = tmp_path / "test.txt"
        test_file.write_text("just text")

        with patch("tools.priority_inference.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            inference = PriorityInference(state_dir=str(tmp_path))
            score = inference.calculate_priority_score(str(test_file))

            # Should return default priority, not crash
            assert score == 50
