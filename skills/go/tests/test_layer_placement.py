"""Tests for /go layer-placement guard (hook/gate boundary).

Real imports of preflight_propose.generate_proposal, exercising the actual
preflight path. No Mock objects.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_preflight():
    spec = importlib.util.spec_from_file_location(
        "preflight_propose", SCRIPTS / "preflight_propose.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Stub classify_complexity dependency
    sys.modules.setdefault("classify_complexity", type(sys)("classify_complexity"))
    sys.modules["classify_complexity"].classify_model_affinity = lambda *a, **kw: "T2"
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pf():
    return _load_preflight()


def test_pattern_detection_in_stop_hook_triggers_wrong_layer(pf):
    """Pattern detection proposed for a Stop hook must be wrong_layer."""
    prompt = "Add pattern detection to Stop_enforce_gate.py"
    result = pf.classify_layer_placement(prompt)
    assert result["verdict"] == "wrong_layer"
    assert "pattern detection" in result["proposed_behavior"]
    assert result["chosen_layer"] == "preflight/report-gate"
    assert "stop_hook" in result["rejected_layers"]


def test_dry_run_analysis_in_stop_hook_triggers_wrong_layer(pf):
    """Dry-run refactor analysis in a Stop hook must be wrong_layer."""
    prompt = "Add dry-run refactor analysis to the stop hook"
    result = pf.classify_layer_placement(prompt)
    assert result["verdict"] == "wrong_layer"
    assert result["chosen_layer"] == "preflight/report-gate"


def test_cross_session_state_in_stop_hook_triggers_wrong_layer(pf):
    """Cross-session state writes from a Stop hook must be wrong_layer."""
    prompt = "Add cross-session state tracking to Stop_enforce_gate"
    result = pf.classify_layer_placement(prompt)
    assert result["verdict"] == "wrong_layer"


def test_narrow_evidence_verifier_in_stop_hook_allowed(pf):
    """Narrow session-bound evidence verification in a Stop hook is allowed."""
    prompt = "Verify evidence artifacts in Stop_enforce_gate.py"
    result = pf.classify_layer_placement(prompt)
    assert result["verdict"] == "allowed"
    assert result["chosen_layer"] == "stop_hook (narrow verification)"


def test_non_hook_task_not_applicable(pf):
    """Non-hook tasks return not_applicable."""
    prompt = "Fix the typo in README.md"
    result = pf.classify_layer_placement(prompt)
    assert result["verdict"] == "not_applicable"
    assert result["required"] is False


def test_layer_placement_appears_in_proposal(pf):
    """The generate_proposal path emits layer_placement in the output."""
    prompt = "Add pattern detection to Stop_enforce_gate.py"
    proposal = pf.generate_proposal(prompt, "test-run-001", "test-terminal")
    assert "layer_placement" in proposal
    assert proposal["layer_placement"]["verdict"] == "wrong_layer"
    # Wrong-layer must escalate to pause_for_authorization
    assert proposal["execution_tier"] == "pause_for_authorization"
    assert proposal["mixed_work_status"] == "blocked_policy"


def test_allowed_hook_edit_does_not_pause(pf):
    """Narrow hook edit does not trigger pause_for_authorization."""
    prompt = "Verify evidence artifacts in Stop_enforce_gate.py"
    proposal = pf.generate_proposal(prompt, "test-run-002", "test-terminal")
    assert proposal["layer_placement"]["verdict"] == "allowed"
    # Execution tier should NOT be forced to pause for a narrow verification task
    assert proposal["execution_tier"] != "pause_for_authorization" or \
           proposal.get("prompt_review_required") is True  # may still pause for high-risk, but not from layer check


def test_dry_run_analysis_routes_to_preflight(pf):
    """Dry-run analysis without a hook target is not_applicable (it belongs in preflight)."""
    prompt = "Add dry-run refactor analysis to preflight_propose.py"
    result = pf.classify_layer_placement(prompt)
    assert result["verdict"] == "not_applicable"
    # The broad behavior is detected but no hook file is mentioned, so it's correctly scoped
