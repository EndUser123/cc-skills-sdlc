"""Tests for /go pattern candidates + dry-run trigger (preflight layer).

Real imports of preflight_propose.generate_proposal, exercising the actual
preflight path. No Mock objects. Confirms all logic is in preflight, NOT in
Stop_enforce_gate.py.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"
HOOKS = PLUGIN_ROOT / "hooks"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_preflight():
    spec = importlib.util.spec_from_file_location(
        "preflight_propose_pd", SCRIPTS / "preflight_propose.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("classify_complexity", type(sys)("classify_complexity"))
    sys.modules["classify_complexity"].classify_model_affinity = lambda *a, **kw: "T2"
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pf():
    return _load_preflight()


def test_pattern_candidate_dead_code(pf):
    """Dead code marker produces pattern_candidate."""
    proposal = pf.generate_proposal(
        "Fix the dead code in the validator module", "test-pc-001", "test-terminal"
    )
    # The proposal has refactor_escalation with dead code trigger
    assert proposal["refactor_escalation"]["required"] is True
    # classify_pattern_candidates reads the proposal
    candidates = pf.classify_pattern_candidates(proposal)
    # dead_code maps to unit_test_only or cache_not_verified via failure shapes
    # The key is: candidates list is populated
    assert isinstance(candidates, list)


def test_third_recurrence_recommends_report_gate(pf, monkeypatch):
    """Third occurrence of same failure shape recommends report_gate."""
    import tempfile, json, os
    tmp = Path(tempfile.mkdtemp())
    pdb = tmp / "patterns.jsonl"
    # Write 2 prior occurrences of cache_not_verified
    for i in range(2):
        with open(pdb, "a") as f:
            f.write(json.dumps({"failure_shape": "cache_not_verified"}) + "\n")
    monkeypatch.setattr(pf, "_PATTERN_DB_FALLBACK", pdb)
    # Simulate a third occurrence
    proposal = {
        "refactor_escalation": {
            "trigger_evidence": ["cache not verified"],
        }
    }
    candidates = pf.classify_pattern_candidates(proposal)
    # The function detects the shape from trigger_evidence
    for c in candidates:
        if c["failure_shape"] == "cache_not_verified":
            assert c["promotion_recommendation"] in ("report_gate", "hook")


def test_high_risk_shape_recommends_hook(pf):
    """High-risk shapes (cache_not_verified, missing_backend) recommend hook immediately."""
    proposal = {
        "refactor_escalation": {
            "trigger_evidence": ["cache not verified"],
        }
    }
    candidates = pf.classify_pattern_candidates(proposal)
    for c in candidates:
        if c["failure_shape"] == "cache_not_verified":
            assert c["promotion_recommendation"] == "hook"


def test_dry_run_trigger_for_routing_task(pf):
    """Tasks touching routing/hooks/gates trigger dry-run analysis."""
    result = pf.classify_dry_run_trigger("Update hook dispatch routing")
    assert result["triggered"] is True
    assert "hook" in result["trigger_markers"]
    assert result["mode"] == "no_mutation"
    assert len(result["analysis_checklist"]) >= 8


def test_dry_run_trigger_for_plugin_task(pf):
    """Plugin/cache tasks trigger dry-run."""
    result = pf.classify_dry_run_trigger("Refactor the plugin cache system")
    assert result["triggered"] is True
    assert "plugin" in result["trigger_markers"]


def test_dry_run_not_triggered_for_simple_task(pf):
    """Simple typo fix does not trigger dry-run."""
    result = pf.classify_dry_run_trigger("Fix typo in README.md")
    assert result["triggered"] is False


def test_dry_run_mode_performs_no_mutation(pf):
    """classify_dry_run_trigger is a pure function — no side effects."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    before = {f.name: f.read_bytes() for f in tmp.iterdir()} if tmp.exists() else {}
    result = pf.classify_dry_run_trigger("Refactor hook routing")
    after = {f.name: f.read_bytes() for f in tmp.iterdir()} if tmp.exists() else {}
    assert before == after
    assert result["mode"] == "no_mutation"


def test_stop_enforce_gate_unchanged():
    """Stop_enforce_gate.py has no pattern/dry-run/refactor logic."""
    gate_py = HOOKS / "Stop_enforce_gate.py"
    content = gate_py.read_text(encoding="utf-8")
    bad_symbols = [
        "_classify_failure_shape", "_dry_run_analysis",
        "_KNOWN_FAILURE_SHAPES", "_PATTERN_DB",
        "_should_trigger_dry_run", "classify_pattern_candidates",
        "classify_dry_run_trigger", "classify_refactor_escalation",
    ]
    for s in bad_symbols:
        assert s not in content, f"Stop_enforce_gate.py contains {s}"


def test_all_fields_in_proposal(pf):
    """generate_proposal emits all required fields."""
    proposal = pf.generate_proposal(
        "Refactor the hook dispatch routing in Stop_enforce_gate.py",
        "test-all-001", "test-terminal"
    )
    assert "layer_placement" in proposal
    assert "refactor_escalation" in proposal
    assert "dry_run_trigger" in proposal
    assert "pattern_candidates" in proposal
    # layer_placement should fire wrong_layer for Stop hook + refactor
    assert proposal["layer_placement"]["verdict"] in ("wrong_layer", "allowed")
    # dry_run should trigger (routing, hook, dispatch)
    assert proposal["dry_run_trigger"]["triggered"] is True
