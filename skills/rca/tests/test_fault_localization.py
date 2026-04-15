"""Fault Localization tests for rca.

These tests verify the Statistical Bug Fault Localization (SBFL) functionality
including suspiciousness scoring formulas and coverage data processing.

Run with: pytest P:/packages/rca/skill/tests/test_fault_localization.py -v
"""

import json
import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca.fault_localization import (
    CoverageData,
    SuspiciousnessScore,
    dstar_score,
    ochiai_score,
    parse_coverage_json,
    parse_pytest_json_report,
    rank_suspicious_locations,
    tarantula_score,
)


class TestCoverageData:
    """Tests for CoverageData dataclass."""

    def test_coverage_data_creation(self):
        """Test that CoverageData can be instantiated with all fields.

        Given: A coverage data point is needed
        When: Creating a CoverageData object
        Then: All fields should be stored correctly
        """
        cov = CoverageData(
            file_path="src/example.py",
            line_number=42,
            function_name="buggy_function",
            executed_in_passing=5,
            executed_in_failing=10,
            total_passing=20,
            total_failing=10,
        )

        assert cov.file_path == "src/example.py"
        assert cov.line_number == 42
        assert cov.function_name == "buggy_function"
        assert cov.executed_in_passing == 5
        assert cov.executed_in_failing == 10
        assert cov.total_passing == 20
        assert cov.total_failing == 10


class TestSuspiciousnessScore:
    """Tests for SuspiciousnessScore dataclass."""

    def test_suspiciousness_score_creation(self):
        """Test that SuspiciousnessScore can be instantiated.

        Given: A suspiciousness score result is needed
        When: Creating a SuspiciousnessScore object
        Then: All fields should be stored correctly
        """
        score = SuspiciousnessScore(
            file_path="src/example.py",
            line_number=42,
            function_name="buggy_function",
            score=0.85,
            formula="ochiai",
        )

        assert score.file_path == "src/example.py"
        assert score.line_number == 42
        assert score.function_name == "buggy_function"
        assert score.score == 0.85
        assert score.formula == "ochiai"


class TestOchiaiScore:
    """Tests for ochiai_score function."""

    def test_ochiai_empty_evidence(self):
        """Test that ochiai_score handles empty evidence gracefully.

        Given: No failing tests exist
        When: Calculating ochiai score with total_failing=0
        Then: Should return 0.0 to avoid division by zero
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=1,
            executed_in_passing=0,
            executed_in_failing=0,
            total_passing=10,
            total_failing=0,  # No failing tests
        )

        score = ochiai_score(cov)
        assert score == 0.0

    def test_ochiai_single_cause(self):
        """Test that ochiai_score identifies highly suspicious lines.

        Given: A line executed in all failing tests but no passing tests
        When: Calculating ochiai score
        Then: Should return a score close to 1.0 (highly suspicious)
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=42,
            executed_in_passing=0,  # Not executed in passing tests
            executed_in_failing=10,  # Executed in all failing tests
            total_passing=20,
            total_failing=10,
        )

        score = ochiai_score(cov)
        # Ochiai: failed(e) / sqrt(total_failed * (failed(e) + passed(e)))
        # = 10 / sqrt(10 * (10 + 0)) = 10 / sqrt(100) = 10 / 10 = 1.0
        assert score == pytest.approx(1.0, rel=1e-6)

    def test_ochiai_multiple_causes(self):
        """Test that ochiai_score ranks multiple suspicious lines.

        Given: Multiple lines with different execution patterns
        When: Calculating ochiai scores for each line
        Then: Lines executed in more failing tests should have higher scores
        """
        # Highly suspicious line
        cov_high = CoverageData(
            file_path="test.py",
            line_number=10,
            executed_in_passing=1,
            executed_in_failing=10,
            total_passing=20,
            total_failing=10,
        )

        # Moderately suspicious line
        cov_med = CoverageData(
            file_path="test.py",
            line_number=20,
            executed_in_passing=10,
            executed_in_failing=5,
            total_passing=20,
            total_failing=10,
        )

        # Not suspicious
        cov_low = CoverageData(
            file_path="test.py",
            line_number=30,
            executed_in_passing=20,
            executed_in_failing=0,
            total_passing=20,
            total_failing=10,
        )

        score_high = ochiai_score(cov_high)
        score_med = ochiai_score(cov_med)
        score_low = ochiai_score(cov_low)

        assert score_high > score_med > score_low

    def test_ochiai_confidence_scoring(self):
        """Test that ochiai_score provides confidence metrics.

        Given: A line with varying execution patterns
        When: Calculating ochiai score
        Then: Score should be between 0.0 and 1.0
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=42,
            executed_in_passing=5,
            executed_in_failing=8,
            total_passing=20,
            total_failing=10,
        )

        score = ochiai_score(cov)
        assert 0.0 <= score <= 1.0


class TestTarantulaScore:
    """Tests for tarantula_score function."""

    def test_tarantula_empty_evidence(self):
        """Test that tarantula_score handles empty evidence gracefully.

        Given: No passing or failing tests exist
        When: Calculating tarantula score with zero totals
        Then: Should return 0.0 to avoid division by zero
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=1,
            executed_in_passing=0,
            executed_in_failing=0,
            total_passing=0,
            total_failing=0,
        )

        score = tarantula_score(cov)
        assert score == 0.0

    def test_tarantula_single_cause(self):
        """Test that tarantula_score identifies highly suspicious lines.

        Given: A line executed in all failing tests but no passing tests
        When: Calculating tarantula score
        Then: Should return a score of 1.0 (highly suspicious)
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=42,
            executed_in_passing=0,
            executed_in_failing=10,
            total_passing=20,
            total_failing=10,
        )

        score = tarantula_score(cov)
        # Tarantula: (failed/total_failed) / ((failed/total_failed) + (passed/total_passed))
        # = (10/10) / ((10/10) + (0/20)) = 1.0 / (1.0 + 0.0) = 1.0
        assert score == pytest.approx(1.0, rel=1e-6)

    def test_tarantula_multiple_causes(self):
        """Test that tarantula_score ranks multiple suspicious lines.

        Given: Multiple lines with different execution patterns
        When: Calculating tarantula scores for each line
        Then: Should produce scores that distinguish between suspiciousness levels
        """
        cov_high = CoverageData(
            file_path="test.py",
            line_number=10,
            executed_in_passing=1,
            executed_in_failing=10,
            total_passing=20,
            total_failing=10,
        )

        cov_med = CoverageData(
            file_path="test.py",
            line_number=20,
            executed_in_passing=10,
            executed_in_failing=5,
            total_passing=20,
            total_failing=10,
        )

        score_high = tarantula_score(cov_high)
        score_med = tarantula_score(cov_med)

        assert score_high > score_med
        assert 0.0 <= score_high <= 1.0
        assert 0.0 <= score_med <= 1.0


class TestDStarScore:
    """Tests for dstar_score function."""

    def test_dstar_empty_evidence(self):
        """Test that dstar_score handles empty evidence gracefully.

        Given: A line with no execution in failing tests
        When: Calculating dstar score
        Then: Should return 0.0 for non-suspicious lines
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=1,
            executed_in_passing=10,
            executed_in_failing=0,
            total_passing=20,
            total_failing=10,
        )

        score = dstar_score(cov)
        assert score == 0.0

    def test_dstar_single_cause(self):
        """Test that dstar_score identifies highly suspicious lines.

        Given: A line executed in all failing tests
        When: Calculating dstar score with default star=2
        Then: Should return a high score reflecting suspiciousness
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=42,
            executed_in_passing=0,
            executed_in_failing=10,
            total_passing=20,
            total_failing=10,
        )

        score = dstar_score(cov)
        # D*: failed(e)^2 / (passed(e) + (total_failed - failed(e)))
        # = 10^2 / (0 + (10 - 10)) = 100 / 0 = infinity
        assert score == float("inf")

    def test_dstar_confidence_scoring(self):
        """Test that dstar_score provides confidence metrics.

        Given: A line with moderate execution in failing tests
        When: Calculating dstar score
        Then: Should return a numeric score reflecting suspiciousness
        """
        cov = CoverageData(
            file_path="test.py",
            line_number=42,
            executed_in_passing=5,
            executed_in_failing=8,
            total_passing=20,
            total_failing=10,
        )

        score = dstar_score(cov, star=2)
        # D*: 8^2 / (5 + (10 - 8)) = 64 / 7 ≈ 9.14
        assert score > 0
        assert isinstance(score, (int, float))


class TestRankSuspiciousLocations:
    """Tests for rank_suspicious_locations function."""

    def test_fault_localization_empty_evidence(self):
        """Test that rank_suspicious_locations handles empty evidence list.

        Given: No coverage data is available
        When: Ranking suspicious locations with empty list
        Then: Should return an empty list
        """
        result = rank_suspicious_locations([])
        assert result == []

    def test_fault_localization_single_cause(self):
        """Test that rank_suspicious_locations identifies single root cause.

        Given: One highly suspicious line in coverage data
        When: Ranking suspicious locations
        Then: Should return the line with highest score first
        """
        coverage_data = [
            CoverageData(
                file_path="test.py",
                line_number=42,
                function_name="buggy_func",
                executed_in_passing=0,
                executed_in_failing=10,
                total_passing=20,
                total_failing=10,
            ),
        ]

        result = rank_suspicious_locations(coverage_data, formula="ochiai")

        assert len(result) == 1
        assert result[0].file_path == "test.py"
        assert result[0].line_number == 42
        assert result[0].score == pytest.approx(1.0, rel=1e-6)
        assert result[0].formula == "ochiai"

    def test_fault_localization_multiple_causes(self):
        """Test that rank_suspicious_locations ranks multiple potential causes.

        Given: Multiple lines with different suspiciousness levels
        When: Ranking suspicious locations
        Then: Should return results sorted by score in descending order
        """
        coverage_data = [
            CoverageData(
                file_path="test.py",
                line_number=10,
                function_name="func_a",
                executed_in_passing=10,
                executed_in_failing=5,
                total_passing=20,
                total_failing=10,
            ),
            CoverageData(
                file_path="test.py",
                line_number=20,
                function_name="func_b",
                executed_in_passing=1,
                executed_in_failing=10,
                total_passing=20,
                total_failing=10,
            ),
            CoverageData(
                file_path="test.py",
                line_number=30,
                function_name="func_c",
                executed_in_passing=20,
                executed_in_failing=0,
                total_passing=20,
                total_failing=10,
            ),
        ]

        result = rank_suspicious_locations(coverage_data, formula="ochiai")

        assert len(result) == 3
        # Should be sorted by score descending
        assert result[0].score >= result[1].score >= result[2].score
        # Line 20 should be most suspicious (high failing, low passing)
        assert result[0].line_number == 20
        # Line 30 should be least suspicious (no failing execution)
        assert result[2].line_number == 30

    def test_fault_localization_confidence_scoring(self):
        """Test that rank_suspicious_locations scores confidence of localization.

        Given: Coverage data with multiple formulas available
        When: Ranking with different formulas
        Then: Should produce scores using the specified formula
        """
        coverage_data = [
            CoverageData(
                file_path="test.py",
                line_number=42,
                executed_in_passing=5,
                executed_in_failing=8,
                total_passing=20,
                total_failing=10,
            ),
        ]

        result_ochiai = rank_suspicious_locations(coverage_data, formula="ochiai")
        result_tarantula = rank_suspicious_locations(coverage_data, formula="tarantula")
        result_dstar = rank_suspicious_locations(coverage_data, formula="dstar")

        assert len(result_ochiai) == 1
        assert len(result_tarantula) == 1
        assert len(result_dstar) == 1

        assert result_ochiai[0].formula == "ochiai"
        assert result_tarantula[0].formula == "tarantula"
        assert result_dstar[0].formula == "dstar"

        # All scores should be valid numbers
        assert isinstance(result_ochiai[0].score, (int, float))
        assert isinstance(result_tarantula[0].score, (int, float))
        assert isinstance(result_dstar[0].score, (int, float))

    def test_fault_localization_unknown_formula(self):
        """Test that rank_suspicious_locations handles unknown formula.

        Given: An unknown formula name is provided
        When: Ranking suspicious locations
        Then: Should default to ochiai formula
        """
        coverage_data = [
            CoverageData(
                file_path="test.py",
                line_number=42,
                executed_in_passing=5,
                executed_in_failing=8,
                total_passing=20,
                total_failing=10,
            ),
        ]

        result = rank_suspicious_locations(coverage_data, formula="unknown_formula")

        assert len(result) == 1
        # Should default to ochiai
        assert result[0].formula == "ochiai"


class TestParseCoverageJson:
    """Tests for parse_coverage_json function."""

    def test_parse_coverage_missing_file(self, tmp_path):
        """Test that parse_coverage_json handles missing coverage file.

        Given: Coverage file does not exist
        When: Parsing coverage JSON
        Then: Should return empty list
        """
        result = parse_coverage_json(tmp_path / "nonexistent.json", [])
        assert result == []

    def test_parse_coverage_no_failing_tests(self, tmp_path):
        """Test that parse_coverage_json handles no failing tests.

        Given: All tests pass
        When: Parsing coverage JSON with only passing tests
        Then: Should return empty list (no faults to localize)
        """
        # Create minimal coverage file
        cov_data = {
            "files": {
                "test.py": {
                    "executed_lines": [1, 2, 3],
                }
            }
        }

        cov_file = tmp_path / "coverage.json"
        with open(cov_file, "w") as f:
            json.dump(cov_data, f)

        test_results = [
            {"name": "test_a", "passed": True, "covered_lines": {"test.py": [1, 2]}},
            {"name": "test_b", "passed": True, "covered_lines": {"test.py": [2, 3]}},
        ]

        result = parse_coverage_json(cov_file, test_results)
        assert result == []

    def test_parse_coverage_valid_data(self, tmp_path):
        """Test that parse_coverage_json parses valid coverage data.

        Given: Valid coverage JSON and test results
        When: Parsing coverage data
        Then: Should return list of CoverageData objects
        """
        cov_data = {
            "files": {
                "test.py": {
                    "executed_lines": [10, 20, 30],
                }
            }
        }

        cov_file = tmp_path / "coverage.json"
        with open(cov_file, "w") as f:
            json.dump(cov_data, f)

        test_results = [
            {"name": "test_pass", "passed": True, "covered_lines": {"test.py": [10, 20]}},
            {"name": "test_fail", "passed": False, "covered_lines": {"test.py": [20, 30]}},
        ]

        result = parse_coverage_json(cov_file, test_results)

        assert len(result) > 0
        assert all(isinstance(cov, CoverageData) for cov in result)

        # Check that failing test coverage is tracked
        line_20_data = [c for c in result if c.line_number == 20]
        assert len(line_20_data) == 1
        assert line_20_data[0].executed_in_failing == 1
        assert line_20_data[0].executed_in_passing == 1


class TestParsePytestJsonReport:
    """Tests for parse_pytest_json_report function."""

    def test_parse_pytest_report_missing_file(self, tmp_path):
        """Test that parse_pytest_json_report handles missing report file.

        Given: Report file does not exist
        When: Parsing pytest JSON report
        Then: Should return empty results and coverage
        """
        test_results, coverage = parse_pytest_json_report(tmp_path / "nonexistent.json")
        assert test_results == []
        assert coverage == {}

    def test_parse_pytest_report_valid_data(self, tmp_path):
        """Test that parse_pytest_json_report parses valid report data.

        Given: Valid pytest JSON report file
        When: Parsing pytest report
        Then: Should extract test results with pass/fail status
        """
        report_data = {
            "tests": [
                {"nodeid": "test_module.py::test_func_a", "outcome": "passed"},
                {"nodeid": "test_module.py::test_func_b", "outcome": "failed"},
                {"nodeid": "test_module.py::test_func_c", "outcome": "passed"},
            ]
        }

        report_file = tmp_path / "report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        test_results, coverage = parse_pytest_json_report(report_file)

        assert len(test_results) == 3
        assert test_results[0]["name"] == "test_module.py::test_func_a"
        assert test_results[0]["passed"] is True
        assert test_results[1]["name"] == "test_module.py::test_func_b"
        assert test_results[1]["passed"] is False
        assert test_results[2]["name"] == "test_module.py::test_func_c"
        assert test_results[2]["passed"] is True
