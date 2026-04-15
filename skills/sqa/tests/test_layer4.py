"""Tests for Layer 4 REQUIREMENTS analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer4_requirements


class TestLayer4Run:
    """Tests for layer4_requirements.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer4_requirements.run(tmp_target)
        assert isinstance(result, list)

    def test_missing_changelog_reported(self, tmp_target):
        """When CHANGELOG.md is absent, L4 reports it."""
        findings = layer4_requirements.run(tmp_target)
        ids = [f.finding_id for f in findings]
        assert "L4-MISSING-CHANGELOG" in ids


class TestCheckArtifactStatus:
    """Tests for _check_artifact_status."""

    def test_no_changelog_returns_missing_finding(self, tmp_path):
        findings = layer4_requirements._check_artifact_status(tmp_path)
        assert len(findings) == 1
        assert findings[0].finding_id == "L4-MISSING-CHANGELOG"


class TestCheckContradictions:
    """Tests for _check_contradictions (CHANGE-004 pre-mortem contradiction detection)."""

    def test_no_spec_files_returns_empty(self, tmp_path):
        """When no spec files exist, no contradiction findings."""
        findings = layer4_requirements._check_contradictions(tmp_path)
        assert findings == []

    def test_prd_with_will_wont_contradiction(self, tmp_path):
        """PRD with 'will X' and 'won't X' is flagged as contradiction."""
        (tmp_path / "PRD.md").write_text(
            "The system will process all requests.\n"
            "The system won't process batch requests."
        )
        findings = layer4_requirements._check_contradictions(tmp_path)
        assert len(findings) == 1
        assert findings[0].finding_id == "L4-CONTRADICTION-PRDMD"
        assert findings[0].severity.value == "MEDIUM"

    def test_ard_with_can_cannot_contradiction(self, tmp_path):
        """ARD with 'can X' and 'cannot X' is flagged as contradiction."""
        (tmp_path / "ARD.md").write_text(
            "The agent can access the filesystem.\n"
            "The agent cannot access network resources."
        )
        findings = layer4_requirements._check_contradictions(tmp_path)
        assert len(findings) == 1
        assert findings[0].finding_id == "L4-CONTRADICTION-ARDMD"

    def test_changelog_no_contradiction(self, tmp_path):
        """CHANGELOG without contradictions returns empty."""
        (tmp_path / "CHANGELOG.md").write_text(
            "## 1.0.0\n- Initial release\n- Supports authentication"
        )
        findings = layer4_requirements._check_contradictions(tmp_path)
        assert findings == []

    def test_multiple_files_one_finding_per_file(self, tmp_path):
        """Only one finding per file even with multiple contradictions."""
        (tmp_path / "README.md").write_text(
            "Enabled by default.\nDisabled for security."
        )
        findings = layer4_requirements._check_contradictions(tmp_path)
        assert len(findings) == 1
        assert findings[0].finding_id == "L4-CONTRADICTION-READMEMD"
