"""Tests for PI outcome metrics and advisory classification."""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if "classify_complexity" not in sys.modules:
    import types as _types
    _cc = _types.ModuleType("classify_complexity")
    _cc.classify_model_affinity = lambda *a, **kw: "T2"
    sys.modules["classify_complexity"] = _cc

_spec = importlib.util.spec_from_file_location("pf", SCRIPTS / "preflight_propose.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)


class TestClassifyPiAdvisory:
    """Tests for the advisory classification logic."""

    def test_pi_clean_run_strong_candidate(self):
        """PI dispatch, clean review, no errors → pi_strong_candidate."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "low",
            "task_class": "bugfix",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        assert result == "pi_strong_candidate"

    def test_pi_warnings_ok_with_review(self):
        """PI dispatch, warnings present → pi_ok_with_review."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "medium",
            "task_class": "feature",
            "review_verdict": "warnings_present",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        assert result == "pi_ok_with_review"

    def test_pi_writer_error_evidence_collector(self):
        """PI dispatch with writer error → pi_evidence_collector."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "low",
            "task_class": "bugfix",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": True,
        })
        assert result == "pi_evidence_collector"

    def test_pi_rescue_needed_avoid(self):
        """PI dispatch with rescue needed → pi_evidence_collector."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "low",
            "task_class": "bugfix",
            "review_verdict": "clean",
            "rescue_escalation_needed": True,
            "writer_error": False,
        })
        assert result == "pi_evidence_collector"

    def test_high_risk_avoids_pi(self):
        """High-risk task → avoid_pi."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "high",
            "task_class": "bugfix",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        assert result == "avoid_pi"

    def test_hook_task_avoids_pi(self):
        """Hook task class → avoid_pi, regardless of dispatch."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "low",
            "task_class": "hook",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        assert result == "avoid_pi"

    def test_unrelated_success_does_not_promote_hook_tasks(self):
        """A clean PI run in bugfix class should NOT promote hook tasks."""
        bugfix_result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "low",
            "task_class": "bugfix",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        hook_result = pf.classify_pi_advisory({
            "dispatch_route": "pi",
            "risk_class": "low",
            "task_class": "hook",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        assert bugfix_result == "pi_strong_candidate"
        assert hook_result == "avoid_pi"

    def test_clude_dispatch_avoids_pi(self):
        """Claude dispatch → avoid_pi (PI metrics don't promote Claude runs)."""
        result = pf.classify_pi_advisory({
            "dispatch_route": "claude",
            "risk_class": "low",
            "task_class": "bugfix",
            "review_verdict": "clean",
            "rescue_escalation_needed": False,
            "writer_error": False,
        })
        assert result == "avoid_pi"


class TestRecordPiOutcome:
    """Tests for run_local record_pi_outcome."""

    def test_metrics_written_for_run(self, tmp_path):
        """record_pi_outcome writes a JSONL file scoped by run_id."""
        rid = "metrics-001"
        record = pf.record_pi_outcome(
            tmp_path, rid,
            dispatch_route="pi",
            task_class="bugfix",
            risk_class="low",
            review_verdict="clean",
        )
        assert record["event"] == "pi_outcome"
        assert record["run_id"] == rid
        assert record["pi_advisory"] == "pi_strong_candidate"
        tel_file = tmp_path / f"pi-outcome_{rid}.jsonl"
        assert tel_file.exists()

    def test_two_run_ids_do_not_contaminate(self, tmp_path):
        """Different run_ids produce separate, non-overlapping files."""
        pf.record_pi_outcome(tmp_path, "run-a", dispatch_route="pi",
                             risk_class="low", task_class="bugfix", review_verdict="clean")
        pf.record_pi_outcome(tmp_path, "run-b", dispatch_route="pi",
                             risk_class="high", task_class="hook", review_verdict="clean")
        a_file = tmp_path / "pi-outcome_run-a.jsonl"
        b_file = tmp_path / "pi-outcome_run-b.jsonl"
        assert a_file.exists() and b_file.exists()
        a_rec = [json.loads(l) for l in a_file.read_text().strip().splitlines()][-1]
        b_rec = [json.loads(l) for l in b_file.read_text().strip().splitlines()][-1]
        assert a_rec["pi_advisory"] == "pi_strong_candidate"
        assert b_rec["pi_advisory"] == "avoid_pi"

    def test_missing_metrics_do_not_promote_pi(self, tmp_path):
        """Empty dispatch_route + no review → avoid_pi."""
        record = pf.record_pi_outcome(tmp_path, "no-metrics-001")
        assert record["pi_advisory"] == "avoid_pi"

    def test_writer_error_reduces_confidence(self, tmp_path):
        """Writer error during PI → pi_evidence_collector."""
        record = pf.record_pi_outcome(
            tmp_path, "err-001",
            dispatch_route="pi", task_class="bugfix", risk_class="low",
            review_verdict="clean",
            writer_error=True,
        )
        assert record["pi_advisory"] == "pi_evidence_collector"

    def test_high_risk_contracts_recommendation(self, tmp_path):
        """High-risk task → avoid_pi."""
        record = pf.record_pi_outcome(
            tmp_path, "risk-001",
            dispatch_route="pi", task_class="bugfix", risk_class="high",
            review_verdict="clean",
        )
        assert record["pi_advisory"] == "avoid_pi"

    def test_unrelated_task_class_success_does_not_promote(self, tmp_path):
        """Success in bugfix does not promote hook/gate/cache/state tasks."""
        pf.record_pi_outcome(tmp_path, "ok-001",
                             dispatch_route="pi", task_class="bugfix",
                             risk_class="low", review_verdict="clean")
        hook_record = pf.record_pi_outcome(
            tmp_path, "hook-001",
            dispatch_route="pi", task_class="hook",
            risk_class="low", review_verdict="clean",
        )
        assert hook_record["pi_advisory"] == "avoid_pi"
