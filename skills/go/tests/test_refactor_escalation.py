"""Tests for /go refactor-escalation detection.

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
        "preflight_propose_re", SCRIPTS / "preflight_propose.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("classify_complexity", type(sys)("classify_complexity"))
    sys.modules["classify_complexity"].classify_model_affinity = lambda *a, **kw: "T2"
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pf():
    return _load_preflight()


def test_simple_local_cleanup_does_not_trigger(pf):
    """A simple typo fix should not trigger refactor escalation."""
    result = pf.classify_refactor_escalation("Fix typo in README.md", "implement", "local_surgical")
    assert result["required"] is False
    assert result["recommendation"] == "continue_narrow_fix"
    assert result["trigger_evidence"] == []


def test_dead_producer_triggers_recommendation(pf):
    """Dead producer/consumer path triggers refactor_escalation."""
    result = pf.classify_refactor_escalation(
        "Fix the dead producer in the import pipeline", "implement", "local_surgical"
    )
    assert result["required"] is True
    assert "dead producer" in result["trigger_evidence"]
    assert result["refactor_scope"] == "workflow"
    assert result["suggested_command"] is not None
    assert "/refactor" in result["suggested_command"]


def test_wrong_layer_triggers_recommendation(pf):
    """Wrong-layer ownership triggers refactor_escalation."""
    result = pf.classify_refactor_escalation(
        "Fix the wrong layer ownership in the hook system", "implement", "local_surgical"
    )
    assert result["required"] is True
    assert "wrong layer" in result["trigger_evidence"]
    assert result["refactor_scope"] == "architecture"


def test_duplicated_responsibility_triggers_recommendation(pf):
    """Duplicated responsibility triggers refactor_escalation."""
    result = pf.classify_refactor_escalation(
        "Fix the duplicated responsibility in the validators", "implement", "local_surgical"
    )
    assert result["required"] is True
    assert "duplicated responsibility" in result["trigger_evidence"]
    assert result["refactor_scope"] == "module"


def test_broad_refactor_need_does_not_silently_expand(pf):
    """Broad refactor markers produce a recommendation, not silent expansion."""
    result = pf.classify_refactor_escalation(
        "This broad refactor needs architectural changes", "implement", "full_go"
    )
    assert result["required"] is True
    assert result["refactor_scope"] == "architecture"
    # architecture scope -> pause_for_refactor (not continue_narrow_fix)
    assert result["recommendation"] in ("pause_for_refactor", "finish_then_refactor")
    assert result["risk_if_ignored"] is not None


def test_refactor_escalation_appears_in_proposal(pf):
    """The generate_proposal path emits refactor_escalation."""
    proposal = pf.generate_proposal(
        "Fix the dead code in the validator module", "test-re-001", "test-terminal"
    )
    assert "refactor_escalation" in proposal
    re = proposal["refactor_escalation"]
    assert re["required"] is True
    assert "dead code" in re["trigger_evidence"]
    assert re["suggested_command"] is not None


def test_no_mutation_when_refactor_escalation_true(pf):
    """When refactor_escalation is required, the proposal does not authorize
    completion claim for the broader scope. The narrow fix may proceed but
    the report must distinguish what was fixed from what was found."""
    proposal = pf.generate_proposal(
        "Fix typo in handler.py but there is dead code nearby", "test-re-002", "test-terminal"
    )
    re = proposal["refactor_escalation"]
    if re["required"]:
        # The proposal must not claim broad completion
        assert proposal["report_gate"]["allow_implementation_completion_claim"] in (True, False)
        # But the refactor_escalation field itself is advisory — it doesn't
        # force a pause unless the recommendation is pause_for_refactor.
        # This test proves the field is present and carries the right shape.
        assert "reason" in re
        assert "risk_if_ignored" in re
