"""Tests for mechanism-change resolution fields on the /go proposal.

Covers the durable invariant: for tasks that trigger existing operational
discovery (or arrive with upstream mechanism-change metadata), /go must
resolve the change as one of NO_CHANGE | CLARIFY_EXISTING | EXTEND_EXISTING |
SIMPLIFY_EXISTING | NEW_MECHANISM_JUSTIFIED | BLOCKED, and must NOT edit when
the resolution is NO_CHANGE or BLOCKED.

Activation rides existing operational_discovery.required — there is NO new
prompt keyword classifier (regression test below pins that).
"""
import json

import pytest

from preflight_propose import (
    classify_mechanism_change,
    classify_operational_discovery,
    derive_report_gate,
    generate_proposal,
    apply_discovery_evidence_merge,
    _MECHANISM_EXTENSION_PATHS,
    _MECHANISM_REPORT_ONLY_PATHS,
)


# --- Activation: only existing signals, no keyword classifier ----------------

def test_ordinary_implementation_prompt_does_not_require_mechanism_change():
    p = generate_proposal("fix the off-by-one in parser.py", "r1", "t1")
    mc = p["mechanism_change"]
    assert mc["required"] is False
    assert mc["extension_path"] is None
    assert mc["closest_existing_mechanisms"] == []


def test_no_new_keyword_classifier_for_meta_words():
    # "improve /design by adding rules" contains no operational surface and no
    # upstream signal. classify_mechanism_change must NOT fire on the bare words
    # "improve", "design", "rules" — that was the rejected classifier approach.
    od = classify_operational_discovery("improve /design by adding attention rules", "implement")
    mc = classify_mechanism_change("improve /design by adding attention rules", "implement", od)
    # operational_discovery does not fire on "design" alone => mc not required.
    assert od["required"] is False
    assert mc["required"] is False


def test_operational_discovery_activates_mechanism_change():
    od = classify_operational_discovery("investigate why the hook double-fires", "investigate")
    assert od["required"] is True
    mc = classify_mechanism_change("investigate why the hook double-fires", "investigate", od)
    assert mc["required"] is True
    assert mc["activated_by"] == "operational_discovery"
    # scaffold only — worker resolves after source read
    assert mc["extension_path"] is None
    assert mc["closest_existing_mechanisms"] == []
    assert set(mc["allowed_paths"]) == _MECHANISM_EXTENSION_PATHS


def test_upstream_signal_activates_even_without_operational_discovery():
    od = {"required": False}
    mc = classify_mechanism_change("anything", "implement", od, upstream_signal=True)
    assert mc["required"] is True
    assert mc["activated_by"] == "upstream_signal"


# --- Report-gate enforcement ------------------------------------------------

@pytest.mark.parametrize("path", sorted(_MECHANISM_REPORT_ONLY_PATHS))
def test_report_only_paths_block_completion(path):
    gate = derive_report_gate("implement", "full_go", mechanism_change={
        "required": True, "extension_path": path,
        "closest_existing_mechanisms": ["x"],
    })
    assert gate["mechanism_change_report_only"] is True
    assert gate["allow_implementation_completion_claim"] is False
    assert gate["allow_targeted_fix_claim_only"] is False


@pytest.mark.parametrize("path", [
    "CLARIFY_EXISTING", "EXTEND_EXISTING", "SIMPLIFY_EXISTING", "NEW_MECHANISM_JUSTIFIED",
])
def test_proceed_paths_allow_completion_when_closest_named(path):
    gate = derive_report_gate("implement", "full_go", mechanism_change={
        "required": True, "extension_path": path,
        "closest_existing_mechanisms": ["preflight_propose.classify_operational_discovery"],
    })
    assert gate["mechanism_change_report_only"] is False
    assert gate["allow_implementation_completion_claim"] is True


def test_new_mechanism_without_closest_existing_is_advisory_not_accepted():
    gate = derive_report_gate("implement", "full_go", mechanism_change={
        "required": True, "extension_path": "NEW_MECHANISM_JUSTIFIED",
        "closest_existing_mechanisms": [],
    })
    # flagged advisory, not silently accepted as completion-eligible
    assert gate["mechanism_change_new_unjustified"] is True
    # a new BLOCKING gate/classifier without corpus evidence must not be
    # silently accepted — director decides (advisory), so completion is not
    # blocked automatically; the flag is the signal.
    assert gate["mechanism_change_report_only"] is False


# --- Backward compatibility: no regression when mechanism_change absent ------

def test_derive_report_gate_unchanged_without_mechanism_change():
    # Same inputs as the existing test_preflight_intent expectations.
    assert derive_report_gate("implement", "full_go")["allow_implementation_completion_claim"] is True
    assert derive_report_gate("investigate", "direct_answer")["allow_implementation_completion_claim"] is False
    # New keys default to "not required" when mechanism_change is None.
    gate = derive_report_gate("implement", "full_go")
    assert gate["mechanism_change_required"] is False
    assert gate["mechanism_change_report_only"] is False


def test_full_proposal_routing_unchanged_for_ordinary_tasks():
    # Routing values must match what they were before the mechanism_change
    # addition for a plain bounded implementation prompt.
    p = generate_proposal("fix the typo in foo.py", "r", "t")
    assert p["task_intent"] == "implement"
    assert p["suggestedDispatch"] in ("pi", "local", "claude")
    assert p["mechanism_change"]["required"] is False
    # report_gate completion eligibility is a function of tier/intent only here.
    assert isinstance(p["report_gate"]["allow_implementation_completion_claim"], bool)


# --- Integration: discovery-evidence merge resolves extension_path -----------

def test_apply_merge_resolves_extension_path_and_blocks_on_no_change(tmp_path):
    proposal = generate_proposal("investigate why the hook double-fires", "r-merge", "t-merge")
    assert proposal["mechanism_change"]["required"] is True
    # write proposal
    (tmp_path / "task-proposal_r-merge.json").write_text(
        json.dumps(proposal), encoding="utf-8")
    # worker resolved the change after reading source: NO_CHANGE (existing
    # machinery already covers it) — written to the standard discovery file.
    (tmp_path / "discovery-evidence_r-merge.json").write_text(json.dumps({
        "findings": [{"source": "src.py", "provenance": "verified",
                      "summary": "already covered"}],
        "mechanism_change": {
            "extension_path": "NO_CHANGE",
            "closest_existing_mechanisms": ["preflight_propose.classify_operational_discovery"],
        },
    }), encoding="utf-8")
    ok = apply_discovery_evidence_merge(tmp_path, "r-merge")
    assert ok is True
    merged = json.loads((tmp_path / "task-proposal_r-merge.json").read_text(encoding="utf-8"))
    mc = merged["mechanism_change"]
    assert mc["extension_path"] == "NO_CHANGE"
    assert mc["report_only"] is True
    assert merged["report_gate"]["mechanism_change_report_only"] is True
    assert merged["report_gate"]["allow_implementation_completion_claim"] is False


def test_apply_merge_extends_existing_allows_completion(tmp_path):
    proposal = generate_proposal("investigate why the hook double-fires", "r-ext", "t-ext")
    (tmp_path / "task-proposal_r-ext.json").write_text(
        json.dumps(proposal), encoding="utf-8")
    (tmp_path / "discovery-evidence_r-ext.json").write_text(json.dumps({
        "mechanism_change": {
            "extension_path": "EXTEND_EXISTING",
            "closest_existing_mechanisms": ["preflight_propose.classify_operational_discovery"],
        },
    }), encoding="utf-8")
    apply_discovery_evidence_merge(tmp_path, "r-ext")
    merged = json.loads((tmp_path / "task-proposal_r-ext.json").read_text(encoding="utf-8"))
    assert merged["mechanism_change"]["extension_path"] == "EXTEND_EXISTING"
    assert merged["mechanism_change"]["report_only"] is False


def test_apply_merge_rejects_unknown_extension_path(tmp_path):
    proposal = generate_proposal("investigate why the hook double-fires", "r-bad", "t-bad")
    (tmp_path / "task-proposal_r-bad.json").write_text(
        json.dumps(proposal), encoding="utf-8")
    (tmp_path / "discovery-evidence_r-bad.json").write_text(json.dumps({
        "mechanism_change": {"extension_path": "BOGUS_PATH"},
    }), encoding="utf-8")
    apply_discovery_evidence_merge(tmp_path, "r-bad")
    merged = json.loads((tmp_path / "task-proposal_r-bad.json").read_text(encoding="utf-8"))
    # unknown path is ignored — preflight scaffold (None) preserved
    assert merged["mechanism_change"]["extension_path"] is None
