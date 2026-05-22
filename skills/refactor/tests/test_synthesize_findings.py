"""Tests for synthesize_findings module."""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.synthesize_findings import (
    calculate_health_score,
    load_agent_findings,
    deduplicate_findings,
    group_by_severity,
    synthesize_report,
    format_synthesis_for_display,
)


class TestCalculateHealthScore:
    """Tests for Health Score calculation."""

    def test_perfect_score_no_findings(self):
        """No findings yields perfect score."""
        score = calculate_health_score([])
        assert score == 100

    def test_critical_findings_reduce_score_most(self):
        """Each CRITICAL finding reduces score by 20."""
        score = calculate_health_score([
            {'severity': 'CRITICAL'},
            {'severity': 'CRITICAL'},
        ])
        assert score == 60  # 100 - (2 * 20)

    def test_high_findings_reduce_score_moderately(self):
        """Each HIGH finding reduces score by 10."""
        score = calculate_health_score([
            {'severity': 'HIGH'},
            {'severity': 'HIGH'},
            {'severity': 'HIGH'},
        ])
        assert score == 70  # 100 - (3 * 10)

    def test_medium_findings_reduce_score_little(self):
        """Each MEDIUM finding reduces score by 5."""
        score = calculate_health_score([
            {'severity': 'MEDIUM'},
            {'severity': 'MEDIUM'},
        ])
        assert score == 90  # 100 - (2 * 5)

    def test_low_findings_reduce_score_minimally(self):
        """Each LOW finding reduces score by 2."""
        score = calculate_health_score([
            {'severity': 'LOW'},
        ])
        assert score == 98  # 100 - (1 * 2)

    def test_mixed_severity_calculations(self):
        """Mixed severities sum their weights correctly."""
        score = calculate_health_score([
            {'severity': 'CRITICAL'},  # -20
            {'severity': 'HIGH'},      # -10
            {'severity': 'MEDIUM'},    # -5
            {'severity': 'LOW'},       # -2
        ])
        assert score == 63  # 100 - 37

    def test_score_capped_at_zero(self):
        """Score cannot go below zero."""
        score = calculate_health_score([
            {'severity': 'CRITICAL'},
            {'severity': 'CRITICAL'},
            {'severity': 'CRITICAL'},
            {'severity': 'CRITICAL'},
            {'severity': 'CRITICAL'},
            {'severity': 'CRITICAL'},
        ])
        assert score == 0  # Would be -20, capped at 0

    def test_missing_severity_treated_as_low(self):
        """Findings without severity are ignored (not counted as LOW)."""
        score = calculate_health_score([
            {'severity': 'CRITICAL'},
            {},  # Missing severity - not counted
            {'severity': 'HIGH'},
        ])
        assert score == 70  # 100 - (20 + 10)


class TestLoadAgentFindings:
    """Tests for loading agent findings."""

    def test_loads_single_findings_file(self, tmp_path):
        """Load findings from a single agent file."""
        findings_file = tmp_path / "findings-agent1.json"
        findings = [
            {'severity': 'HIGH', 'file': 'test.py', 'line': 10},
            {'severity': 'LOW', 'file': 'test.py', 'line': 20},
        ]
        findings_file.write_text(json.dumps(findings))

        loaded = load_agent_findings(tmp_path)
        assert loaded == findings

    def test_loads_multiple_findings_files(self, tmp_path):
        """Combine findings from multiple agent files."""
        agent1_file = tmp_path / "findings-agent1.json"
        agent2_file = tmp_path / "findings-agent2.json"

        agent1_file.write_text(json.dumps([
            {'severity': 'HIGH', 'file': 'test.py', 'line': 10},
        ]))
        agent2_file.write_text(json.dumps([
            {'severity': 'LOW', 'file': 'test.py', 'line': 20},
        ]))

        loaded = load_agent_findings(tmp_path)
        assert len(loaded) == 2
        assert loaded[0]['severity'] == 'HIGH'
        assert loaded[1]['severity'] == 'LOW'

    def test_handles_invalid_json_gracefully(self, tmp_path):
        """Invalid JSON files are skipped with warning."""
        valid_file = tmp_path / "findings-valid.json"
        invalid_file = tmp_path / "findings-invalid.json"

        valid_file.write_text(json.dumps([{'severity': 'HIGH'}]))
        invalid_file.write_text("{invalid json")

        loaded = load_agent_findings(tmp_path)
        assert len(loaded) == 1
        assert loaded[0]['severity'] == 'HIGH'

    def test_handles_non_list_files_gracefully(self, tmp_path):
        """Files containing non-list JSON are handled gracefully."""
        findings_file = tmp_path / "findings-agent.json"
        findings_file.write_text(json.dumps({'key': 'value'}))  # Not a list

        loaded = load_agent_findings(tmp_path)
        assert loaded == []  # Non-list files contribute nothing


class TestDeduplicateFindings:
    """Tests for findings deduplication."""

    def test_removes_exact_duplicates(self):
        """Remove findings with same file, line, and description."""
        findings = [
            {'file': 'test.py', 'line': 10, 'description': 'Bug here', 'severity': 'HIGH'},
            {'file': 'test.py', 'line': 10, 'description': 'Bug here', 'severity': 'HIGH'},
            {'file': 'other.py', 'line': 5, 'description': 'Different', 'severity': 'LOW'},
        ]

        deduplicated = deduplicate_findings(findings)
        assert len(deduplicated) == 2
        assert deduplicated[0]['file'] == 'test.py'
        assert deduplicated[1]['file'] == 'other.py'

    def test_keeps_different_lines(self):
        """Same file and description but different lines are kept."""
        findings = [
            {'file': 'test.py', 'line': 10, 'description': 'Bug here'},
            {'file': 'test.py', 'line': 20, 'description': 'Bug here'},
        ]

        deduplicated = deduplicate_findings(findings)
        assert len(deduplicated) == 2

    def test_keeps_different_descriptions(self):
        """Same file and line but different descriptions are kept."""
        findings = [
            {'file': 'test.py', 'line': 10, 'description': 'Bug A'},
            {'file': 'test.py', 'line': 10, 'description': 'Bug B'},
        ]

        deduplicated = deduplicate_findings(findings)
        assert len(deduplicated) == 2


class TestGroupBySeverity:
    """Tests for severity grouping."""

    def test_groups_by_known_severities(self):
        """Group findings by CRITICAL, HIGH, MEDIUM, LOW."""
        findings = [
            {'severity': 'CRITICAL', 'description': 'C1'},
            {'severity': 'HIGH', 'description': 'H1'},
            {'severity': 'MEDIUM', 'description': 'M1'},
            {'severity': 'LOW', 'description': 'L1'},
        ]

        grouped = group_by_severity(findings)
        assert len(grouped['CRITICAL']) == 1
        assert len(grouped['HIGH']) == 1
        assert len(grouped['MEDIUM']) == 1
        assert len(grouped['LOW']) == 1

    def test_ignores_unknown_severities(self):
        """Findings with unknown severity are not grouped."""
        findings = [
            {'severity': 'CRITICAL', 'description': 'C1'},
            {'severity': 'UNKNOWN', 'description': 'U1'},
        ]

        grouped = group_by_severity(findings)
        assert len(grouped['CRITICAL']) == 1
        assert len(grouped['HIGH']) == 0
        assert 'UNKNOWN' not in grouped  # Unknown not in groups


class TestSynthesizeReport:
    """Tests for synthesis report generation."""

    def test_generates_complete_report(self):
        """Generate synthesis report with all required fields."""
        findings = [
            {'severity': 'CRITICAL', 'description': 'C1'},
            {'severity': 'HIGH', 'description': 'H1'},
        ]

        report = synthesize_report(findings, "test.py", "session123")

        assert report['target'] == "test.py"
        assert report['session_id'] == "session123"
        assert report['health_score'] == 70  # 100 - (20 + 10)
        assert report['severity_counts']['CRITICAL'] == 1
        assert report['severity_counts']['HIGH'] == 1
        assert report['total_findings'] == 2

    def test_includes_grouped_findings(self):
        """Report includes findings grouped by severity."""
        findings = [
            {'severity': 'CRITICAL', 'description': 'C1'},
            {'severity': 'LOW', 'description': 'L1'},
        ]

        report = synthesize_report(findings, "test.py", "session123")

        assert 'findings_by_severity' in report
        assert len(report['findings_by_severity']['CRITICAL']) == 1
        assert len(report['findings_by_severity']['LOW']) == 1


class TestFormatSynthesisForDisplay:
    """Tests for human-readable display formatting."""

    def test_includes_health_score(self):
        """Formatted output includes health score."""
        synthesis = {
            'target': 'test.py',
            'session_id': 'session123',
            'health_score': 75,
            'severity_counts': {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 0},
            'total_findings': 3,
        }

        output = format_synthesis_for_display(synthesis)

        assert 'Health Score: 75%' in output
        assert 'Warning' in output  # 50-79 range

    def test_includes_severity_table(self):
        """Formatted output includes severity counts table."""
        synthesis = {
            'target': 'test.py',
            'session_id': 'session123',
            'health_score': 60,
            'severity_counts': {'CRITICAL': 1, 'HIGH': 0, 'MEDIUM': 2, 'LOW': 1},
            'total_findings': 4,
        }

        output = format_synthesis_for_display(synthesis)

        assert '| CRITICAL | 1 |' in output
        assert '| HIGH | 0 |' in output
        assert '| MEDIUM | 2 |' in output
        assert '| LOW | 1 |' in output
