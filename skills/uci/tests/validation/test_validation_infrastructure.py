"""
Tests for validation infrastructure.

TDD RED phase: Tests for validation infrastructure that will analyze
historical /uci runs to detect missed bug patterns.
"""

import json
import sys
from pathlib import Path

import pytest

# Add validation directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data_collector import (
    BugCategory,
    UCIRunCollector,
    validate_finding_schema,
)


class TestDataCollector:
    """Test data collector for /uci runs."""

    def test_collector_initialization(self):
        """Test that UCIRunCollector initializes correctly."""
        collector = UCIRunCollector(log_dir=".claude/state/uci")
        assert collector.log_dir == Path(".claude/state/uci")
        assert collector.runs == []
        assert isinstance(collector.runs, list)

    def test_collector_load_from_logs(self):
        """Test loading /uci run data from log files."""
        # Create temporary log file with sample /uci output
        log_dir = Path(".temp/uci/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        sample_log = {
            "timestamp": "2026-03-16T10:00:00",
            "mode": "standard",
            "agents": [
                "adversarial-logic",
                "adversarial-testing",
                "adversarial-security",
                "adversarial-performance",
            ],
            "findings": [
                {
                    "id": "LOGIC-001",
                    "severity": "high",
                    "location": "src/auth.py:45",
                    "problem": "Null pointer dereference",
                }
            ],
        }

        log_file = log_dir / "uci_run_20260316_100000.json"
        log_file.write_text(json.dumps(sample_log))

        collector = UCIRunCollector(log_dir=str(log_dir))
        runs = collector.load_from_logs()

        assert len(runs) == 1
        assert runs[0]["mode"] == "standard"
        assert len(runs[0]["findings"]) == 1

        # Cleanup
        log_file.unlink()
        log_dir.rmdir()
        log_dir.parent.rmdir()

    def test_collector_extract_findings_by_category(self):
        """Test extracting findings categorized by bug type."""
        collector = UCIRunCollector()

        sample_run = {
            "timestamp": "2026-03-16T10:00:00",
            "mode": "standard",
            "findings": [
                {
                    "id": "LOGIC-001",
                    "severity": "high",
                    "location": "src/auth.py:45",
                    "problem": "State transition not validated",
                    "category": "state-transition",
                },
                {
                    "id": "PERF-001",
                    "severity": "medium",
                    "location": "src/api.py:123",
                    "problem": "N+1 query pattern",
                    "category": "performance",
                },
            ],
        }

        categories = collector.extract_findings_by_category(sample_run)

        assert "state-transition" in categories
        assert "performance" in categories
        assert len(categories["state-transition"]) == 1
        assert categories["state-transition"][0]["id"] == "LOGIC-001"


class TestBugCategoryClassification:
    """Test bug category classification for missed patterns."""

    def test_classify_state_transition_bugs(self):
        """Test classification of state-transition bugs."""
        finding = {
            "id": "LOGIC-001",
            "problem": "State transition not validated in mark_snapshot_status()",
            "location": "src/handoff.py:67",
        }

        category = BugCategory.classify(finding)
        assert category == BugCategory.STATE_TRANSITION

    def test_classify_toctou_bugs(self):
        """Test classification of TOCTOU bugs."""
        finding = {
            "id": "SEC-001",
            "problem": "Evidence freshness check has TOCTOU race condition",
            "location": "src/ledger.py:234",
        }

        category = BugCategory.classify(finding)
        assert category == BugCategory.TOCTOU

    def test_classify_id_collision_bugs(self):
        """Test classification of ID collision bugs."""
        finding = {
            "id": "LOGIC-002",
            "problem": "Decision ID collision possibility with concurrent requests",
            "location": "src/decider.py:89",
        }

        category = BugCategory.classify(finding)
        assert category == BugCategory.ID_COLLISION

    def test_classify_path_validation_bugs(self):
        """Test classification of path validation bugs."""
        finding = {
            "id": "IO-001",
            "problem": "Transcript path existence validation gap",
            "location": "src/storage.py:45",
        }

        category = BugCategory.classify(finding)
        assert category == BugCategory.PATH_VALIDATION


class TestFindingSchemaValidation:
    """Test validation of finding data structure."""

    def test_valid_finding_schema(self):
        """Test that valid finding passes validation."""
        valid_finding = {
            "id": "LOGIC-001",
            "severity": "high",
            "location": "src/auth.py:45",
            "problem": "Null pointer dereference",
            "adversarial_scenario": "Input is None causes crash",
            "impact": "Runtime crash",
            "recommendation": "Add null check",
        }

        assert validate_finding_schema(valid_finding) is True

    def test_missing_required_fields(self):
        """Test that missing required fields fail validation."""
        invalid_finding = {
            "id": "LOGIC-001"
            # Missing: severity, location, problem
        }

        assert validate_finding_schema(invalid_finding) is False

    def test_invalid_severity_value(self):
        """Test that invalid severity values fail validation."""
        invalid_finding = {
            "id": "LOGIC-001",
            "severity": "critical",  # Not a valid severity
            "location": "src/auth.py:45",
            "problem": "Some issue",
        }

        assert validate_finding_schema(invalid_finding) is False


class TestMissedBugDetection:
    """Test detection of missed bugs in /uci runs."""

    def test_detect_missed_state_bugs(self):
        """Test detecting state-transition bugs that /uci missed."""
        # Simulate a /uci run that found performance bugs but missed state bugs
        uci_run = {
            "timestamp": "2026-03-16T10:00:00",
            "mode": "standard",
            "findings": [
                {
                    "id": "PERF-001",
                    "severity": "medium",
                    "problem": "N+1 query",
                    "category": "performance",
                }
            ],
        }

        # Simulate code analysis that reveals state bugs were present but not found
        code_analysis = {
            "state_bugs_present": [
                {"location": "src/state.py:100", "problem": "Missing state transition check"}
            ]
        }

        collector = UCIRunCollector()
        missed = collector.detect_missed_bugs(uci_run, code_analysis)

        assert len(missed) == 1
        assert missed[0]["category"] == "state-transition"
        assert missed[0]["status"] == "missed"

    def test_no_missed_bugs_when_all_found(self):
        """Test that no missed bugs are reported when /uci found everything."""
        uci_run = {
            "timestamp": "2026-03-16T10:00:00",
            "mode": "comprehensive",
            "findings": [
                {
                    "id": "LOGIC-001",
                    "severity": "high",
                    "problem": "State bug",
                    "category": "state-transition",
                },
                {
                    "id": "PERF-001",
                    "severity": "medium",
                    "problem": "N+1",
                    "category": "performance",
                },
            ],
        }

        code_analysis = {
            "state_bugs_present": []  # All state bugs were found
        }

        collector = UCIRunCollector()
        missed = collector.detect_missed_bugs(uci_run, code_analysis)

        assert len(missed) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
