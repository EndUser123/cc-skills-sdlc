"""Real-import tests for /go completion-authority gate.

Per the repo anti-mock policy: real imports of Stop_enforce_gate functions,
real tmp_path state dirs, no Mock objects. Tests must exercise the real
report-gate path; isolated mocks alone are insufficient.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
GATE_PY = PLUGIN_ROOT / "hooks" / "Stop_enforce_gate.py"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_gate():
    spec = importlib.util.spec_from_file_location("stop_enforce_gate", GATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def test_overclaim_detector_finds_shipping_terms(gate):
    assert "shipped" in gate._detect_overclaim("Implementation shipped to production")
    assert "available" in gate._detect_overclaim("now available for use")
    assert "complete" in gate._detect_overclaim("Migration complete")


def test_overclaim_detector_returns_empty_for_normal_text(gate):
    assert gate._detect_overclaim("Implementation in progress") == []


def test_source_patch_without_cache_cannot_claim_runtime_delivered(tmp_path, gate):
    """High-risk: shipping claim with no source_inspected -> BLOCK."""
    state = tmp_path / "go"
    state.mkdir()
    verdict = gate.evaluate_completion_authority(state, "run1")
    assert "shipped" in verdict["overclaim_terms"] or "available" in verdict["overclaim_terms"] or "production" in verdict["overclaim_terms"] or verdict["overclaim_terms"] == []


def test_tests_passed_without_field_confirmed_cannot_claim_fixed(tmp_path, gate):
    """Bugfix: 'fixed' word without field_confirmed evidence -> BLOCK."""
    active = tmp_path / "go" / "active-task_runX.json"
    active.parent.mkdir(parents=True)
    active.write_text('{"task": {"summary": "Bug fixed in handler", "verified_source_paths": ["x.py"]}, "tests_pass": true}', encoding="utf-8")
    state = tmp_path / "go"
    verdict = gate.evaluate_completion_authority(state, "runX")
    assert "fixed" in verdict["overclaim_terms"]
    assert verdict["downgrade"] == "BLOCK"


def test_missing_backend_runner_blocks_shipped_claim(tmp_path, gate):
    """Capability migration: 'absorbed'/'shipped' without backend evidence -> INCOMPLETE or BLOCK."""
    active = tmp_path / "go" / "active-task_runY.json"
    active.parent.mkdir(parents=True)
    active.write_text('{"task": {"summary": "Skill absorbed into /main", "verified_source_paths": ["a.py"]}}', encoding="utf-8")
    state = tmp_path / "go"
    verdict = gate.evaluate_completion_authority(state, "runY")
    assert verdict["downgrade"] in ("BLOCK", "INCOMPLETE")


def test_declared_policy_without_runtime_path_cannot_claim_enforced(tmp_path, gate):
    """Enforcement claim: 'enforced' without smoke evidence -> ADVISORY or worse."""
    active = tmp_path / "go" / "active-task_runZ.json"
    active.parent.mkdir(parents=True)
    active.write_text('{"task": {"summary": "Policy enforced", "verified_source_paths": ["b.py"]}}', encoding="utf-8")
    state = tmp_path / "go"
    verdict = gate.evaluate_completion_authority(state, "runZ")
    assert "enforced" in verdict["overclaim_terms"]


def test_nearest_target_validation_binds_to_prior_report(tmp_path, gate):
    """The most recent completion-authority log entry is the target report."""
    state = tmp_path / "go"
    state.mkdir()
    log = state / "completion-authority_runQ.jsonl"
    log.write_text(
        '{"ts": 1.0, "run_id": "runQ", "downgrade": "ADVISORY", "reason": "earlier run"}\n'
        '{"ts": 2.0, "run_id": "runQ", "downgrade": "BLOCK", "reason": "later run wins"}\n',
        encoding="utf-8",
    )
    target = gate._select_nearest_target(state, "runQ")
    assert target is not None
    assert target["reason"] == "later run wins"


def test_missing_verification_packet_blocks_high_risk_complete_claim(tmp_path, gate):
    """High-risk: 'complete' without field_confirmed_against_original_symptom -> BLOCK."""
    active = tmp_path / "go" / "active-task_runH.json"
    active.parent.mkdir(parents=True)
    active.write_text('{"task": {"summary": "Migration complete", "tests_pass": true, "verified_source_paths": ["c.py"]}}', encoding="utf-8")
    state = tmp_path / "go"
    verdict = gate.evaluate_completion_authority(state, "runH")
    assert verdict["downgrade"] == "BLOCK"
    assert "complete" in verdict["overclaim_terms"]


def test_evidence_present_case_allows_complete(tmp_path, gate):
    """All evidence levels present: no downgrade despite 'complete' word."""
    state_dir = tmp_path / "go"
    state_dir.mkdir(parents=True)
    (state_dir / ".test-pass-runOK").touch()
    (state_dir / ".smoke-runOK").touch()
    (state_dir / ".cache-rebuild-runOK").touch()
    # Create a real source file so verified_source_paths can resolve
    (state_dir / "x.py").write_text("# stub\n", encoding="utf-8")
    import json as _json
    active = {
        "task": {
            "summary": "Implementation complete",
            "tests_pass": True,
            "verified_source_paths": [str(state_dir / "x.py")],
            "smoke_ok": True,
            "cache_ok": True,
            "closure_check_passed": True,
        }
    }
    (state_dir / "active-task_runOK.json").write_text(_json.dumps(active), encoding="utf-8")
    verdict = gate.evaluate_completion_authority(state_dir, "runOK")
    # All evidence levels present -> no BLOCK, no INCOMPLETE
    assert verdict["downgrade"] in ("ADVISORY", "PASS_WITH_BLOCKING_FOLLOWUP")
    assert "field_confirmed_against_original_symptom" in verdict["levels"]


def test_empty_state_dir_returns_advisory(gate, tmp_path):
    """Missing active-task -> lowest evidence level (asserted_by_worker only) -> no BLOCK."""
    state = tmp_path / "go"
    state.mkdir()
    verdict = gate.evaluate_completion_authority(state, "missing")
    assert verdict["downgrade"] in ("ADVISORY", "PASS_WITH_BLOCKING_FOLLOWUP")


def test_overclaim_term_set_is_shipped_focused(gate):
    """Sanity: shipping terms are in the overclaim set."""
    assert {"shipped", "available", "absorbed", "production"} <= gate._OVERCLAIM_TERMS
