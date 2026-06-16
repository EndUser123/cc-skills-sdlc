"""Unit tests for skills/__lib/mutation_config.py."""
import json, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mutation_config as mc

VALID_GATES = {
    "version": 1,
    "default_mutation_score": 60,
    "critical_path_mutation_score": 80,
    "equivalent_mutant_threshold": 15,
    "modules": {"skill_guard.breadcrumb.inference": {"tier": "critical", "target": 80, "skip_equivalent_threshold": 15, "rationale": "test"}},
    "tool": {"name": "mutmut", "version": ">=3.0,<4", "coverage_guided": True, "runner": "pytest -x", "timeout_seconds": 300},
    "enforcement": {"block_pr_on_failure": True, "waiver_required_below_target": False, "treat_equivalent_mutants_under_threshold_as_pass": True},
}

def write_gates(tmp_path, payload):
    p = tmp_path / "quality_gates.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_load_quality_gates_happy_path(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    assert g.version == 1
    assert g.default_mutation_score == 60
    assert g.critical_path_mutation_score == 80
    assert g.equivalent_mutant_threshold == 15
    assert g.tool_name == "mutmut"
    assert g.tool_version == ">=3.0,<4"
    assert g.coverage_guided is True
    assert g.runner == "pytest -x"
    assert g.timeout_seconds == 300
    assert g.block_pr_on_failure is True
    assert g.treat_equivalent_mutants_under_threshold_as_pass is True
    assert "skill_guard.breadcrumb.inference" in g.modules
    assert g.modules["skill_guard.breadcrumb.inference"].target == 80


def test_load_quality_gates_missing_file(tmp_path):
    with pytest.raises(mc.QualityGatesError, match="not found"):
        mc.load_quality_gates(tmp_path / "absent.json")


def test_load_quality_gates_malformed_json(tmp_path):
    p = tmp_path / "quality_gates.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(mc.QualityGatesError, match="not valid JSON"):
        mc.load_quality_gates(p)


def test_load_quality_gates_version_mismatch(tmp_path):
    payload = dict(VALID_GATES, version=2)
    p = write_gates(tmp_path, payload)
    with pytest.raises(mc.QualityGatesError, match="Unsupported"):
        mc.load_quality_gates(p)


def test_load_quality_gates_missing_required_key(tmp_path):
    payload = {k: v for k, v in VALID_GATES.items() if k != "default_mutation_score"}
    p = write_gates(tmp_path, payload)
    with pytest.raises(mc.QualityGatesError, match="default_mutation_score"):
        mc.load_quality_gates(p)


def test_load_quality_gates_minimal(tmp_path):
    minimal = {
        "version": 1,
        "default_mutation_score": 50,
        "critical_path_mutation_score": 70,
        "tool": {"name": "mutmut"},
    }
    p = write_gates(tmp_path, minimal)
    g = mc.load_quality_gates(p)
    assert g.default_mutation_score == 50
    assert g.critical_path_mutation_score == 70
    assert g.equivalent_mutant_threshold == 15
    assert g.modules == {}
    assert g.tool_name == "mutmut"
    assert g.coverage_guided is True
    assert g.timeout_seconds == 600
    assert g.block_pr_on_failure is True


def test_get_target_explicit_module(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    assert g.get_target("skill_guard.breadcrumb.inference") == 80


def test_get_target_skill_guard_prefix_falls_back_to_critical(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    assert g.get_target("skill_guard.new_module") == 80


def test_get_target_unknown_module_uses_default(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    assert g.get_target("foo.bar") == 60


def test_list_critical_modules(tmp_path):
    payload = dict(VALID_GATES)
    payload["modules"] = {
        "a": {"tier": "critical", "target": 80},
        "b": {"tier": "standard", "target": 60},
        "c": {"tier": "critical", "target": 80},
    }
    p = write_gates(tmp_path, payload)
    g = mc.load_quality_gates(p)
    assert sorted(g.list_critical_modules()) == ["a", "c"]


def test_evaluate_mutation_run_no_mutants(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    res = mc.evaluate_mutation_run(
        g, "skill_guard.breadcrumb.inference",
        killed=0, survived=0, skipped=0, timeout=0, no_tests=0,
    )
    assert res["status"] == "skipped"
    assert res["score"] is None
    assert res["target"] == 80


def test_evaluate_mutation_run_pass(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    res = mc.evaluate_mutation_run(
        g, "skill_guard.breadcrumb.inference",
        killed=95, survived=5, skipped=0, timeout=0, no_tests=0,
    )
    assert res["status"] == "passed"
    assert res["score"] == 95.0
    assert res["target"] == 80


def test_evaluate_mutation_run_fail(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    res = mc.evaluate_mutation_run(
        g, "skill_guard.breadcrumb.inference",
        killed=70, survived=30, skipped=0, timeout=0, no_tests=0,
    )
    assert res["status"] == "failed"
    assert res["score"] == 70.0


def test_evaluate_mutation_run_equivalent_mutants_within_threshold(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    res = mc.evaluate_mutation_run(
        g, "skill_guard.breadcrumb.inference",
        killed=85, survived=5, skipped=10, timeout=0, no_tests=0,
    )
    assert res["status"] == "passed"
    assert res["score"] == 85.0


def test_evaluate_mutation_run_equivalent_mutants_over_threshold_treated_as_pass(tmp_path):
    p = write_gates(tmp_path, VALID_GATES)
    g = mc.load_quality_gates(p)
    res = mc.evaluate_mutation_run(
        g, "skill_guard.breadcrumb.inference",
        killed=80, survived=0, skipped=20, timeout=0, no_tests=0,
    )
    assert res["status"] == "passed"


def test_evaluate_mutation_run_equivalent_mutants_over_threshold_waived_when_flag_false(tmp_path):
    payload = dict(VALID_GATES)
    payload["enforcement"] = dict(
        VALID_GATES["enforcement"],
        treat_equivalent_mutants_under_threshold_as_pass=False,
    )
    p = write_gates(tmp_path, payload)
    g = mc.load_quality_gates(p)
    res = mc.evaluate_mutation_run(
        g, "skill_guard.breadcrumb.inference",
        killed=80, survived=0, skipped=20, timeout=0, no_tests=0,
    )
    assert res["status"] == "waived"


def test_apply_equivalent_threshold_caps_skipped():
    assert mc._apply_equivalent_threshold(20, 100, 15) == 15
    assert mc._apply_equivalent_threshold(10, 100, 15) == 10
    assert mc._apply_equivalent_threshold(0, 100, 15) == 0
    assert mc._apply_equivalent_threshold(50, 50, 15) == 7
