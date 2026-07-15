"""Tests for hypothesis quality evaluation harness."""
from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path
import sys, os

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import evaluate_hypothesis_quality as ev


class TestDiscoverRuns:
    def test_empty_root(self, tmp_path):
        runs = ev.discover_runs(tmp_path)
        assert runs == []

    def test_standalone_qa_verdicts(self, tmp_path):
        go_dir = tmp_path / "test-term" / "go"
        go_dir.mkdir(parents=True)
        qa = go_dir / "qa-verdict-test-001.json"
        qa.write_text(json.dumps({"run_id": "test-001", "qa_status": "redo"}), encoding="utf-8")
        runs = ev.discover_runs(tmp_path)
        assert len(runs) >= 1
        assert any(r.get("qa_verdict") == "redo" for r in runs)


class TestBuildOutcomeIndexEntries:
    def test_empty_runs(self):
        assert ev.build_outcome_index_entries([]) == []

    def test_creates_entries(self):
        runs = [{"run_id": "r1", "session_id": "s1", "qa_verdict": "redo",
                 "has_discovery_evidence": False, "finding_count": 0}]
        entries = ev.build_outcome_index_entries(runs)
        assert len(entries) == 1
        assert entries[0]["run_id"] == "r1"
        assert entries[0]["outcome_reference"]["qa_verdict"] == "redo"


class TestClassifyHypothesis:
    def _make_hyp(self, htype: str, conf: float) -> dict:
        return {
            "observation": {"type": htype, "description": "test"},
            "hypotheses": [{"statement": "test", "confidence": conf,
                            "supporting_evidence": [], "counter_evidence": []}],
            "investigation_value": {"impact": 0.6, "evidence_quality": 0.4},
            "evidence": {"runs": [{"run_id": "r1"}]},
        }

    def test_valuable_discovery_gap(self):
        h = self._make_hyp("possible_discovery_gap", 0.7)
        result = ev.classify_hypothesis(h)
        assert result["_usefulness"] == "valuable"
        assert result["_actionability"] == "actionable"

    def test_noise_unknown(self):
        h = self._make_hyp("unknown", 0.0)
        result = ev.classify_hypothesis(h)
        assert result["_usefulness"] == "noise"
        assert result["_actionability"] == "not_actionable"

    def test_evaluated_at_set(self):
        h = self._make_hyp("positive_discovery_success", 0.7)
        result = ev.classify_hypothesis(h)
        assert result["_evaluated_at"].endswith("Z")


class TestProduceReport:
    def test_minimal_input(self):
        report = ev.produce_report([], [], [], [], [], {"total_hypotheses": 0}, 0.0)
        assert report["schema_version"] == "hypothesis-evaluation-report.v1"
        assert report["dataset"]["runs_analyzed"] == 0

    def test_deterministic(self):
        runs = [{"run_id": "r1", "qa_verdict": "redo", "session_id": "s1",
                 "has_discovery_evidence": False, "finding_count": 0,
                 "source": "test", "repository": "", "revision": "",
                 "lifecycle_status": "completed", "completion_verdict": "",
                 "falsification_verdict": "", "has_run_record": False,
                 "has_completion_review": False, "has_falsification": False}]
        entries = ev.build_outcome_index_entries(runs)
        import hypothesis_generator as hg
        hyps = hg.generate(entries)
        evaluated = [ev.classify_hypothesis(h) for h in hyps]
        import hypothesis_governance as gov
        deduped = gov.deduplicate(evaluated)
        agg = hg.aggregate(evaluated)
        sm = hg.get_summary(evaluated)
        r1 = ev.produce_report(runs, entries, evaluated, deduped, agg, sm, 0.0)
        r2 = ev.produce_report(runs, entries, evaluated, deduped, agg, sm, 0.0)
        assert r1 == r2


class TestCLI:
    def test_empty_root_exit_zero(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run(
                [sys.executable, "-m", "evaluate_hypothesis_quality",
                 "--artifacts-root", td, "--output-dir", td, "--quiet"],
                capture_output=True, text=True, cwd=str(SCRIPTS),
            )
            # Empty root → exit 0 with valid report
            assert result.returncode == 0

    def test_provenance_preserved(self, tmp_path):
        runs = [{"run_id": "r1", "qa_verdict": "redo", "session_id": "s1",
                 "has_discovery_evidence": False, "finding_count": 0,
                 "source": "test", "repository": "", "revision": "",
                 "lifecycle_status": "completed", "completion_verdict": "",
                 "falsification_verdict": "", "has_run_record": False,
                 "has_completion_review": False, "has_falsification": False}]
        entries = ev.build_outcome_index_entries(runs)
        import hypothesis_generator as hg
        hyps = hg.generate(entries)
        for h in hyps:
            assert h.get("provenance", {}).get("writer") is not None

