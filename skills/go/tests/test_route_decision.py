"""Tests for the routeDecision metadata in active-task JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from orchestrate import inject_route_decision, PiModelInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_active_task(state_dir: Path, run_id: str = "test-run") -> Path:
    task_file = state_dir / f"active-task_{run_id}.json"
    task_file.write_text(json.dumps({
        "task": {
            "title": "test task",
            "objective": "test",
        }
    }), encoding="utf-8")
    return task_file


def _read_route(state_dir: Path, run_id: str = "test-run") -> dict:
    task_file = state_dir / f"active-task_{run_id}.json"
    data = json.loads(task_file.read_text(encoding="utf-8"))
    return data["task"]["routeDecision"]


# ---------------------------------------------------------------------------
# PI dispatch
# ---------------------------------------------------------------------------

class TestRouteDecisionPI:
    def test_pi_dispatch_records_flat_single_harness(self, tmp_path):
        _make_active_task(tmp_path)
        pi_info = PiModelInfo(
            classifier_model="M3",
            tier="T2",
            pi_model="minimax/MiniMax-M3",
        )
        inject_route_decision(tmp_path, "test-run", "pi", pi_info)
        route = _read_route(tmp_path)

        assert route["dispatchMode"] == "flat-single-harness"
        assert route["singleDispatchHarness"] == "pi"
        assert route["singleDispatchModel"] == "minimax/MiniMax-M3"
        assert route["chosenDispatch"] == "pi"
        assert route["chosenModel"] == "minimax/MiniMax-M3"

    def test_pi_dispatch_model_source_is_classifier(self, tmp_path):
        _make_active_task(tmp_path)
        pi_info = PiModelInfo("M3", "T2", "minimax/MiniMax-M3")
        inject_route_decision(tmp_path, "test-run", "pi", pi_info)
        route = _read_route(tmp_path)

        assert route["modelSource"] == "complexity-classifier"
        assert route["complexityTier"] == "T2"

    def test_pi_dispatch_no_role_separation(self, tmp_path):
        _make_active_task(tmp_path)
        pi_info = PiModelInfo("M3", "T2", "minimax/MiniMax-M3")
        inject_route_decision(tmp_path, "test-run", "pi", pi_info)
        route = _read_route(tmp_path)

        assert route["roleSeparation"] is False
        assert route["plannerHarness"] is None
        assert route["plannerModelRoute"] is None
        assert route["implementerHarness"] == "pi"
        assert route["implementerModelRoute"] == "minimax/MiniMax-M3"

    def test_pi_dispatch_verifier_is_builtin(self, tmp_path):
        _make_active_task(tmp_path)
        pi_info = PiModelInfo("M3", "T2", "minimax/MiniMax-M3")
        inject_route_decision(tmp_path, "test-run", "pi", pi_info)
        route = _read_route(tmp_path)

        assert route["verifierHarness"] == "builtin-scripts"
        assert route["verifierModelRoute"] is None
        assert route["selfVerificationAllowed"] is False
        assert route["piTranscriptReview"] is True


# ---------------------------------------------------------------------------
# Local dispatch
# ---------------------------------------------------------------------------

class TestRouteDecisionLocal:
    """TASK-002 Option B: dispatch=="local" is verification-only.

    No worker is spawned, no model is chosen. GO_LOCAL_LLM is dead and removed.
    These tests pin the verification-only semantics: modelSource is "unknown",
    chosenModel is None, and the harness label still records "local" as the
    chosen dispatch mode (it's the mode the user selected, just workerless).
    """

    def test_local_dispatch_records_flat_single_harness(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "local")
        route = _read_route(tmp_path)

        assert route["dispatchMode"] == "flat-single-harness"
        assert route["singleDispatchHarness"] == "local"
        assert route["chosenDispatch"] == "local"

    def test_local_model_source_unknown(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "local")
        route = _read_route(tmp_path)

        assert route["modelSource"] == "unknown"

    def test_local_chosen_model_is_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "local")
        route = _read_route(tmp_path)

        assert route["chosenModel"] is None
        assert route["singleDispatchModel"] is None

    def test_local_dispatch_pi_in_rejected(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "local")
        route = _read_route(tmp_path)

        rejected_names = [r["harness"] for r in route["rejectedHarnesses"]]
        assert "pi" in rejected_names

    def test_local_pi_transcript_review_false(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "local")
        route = _read_route(tmp_path)

        assert route["piTranscriptReview"] is False


# ---------------------------------------------------------------------------
# Claude dispatch (stub)
# ---------------------------------------------------------------------------

class TestRouteDecisionClaude:
    def test_claude_rejected_as_stub(self, tmp_path):
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "claude")
        route = _read_route(tmp_path)

        rejected = {r["harness"]: r["reason"] for r in route["rejectedHarnesses"]}
        assert "claude" in rejected
        assert "stub" in rejected["claude"].lower()


# ---------------------------------------------------------------------------
# agy appears as not-wired
# ---------------------------------------------------------------------------

class TestRouteDecisionAgy:
    def test_agy_in_rejected_not_wired(self, tmp_path):
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "pi")
        route = _read_route(tmp_path)

        rejected = {r["harness"]: r["reason"] for r in route["rejectedHarnesses"]}
        assert "agy" in rejected
        assert "not-wired" in rejected["agy"].lower()

    def test_agy_not_in_valid_dispatches(self):
        """agy must not be a valid dispatch option."""
        from orchestrate import VALID_DISPATCHES
        assert "agy" not in VALID_DISPATCHES


# ---------------------------------------------------------------------------
# GO_LOCAL_LLM unset
# ---------------------------------------------------------------------------

class TestRouteDecisionLocalUnavailable:
    def test_unset_go_local_llm_recorded_as_unavailable_when_not_chosen(self, tmp_path, monkeypatch):
        """When dispatch is pi and GO_LOCAL_LLM is unset, local is rejected as unavailable."""
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "pi")
        route = _read_route(tmp_path)

        rejected = {r["harness"]: r["reason"] for r in route["rejectedHarnesses"]}
        assert "local" in rejected
        assert "unavailable" in rejected["local"].lower()

    def test_unset_go_local_llm_model_is_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GO_LOCAL_LLM", raising=False)
        _make_active_task(tmp_path)
        inject_route_decision(tmp_path, "test-run", "local")
        route = _read_route(tmp_path)

        assert route["singleDispatchModel"] is None


# ---------------------------------------------------------------------------
# Required keys
# ---------------------------------------------------------------------------

class TestRouteDecisionKeys:
    def test_pi_has_all_required_keys(self, tmp_path):
        _make_active_task(tmp_path)
        pi_info = PiModelInfo("M3", "T2", "minimax/MiniMax-M3")
        inject_route_decision(tmp_path, "test-run", "pi", pi_info)
        route = _read_route(tmp_path)

        required = [
            "roleSeparation", "dispatchMode",
            "plannerHarness", "plannerModelRoute",
            "implementerHarness", "implementerModelRoute",
            "verifierHarness", "verifierModelRoute",
            "selfVerificationAllowed", "piTranscriptReview",
            "singleDispatchHarness", "singleDispatchModel",
            "chosenDispatch", "chosenModel",
            "modelSource", "complexityTier",
            "fallbackPolicyVisibleToGo", "actualFallbackObserved",
            "rejectedHarnesses",
        ]
        for key in required:
            assert key in route, f"missing required key: {key}"

    def test_no_role_separation_claimed(self, tmp_path):
        _make_active_task(tmp_path)
        pi_info = PiModelInfo("M3", "T2", "minimax/MiniMax-M3")
        inject_route_decision(tmp_path, "test-run", "pi", pi_info)
        route = _read_route(tmp_path)

        assert route["roleSeparation"] is False
        assert route["dispatchMode"] == "flat-single-harness"


# ---------------------------------------------------------------------------
# GO_MODEL_OVERRIDE
# ---------------------------------------------------------------------------

class TestRouteDecisionOverride:
    def test_override_model_source(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GO_MODEL_OVERRIDE", "anthropic/claude-sonnet-4-20250514")
        _make_active_task(tmp_path)
        # Override is read at classify time, not at inject time.
        # But inject_route_decision checks the env var directly.
        inject_route_decision(tmp_path, "test-run", "pi", None)
        route = _read_route(tmp_path)

        assert route["modelSource"] == "GO_MODEL_OVERRIDE"
        assert route["chosenModel"] == "anthropic/claude-sonnet-4-20250514"
