#!/usr/bin/env python3
"""Tests for the improvement-candidate contract (validator + fixtures).

Covers:
  * valid candidate passes (incl. valid /friction and /behave fixtures)
  * missing required field fails
  * invalid enum fails
  * invalid candidate_id format fails
  * runtime_gate without mechanism_trace fails
  * hook without the full hook promotion checklist fails
  * runtime_gate without the full runtime-gate promotion checklist fails
  * review_status='implemented' without per-item satisfied+evidence fails
  * validator exits nonzero on an invalid file (subprocess invocation)
  * proposed candidate does NOT imply implementation (the contract allows
    'proposed' to pass; this test pins that contract behavior)
  * all three fixture examples behave as documented
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Mirror conftest.py's path setup so the validator script imports cleanly
# whether the suite is run via `pytest tests/...` or `python -m pytest`.
SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
REFS = SKILL_DIR / "references" / "examples"
SCHEMA = SKILL_DIR / "schemas" / "improvement_candidate.schema.json"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_improvement_candidate as vic  # noqa: E402


# ---------- minimal valid candidate (used as a template in tests) ----------

def _minimal_valid() -> dict:
    return {
        "candidate_id": "IC-MAN-test-fixture-001",
        "created_at": "2026-07-10T12:00:00Z",
        "source_skill": "manual",
        "observed_problem": "test",
        "evidence": ["test:1"],
        "evidence_tier": "user_report",
        "frequency": "once",
        "affected_layer": "prompt_only",
        "target_skill_or_system": "go",
        "candidate_type": "documentation_gap",
        "proposed_change": "test",
        "target_layer": "docs",
        "mechanism_trace": None,
        "confidence": "low",
        "risk": "low",
        "expected_benefit": "test",
        "failure_mode_prevented": "test",
        "falsification_condition": "test",
        "promotion_requirements": {
            "reviewer_acceptance": False,
            "evidence_basis": "test",
            "items": [],
        },
        "recommended_destination": "docs",
        "review_status": "proposed",
    }


# ---------- happy path ------------------------------------------------------

class TestHappyPath:
    def test_minimal_valid_passes(self):
        assert vic.validate_payload(_minimal_valid()) == []

    def test_proposed_does_not_imply_implementation(self):
        """Pin the contract: review_status='proposed' is a valid state.

        The validator must NOT reject 'proposed'; promotion is a separate step.
        """
        payload = _minimal_valid()
        payload["review_status"] = "proposed"
        assert vic.validate_payload(payload) == []

    def test_needs_evidence_also_valid(self):
        payload = _minimal_valid()
        payload["review_status"] = "needs_evidence"
        assert vic.validate_payload(payload) == []


# ---------- structural failures --------------------------------------------

class TestStructuralFailures:
    def test_missing_required_field(self):
        payload = _minimal_valid()
        del payload["observed_problem"]
        errs = vic.validate_payload(payload)
        assert any("missing required field 'observed_problem'" in e for e in errs), errs

    def test_invalid_enum_value(self):
        payload = _minimal_valid()
        payload["source_skill"] = "made_up_skill"
        errs = vic.validate_payload(payload)
        assert any("source_skill" in e and "made_up_skill" in e for e in errs), errs

    def test_invalid_enum_for_target_layer(self):
        payload = _minimal_valid()
        payload["target_layer"] = "everywhere"
        errs = vic.validate_payload(payload)
        assert any("target_layer" in e and "everywhere" in e for e in errs), errs

    def test_invalid_candidate_id_format(self):
        payload = _minimal_valid()
        payload["candidate_id"] = "not-ic-format"
        errs = vic.validate_payload(payload)
        assert any("candidate_id" in e for e in errs), errs

    def test_candidate_id_wrong_source_key(self):
        payload = _minimal_valid()
        payload["candidate_id"] = "IC-XX-foo"
        errs = vic.validate_payload(payload)
        assert any("candidate_id" in e for e in errs), errs

    def test_invalid_created_at_format(self):
        payload = _minimal_valid()
        payload["created_at"] = "10-Jul-2026"
        errs = vic.validate_payload(payload)
        assert any("created_at" in e for e in errs), errs

    def test_empty_evidence_array(self):
        payload = _minimal_valid()
        payload["evidence"] = []
        errs = vic.validate_payload(payload)
        assert any("evidence" in e for e in errs), errs


# ---------- cross-field: mechanism_trace required ---------------------------

class TestMechanismTraceRequired:
    def test_runtime_gate_without_mechanism_trace_fails(self):
        payload = _minimal_valid()
        payload["target_layer"] = "runtime_gate"
        payload["mechanism_trace"] = None
        errs = vic.validate_payload(payload)
        assert any("mechanism_trace" in e and "runtime_gate" in e for e in errs), errs

    def test_hook_without_mechanism_trace_fails(self):
        payload = _minimal_valid()
        payload["target_layer"] = "hook"
        payload["mechanism_trace"] = None
        errs = vic.validate_payload(payload)
        assert any("mechanism_trace" in e and "hook" in e for e in errs), errs

    def test_orchestrator_without_mechanism_trace_fails(self):
        payload = _minimal_valid()
        payload["target_layer"] = "orchestrator"
        payload["mechanism_trace"] = None
        errs = vic.validate_payload(payload)
        assert any("mechanism_trace" in e and "orchestrator" in e for e in errs), errs

    def test_validation_script_without_mechanism_trace_fails(self):
        payload = _minimal_valid()
        payload["target_layer"] = "validation_script"
        payload["mechanism_trace"] = None
        errs = vic.validate_payload(payload)
        assert any("mechanism_trace" in e and "validation_script" in e for e in errs), errs

    def test_runtime_gate_with_full_mechanism_trace_passes_structure(self):
        payload = _minimal_valid()
        payload["target_layer"] = "runtime_gate"
        payload["mechanism_trace"] = {
            "producer": "scripts/orchestrate.py:new_gate",
            "artifact_or_state": "gate-result_{RUN_ID}.json",
            "consumer": "scripts/orchestrate.py:read_gate",
            "authority_or_verdict": "new_gate verdict",
            "freshness_check": "assert_fresh(gate-result, run_id)",
            "failure_direction": "fail-open to default; explicit only when corpus evidence permits",
            "real_boundary_test": "spawn real subprocess + verify state file",
        }
        payload["promotion_requirements"]["items"] = [
            {"key": "real_boundary_test", "description": "Real-boundary test exists and passes."},
            {"key": "calibration_data", "description": "TP/FP measured on the gold corpus."},
            {"key": "fail_direction_decision", "description": "Fail-open vs fail-closed decision documented."},
            {"key": "owner_approval", "description": "Director sign-off recorded."},
        ]
        # still 'proposed' so no per-item satisfied/evidence needed
        assert vic.validate_payload(payload) == []


# ---------- cross-field: hook promotion checklist --------------------------

class TestHookPromotionChecklist:
    def _hook_target(self, items: list[dict]) -> dict:
        payload = _minimal_valid()
        payload["target_layer"] = "hook"
        payload["mechanism_trace"] = {
            "producer": "test",
            "artifact_or_state": "test",
            "consumer": "test",
            "authority_or_verdict": "test",
            "freshness_check": "test",
            "failure_direction": "test",
            "real_boundary_test": "test",
        }
        payload["promotion_requirements"]["items"] = items
        return payload

    def test_hook_missing_checklist_fails(self):
        # missing lifecycle_necessity, tested_script_underneath, safe_failure_direction,
        # explicit_registration_plan
        payload = self._hook_target([
            {"key": "deterministic_decision", "description": "..."},
        ])
        errs = vic.validate_payload(payload)
        assert any("hook target_layer" in e for e in errs), errs

    def test_hook_full_checklist_passes_structure(self):
        payload = self._hook_target([
            {"key": k, "description": "..."}
            for k in sorted(vic.HOOK_PROMOTION_KEYS)
        ])
        assert vic.validate_payload(payload) == []


# ---------- cross-field: runtime-gate promotion checklist ------------------

class TestRuntimeGatePromotionChecklist:
    def _gate_target(self, items: list[dict]) -> dict:
        payload = _minimal_valid()
        payload["target_layer"] = "runtime_gate"
        payload["mechanism_trace"] = {
            "producer": "t", "artifact_or_state": "t", "consumer": "t",
            "authority_or_verdict": "t", "freshness_check": "t",
            "failure_direction": "t", "real_boundary_test": "t",
        }
        payload["promotion_requirements"]["items"] = items
        return payload

    def test_runtime_gate_missing_checklist_fails(self):
        payload = self._gate_target([
            {"key": "real_boundary_test", "description": "..."},
        ])
        errs = vic.validate_payload(payload)
        assert any("runtime_gate target_layer" in e for e in errs), errs

    def test_runtime_gate_full_checklist_passes_structure(self):
        payload = self._gate_target([
            {"key": k, "description": "..."}
            for k in sorted(vic.RUNTIME_GATE_PROMOTION_KEYS)
        ])
        assert vic.validate_payload(payload) == []


# ---------- cross-field: implemented requires promotion evidence ------------

class TestImplementedRequiresEvidence:
    def test_implemented_without_per_item_evidence_fails(self):
        payload = _minimal_valid()
        payload["review_status"] = "implemented"
        payload["promotion_requirements"]["items"] = [
            {"key": "x", "description": "y", "satisfied": False, "evidence": ""},
        ]
        errs = vic.validate_payload(payload)
        assert any("satisfied=true" in e for e in errs), errs
        assert any("evidence" in e for e in errs), errs

    def test_implemented_with_per_item_evidence_passes(self):
        payload = _minimal_valid()
        payload["review_status"] = "implemented"
        payload["promotion_requirements"]["items"] = [
            {"key": "x", "description": "y", "satisfied": True, "evidence": "real:1"},
        ]
        assert vic.validate_payload(payload) == []


# ---------- fixture files: pass/fail as documented --------------------------

class TestFixtures:
    def test_friction_docs_example_validates(self):
        """The /friction docs candidate: target_layer=docs, no mechanism_trace needed."""
        path = REFS / "IC-FRI-workflow-orchestrator-readme.json"
        assert path.exists(), f"missing fixture: {path}"
        ok, errs = vic.validate_file(path)
        assert ok, errs

    def test_behave_validation_script_example_validates(self):
        """The /behave candidate: target_layer=validation_script requires mechanism_trace."""
        path = REFS / "IC-BEH-empty-output-hypothesis.json"
        assert path.exists(), f"missing fixture: {path}"
        ok, errs = vic.validate_file(path)
        assert ok, errs

    def test_invalid_runtime_gate_fixture_fails(self):
        """The intentionally invalid runtime_gate candidate must be rejected."""
        path = REFS / "IC-MAN-invalid-runtime-gate-no-trace.json"
        assert path.exists(), f"missing fixture: {path}"
        ok, errs = vic.validate_file(path)
        assert not ok, "expected this fixture to FAIL validation"
        joined = " ".join(errs)
        assert "mechanism_trace" in joined and "runtime_gate" in joined


# ---------- CLI exit codes --------------------------------------------------

class TestCLI:
    def test_validator_exits_nonzero_on_invalid_file(self):
        path = REFS / "IC-MAN-invalid-runtime-gate-no-trace.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_improvement_candidate.py"), "--file", str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"expected nonzero exit, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "FAIL" in result.stdout

    def test_validator_exits_zero_on_valid_file(self):
        path = REFS / "IC-FRI-workflow-orchestrator-readme.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_improvement_candidate.py"), "--file", str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"expected zero exit, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_validator_exits_nonzero_on_nonexistent_file(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_improvement_candidate.py"),
             "--file", "P:/nonexistent/IC-XX-nope.json"],
            capture_output=True, text=True,
        )
        # argparse + path check → exit 2
        assert result.returncode == 2


# ---------- schema presence (sanity) ---------------------------------------

class TestArtifacts:
    def test_schema_file_exists(self):
        assert SCHEMA.exists()

    def test_script_file_exists(self):
        assert (SCRIPTS / "validate_improvement_candidate.py").exists()

    def test_schema_is_valid_json(self):
        data = json.loads(SCHEMA.read_text(encoding="utf-8"))
        assert data["$schema"].startswith("https://json-schema.org/draft/2020-12")
        assert "ImprovementCandidate" in data["title"]