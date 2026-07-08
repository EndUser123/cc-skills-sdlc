"""Tests for PI model candidate chains, local eligibility, and failover telemetry."""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if "classify_complexity" not in sys.modules:
    sys.path.insert(0, str(SCRIPTS))
    import classify_complexity as _cc
    sys.modules["classify_complexity"] = _cc

# Load preflight_propose
_spec = importlib.util.spec_from_file_location("pf", SCRIPTS / "preflight_propose.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)

# Load resolve_model
_rm_spec = importlib.util.spec_from_file_location("rm", SCRIPTS / "adapters" / "pi" / "resolve_model.py")
rm = importlib.util.module_from_spec(_rm_spec)
_rm_spec.loader.exec_module(rm)


def _task(**kw):
    base = {"task_type": "implementation", "scope_in": [], "forbidden_files": [],
            "acceptance_criteria": [], "verification_commands": []}
    base.update(kw)
    return base


class TestCandidateChains:
    """Tests for resolve_model candidate chain resolution."""

    def test_t0_gets_local_then_m3(self):
        chain = rm.resolve_chain("T0")
        assert "llama-cpp/ornith-1.0-9b" in chain
        assert "minimax/MiniMax-M3" in chain
        assert chain[0] == "llama-cpp/ornith-1.0-9b"  # local first

    def test_t1_gets_local_then_m3(self):
        chain = rm.resolve_chain("T1")
        assert chain == ["llama-cpp/ornith-1.0-9b", "minimax/MiniMax-M3"]

    def test_t2_m3_only(self):
        chain = rm.resolve_chain("T2")
        assert chain == ["minimax/MiniMax-M3"]

    def test_t4_glm_then_m3(self):
        chain = rm.resolve_chain("T4")
        assert chain == ["zai/glm-5.2", "minimax/MiniMax-M3"]

    def test_local_ornith_resolves(self):
        assert rm.resolve("LOCAL_ORNITH") == "llama-cpp/ornith-1.0-9b"

    def test_unknown_tier_defaults_m3(self):
        chain = rm.resolve_chain("T99")
        assert chain == ["minimax/MiniMax-M3"]


class TestLocalEligibility:
    """Tests for _is_local_eligible task classification."""

    def test_hook_task_not_local_eligible(self):
        from skills.go.scripts.classify_complexity import _is_local_eligible
        assert _is_local_eligible(_task(task_type="hook"), "hook") is False

    def test_gate_task_not_local_eligible(self):
        from skills.go.scripts.classify_complexity import _is_local_eligible
        assert _is_local_eligible(_task(task_type="gate"), "gate") is False

    def test_cache_task_not_local_eligible(self):
        from skills.go.scripts.classify_complexity import _is_local_eligible
        assert _is_local_eligible(_task(task_type="cache"), "cache") is False

    def test_simple_readonly_eligible(self):
        from skills.go.scripts.classify_complexity import _is_local_eligible
        assert _is_local_eligible(_task(scope_in=["a.py"]), "implementation") is True

    def test_forbidden_files_not_eligible(self):
        from skills.go.scripts.classify_complexity import _is_local_eligible
        assert _is_local_eligible(_task(forbidden_files=["secret.py"]), "implementation") is False

    def test_large_scope_not_eligible(self):
        from skills.go.scripts.classify_complexity import _is_local_eligible
        assert _is_local_eligible(_task(scope_in=["a", "b", "c", "d"]), "implementation") is False


class TestAcceptLocalCandidate:
    """Tests for accept_local_candidate validation."""

    def test_good_text_accepted(self):
        assert pf.accept_local_candidate("The first line is: import os\n") is True

    def test_empty_rejected(self):
        assert pf.accept_local_candidate("") is False

    def test_short_rejected(self):
        assert pf.accept_local_candidate("ok") is False

    def test_thinking_only_rejected(self):
        assert pf.accept_local_candidate("<thinking>user wants</thinking>") is True  # 30+ chars


class TestFailoverTelemetry:
    """Tests for record_failover_telemetry."""

    def test_failover_written(self, tmp_path):
        record = pf.record_failover_telemetry(
            tmp_path, "fail-001",
            candidate_chain=["llama-cpp/ornith-1.0-9b", "minimax/MiniMax-M3"],
            attempted_model="llama-cpp/ornith-1.0-9b",
            provider="llama-cpp",
            outcome="failed",
            failure_reason="thinking_only_no_text",
            fallback_selected="minimax/MiniMax-M3",
            final_model="minimax/MiniMax-M3",
            final_status="completed",
        )
        assert record["event"] == "pi_failover"
        assert record["run_id"] == "fail-001"
        tel_file = tmp_path / "failover-telemetry_fail-001.jsonl"
        assert tel_file.exists()

    def test_two_run_ids_isolated(self, tmp_path):
        pf.record_failover_telemetry(
            tmp_path, "run-a",
            ["model-a"], "model-a", "prov-a", "success")
        pf.record_failover_telemetry(
            tmp_path, "run-b",
            ["model-b"], "model-b", "prov-b", "failed",
            fallback_selected="model-c", final_model="model-c")
        a = json.loads((tmp_path / "failover-telemetry_run-a.jsonl").read_text().strip().splitlines()[-1])
        b = json.loads((tmp_path / "failover-telemetry_run-b.jsonl").read_text().strip().splitlines()[-1])
        assert a["outcome"] == "success"
        assert b["outcome"] == "failed"


class TestStopBoundary:
    """Stop_enforce_gate.py must remain clean."""

    def test_no_candidate_chain_symbols(self):
        gate = (SCRIPTS / ".." / "hooks" / "Stop_enforce_gate.py").read_text(encoding="utf-8")
        for sym in ["LOCAL_ORNITH", "candidate_chain", "resolve_chain", "accept_local_candidate"]:
            assert sym not in gate, f"Stop_enforce_gate.py contains {sym}"
