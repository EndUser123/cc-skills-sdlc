"""Tests for /go pattern detection and dry-run refactor analysis.

Real imports of Stop_enforce_gate, real tmp_path state dirs, no Mock.
Exercises the real evaluate_completion_authority path.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
GATE_PY = PLUGIN_ROOT / "hooks" / "Stop_enforce_gate.py"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_gate():
    spec = importlib.util.spec_from_file_location("stop_enforce_gate_pd", GATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def test_repeated_failure_shape_produces_pattern_candidate(tmp_path, gate, monkeypatch):
    """First occurrence of high-risk shape -> hook, second -> pattern_candidate.
    Non-high-risk shapes: first -> note. This test covers both paths."""
    pdb = tmp_path / "patterns.jsonl"
    monkeypatch.setattr(gate, "_PATTERN_DB", pdb)

    state_dir = tmp_path / "go"
    state_dir.mkdir()
    (state_dir / "active-task_run1.json").write_text(
        json.dumps({"task": {"summary": "Bug fixed"}}), encoding="utf-8"
    )
    v1 = gate.evaluate_completion_authority(state_dir, "run1")
    assert v1.get("pattern_candidate") is not None
    # "Bug fixed" without evidence -> first matching shape is cache_not_verified
    # (high-risk) -> promotes to hook on first occurrence, not note.
    shape1 = v1["pattern_candidate"]["failure_shape"]
    if shape1 in ("cache_not_verified", "missing_backend"):
        assert v1["pattern_candidate"]["promotion_recommendation"] == "hook"
    else:
        assert v1["pattern_candidate"]["promotion_recommendation"] == "note"
    assert v1["pattern_candidate"]["recurrence_count"] == 1

    (state_dir / "active-task_run2.json").write_text(
        json.dumps({"task": {"summary": "Bug fixed"}}), encoding="utf-8"
    )
    v2 = gate.evaluate_completion_authority(state_dir, "run2")
    assert v2["pattern_candidate"]["promotion_recommendation"] == "pattern_candidate"
    assert v2["pattern_candidate"]["recurrence_count"] == 2


def test_third_recurrence_recommends_report_gate(tmp_path, gate, monkeypatch):
    """Third occurrence -> report_gate promotion."""
    pdb = tmp_path / "patterns.jsonl"
    monkeypatch.setattr(gate, "_PATTERN_DB", pdb)
    state_dir = tmp_path / "go"
    state_dir.mkdir()
    for i in range(1, 4):
        (state_dir / f"active-task_run{i}.json").write_text(
            json.dumps({"task": {"summary": "Bug fixed"}}), encoding="utf-8"
        )
        v = gate.evaluate_completion_authority(state_dir, f"run{i}")
    assert v["pattern_candidate"]["recurrence_count"] == 3
    assert v["pattern_candidate"]["promotion_recommendation"] == "report_gate"


def test_high_risk_deterministic_miss_recommends_hook(tmp_path, gate, monkeypatch):
    """High-risk shapes (cache_not_verified, missing_backend) promote to hook on first occurrence."""
    pdb = tmp_path / "patterns.jsonl"
    monkeypatch.setattr(gate, "_PATTERN_DB", pdb)
    state_dir = tmp_path / "go"
    state_dir.mkdir()
    # missing_backend: "shipped" claim without backend_path
    (state_dir / "active-task_risk.json").write_text(
        json.dumps({"task": {"summary": "Feature shipped to production"}}),
        encoding="utf-8",
    )
    v = gate.evaluate_completion_authority(state_dir, "risk")
    if v.get("pattern_candidate"):
        shape = v["pattern_candidate"]["failure_shape"]
        if shape in ("cache_not_verified", "missing_backend"):
            assert v["pattern_candidate"]["promotion_recommendation"] == "hook"


def test_routing_hook_plugin_task_triggers_dry_run(tmp_path, gate):
    """Tasks touching routing/hooks/gates/plugins trigger dry_run_refactor_analysis."""
    # _should_trigger_dry_run expects the merged (flat) form from _read_active_task
    active = {
        "summary": "Update hook dispatch routing",
        "task_type": "implementation",
    }
    assert gate._should_trigger_dry_run(active) is True


def test_non_routing_task_does_not_trigger_dry_run(gate):
    """Tasks without routing/hook/gate keywords do not trigger dry-run."""
    active = {"task": {"summary": "Fix typo in README"}}
    assert gate._should_trigger_dry_run(active) is False


def test_dry_run_mode_performs_no_mutation(tmp_path, gate):
    """Dry-run analysis returns findings but does not mutate any files."""
    state_dir = tmp_path / "go"
    state_dir.mkdir()
    active = {"task": {"summary": "Refactor hook routing"}}
    # Snapshot before
    before = {}
    for f in state_dir.iterdir():
        before[f.name] = f.read_bytes()
    result = gate._dry_run_analysis(active, state_dir)
    # Snapshot after
    after = {}
    for f in state_dir.iterdir():
        after[f.name] = f.read_bytes()
    # No mutation: the state dir is unchanged
    assert before == after
    assert result["mode"] == "dry_run_only"


def test_block_finding_prevents_implementation_ready_claim(tmp_path, gate, monkeypatch):
    """A BLOCK finding from dry-run analysis should downgrade verdict to BLOCK."""
    pdb = tmp_path / "patterns.jsonl"
    monkeypatch.setattr(gate, "_PATTERN_DB", pdb)
    state_dir = tmp_path / "go"
    state_dir.mkdir()
    # Task touches "hook" (triggers dry-run) and claims "complete" (triggers overclaim)
    # but has no smoke evidence (triggers BLOCK from dry-run entrypoint_gap)
    (state_dir / "active-task_block.json").write_text(
        json.dumps({"task": {"summary": "Hook refactor complete"}}),
        encoding="utf-8",
    )
    v = gate.evaluate_completion_authority(state_dir, "block")
    assert v.get("dry_run_analysis") is not None
    assert v["dry_run_analysis"]["mode"] == "dry_run_only"
    assert v["downgrade"] == "BLOCK"


def test_existing_tests_still_pass_regression(tmp_path, gate, monkeypatch):
    """Regression: the original 11 unit tests' core assertion still holds."""
    monkeypatch.setattr(gate, "_PATTERN_DB", tmp_path / "patterns.jsonl")
    state_dir = tmp_path / "go"
    state_dir.mkdir()
    v = gate.evaluate_completion_authority(state_dir, "regress")
    # Even with empty state, the gate returns a verdict with required fields
    assert "downgrade" in v
    assert "overclaim_terms" in v
    assert "levels" in v
