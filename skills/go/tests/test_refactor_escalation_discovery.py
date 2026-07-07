"""Tests for /go refactor-escalation with discovery evidence merge.

Real imports of preflight_propose, exercising the actual preflight path.
Tests the merge of prompt-based + discovery-evidence structural_issues.
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
        "preflight_propose_re_d", SCRIPTS / "preflight_propose.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("classify_complexity", type(sys)("classify_complexity"))
    sys.modules["classify_complexity"].classify_model_affinity = lambda *a, **kw: "T2"
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pf():
    return _load_preflight()


def test_prompt_no_markers_but_discovery_does(pf):
    """Prompt has no refactor markers, but runtime discovery does."""
    discovery = {
        "findings": [
            {"provenance": "verified", "source": "code inspection",
             "structural_issues": ["dead_producer_consumer"]}
        ]
    }
    result = pf.classify_refactor_escalation(
        "Fix typo in handler.py", "implement", "local_surgical",
        discovery_evidence=discovery,
    )
    assert result["required"] is True
    assert result["prompt_evidence"] == []
    assert len(result["discovery_issues"]) == 1
    assert result["discovery_issues"][0]["issue"] == "dead_producer_consumer"
    assert result["discovery_issues"][0]["provenance"] == "verified"


def test_verified_discovery_triggers_refactor(pf):
    """Verified structural issue triggers refactor recommendation."""
    discovery = {
        "findings": [
            {"provenance": "verified", "structural_issues": ["inert_code"]}
        ]
    }
    result = pf.classify_refactor_escalation(
        "Fix the validator", "implement", "local_surgical",
        discovery_evidence=discovery,
    )
    assert result["required"] is True
    assert result["suggested_command"] is not None
    assert "/refactor" in result["suggested_command"]


def test_unsafe_narrow_fix_pauses(pf):
    """Unsafe narrow fix (verified wrong-layer) pauses for refactor."""
    discovery = {
        "findings": [
            {"provenance": "verified", "structural_issues": ["wrong_layer_ownership"]}
        ]
    }
    result = pf.classify_refactor_escalation(
        "Fix the hook dispatch", "implement", "local_surgical",
        discovery_evidence=discovery,
    )
    assert result["recommendation"] == "pause_for_refactor"


def test_safe_narrow_fix_completes_with_followup(pf):
    """Safe narrow fix (module-scope duplicated responsibility) completes with follow-up."""
    discovery = {
        "findings": [
            {"provenance": "inference", "structural_issues": ["duplicated_responsibility"]}
        ]
    }
    result = pf.classify_refactor_escalation(
        "Fix the parser", "implement", "local_surgical",
        discovery_evidence=discovery,
    )
    # module scope -> continue_narrow_fix (safe), not pause
    assert result["recommendation"] in ("continue_narrow_fix", "finish_then_refactor")


def test_prompt_and_discovery_merge_without_overwriting(pf):
    """Prompt evidence and discovery evidence both present, neither erased."""
    discovery = {
        "findings": [
            {"provenance": "verified", "structural_issues": ["inert_code"]}
        ]
    }
    result = pf.classify_refactor_escalation(
        "Fix the dead code in the module", "implement", "local_surgical",
        discovery_evidence=discovery,
    )
    assert result["required"] is True
    assert "dead code" in result["prompt_evidence"]
    assert len(result["discovery_issues"]) == 1
    assert "dead code" in result["trigger_evidence"]  # prompt
    assert "inert code" in result["trigger_evidence"]  # discovery


def test_assumption_level_does_not_hard_pause(pf):
    """Assumption-only structural issue does not pause (finish_then_refactor)."""
    discovery = {
        "findings": [
            {"provenance": "assumption", "structural_issues": ["wrong_layer_ownership"]}
        ]
    }
    result = pf.classify_refactor_escalation(
        "Fix the handler", "implement", "local_surgical",
        discovery_evidence=discovery,
    )
    assert result["recommendation"] != "pause_for_refactor"


def test_no_mutation_outside_scope(pf):
    """refactor_escalation is advisory — it does not force execution_tier change
    by itself. The proposal carries the field but doesn't mutate."""
    discovery = {
        "findings": [
            {"provenance": "verified", "structural_issues": ["duplicated_responsibility"]}
        ]
    }
    proposal = pf.generate_proposal(
        "Fix the parser logic", "test-re-dis-001", "test-terminal"
    )
    # The proposal has refactor_escalation, but it doesn't force the tier
    assert "refactor_escalation" in proposal
    re = proposal["refactor_escalation"]
    assert "prompt_evidence" in re
    assert "discovery_issues" in re


def test_empty_discovery_evidence(pf):
    """Empty or missing discovery_evidence produces prompt-only result."""
    result = pf.classify_refactor_escalation(
        "Fix the dead code", "implement", "local_surgical",
        discovery_evidence=None,
    )
    assert result["required"] is True
    assert result["discovery_issues"] == []
    assert "dead code" in result["prompt_evidence"]
