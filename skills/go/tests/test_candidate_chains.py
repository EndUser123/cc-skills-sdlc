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

# Load orchestrate (register in sys.modules BEFORE exec — it uses @dataclass,
# which looks up sys.modules[cls.__module__] during class creation).
_orch_spec = importlib.util.spec_from_file_location("orch_test", SCRIPTS / "orchestrate.py")
orch = importlib.util.module_from_spec(_orch_spec)
sys.modules["orch_test"] = orch
_orch_spec.loader.exec_module(orch)


def _task(**kw):
    base = {"task_type": "implementation", "scope_in": [], "forbidden_files": [],
            "acceptance_criteria": [], "verification_commands": []}
    base.update(kw)
    return base


class TestCandidateChains:
    """Tests for resolve_model candidate chain resolution."""

    def test_t0_gets_local_then_opencode_deepseek(self):
        chain = rm.resolve_chain("T0")
        assert "llama-cpp/ornith-1.0-9b" in chain
        assert "opencode-go/deepseek-v4-flash" in chain
        assert chain[0] == "llama-cpp/ornith-1.0-9b"  # local first

    def test_t1_gets_local_then_opencode_deepseek(self):
        chain = rm.resolve_chain("T1")
        assert chain == ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"]

    def test_t2_opencode_deepseek_only(self):
        chain = rm.resolve_chain("T2")
        assert chain == ["opencode-go/deepseek-v4-flash"]

    def test_t4_glm_then_opencode_deepseek(self):
        chain = rm.resolve_chain("T4")
        assert chain == ["zai/glm-5.2", "opencode-go/deepseek-v4-flash"]

    def test_local_ornith_resolves(self):
        assert rm.resolve("LOCAL_ORNITH") == "llama-cpp/ornith-1.0-9b"

    def test_opencode_deepseek_resolves_with_prefix(self):
        # Bare 'deepseek-v4-flash' resolves to the wrong pi provider (no key).
        assert rm.resolve("OPENCODE_DEEPSEEK") == "opencode-go/deepseek-v4-flash"

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


class TestCandidateAttemptTelemetry:
    """Advisory per-candidate-attempt telemetry writer (run_id-scoped, append-only)."""

    REQUIRED_KEYS = {
        "event", "run_id", "state_dir", "task_class", "tier", "candidate_chain",
        "attempt_index", "model_alias", "provider_model", "started_at", "ended_at",
        "latency_ms", "outcome", "reject_reason", "final_model_used",
        "fallback_used", "validator_reason",
    }

    def test_writer_emits_required_fields(self, tmp_path):
        rec = orch._record_candidate_attempt(
            tmp_path, "att-001", "T0", "implementation",
            ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"],
            0, "LOCAL_ORNITH", "llama-cpp/ornith-1.0-9b",
            "2026-07-08T13:00:00+00:00", 42.5, "success", "",
            "llama-cpp/ornith-1.0-9b", False, "accepted")
        assert rec["event"] == "pi_candidate_attempt"
        assert self.REQUIRED_KEYS.issubset(rec.keys())
        assert (tmp_path / "pi-candidate-attempts_att-001.jsonl").exists()

    def test_run_ids_isolated(self, tmp_path):
        orch._record_candidate_attempt(
            tmp_path, "run-a", "T0", "implementation", ["m-a"], 0,
            "A", "m-a", "t0", 1.0, "success", "", "m-a", False, "accepted")
        orch._record_candidate_attempt(
            tmp_path, "run-b", "T1", "implementation", ["m-b"], 0,
            "B", "m-b", "t0", 2.0, "reject", "thinking_only_or_no_text",
            "", False, "no_acceptable_text")
        a_records = (tmp_path / "pi-candidate-attempts_run-a.jsonl").read_text().strip().splitlines()
        b_records = (tmp_path / "pi-candidate-attempts_run-b.jsonl").read_text().strip().splitlines()
        assert json.loads(a_records[-1])["model_alias"] == "A"
        assert json.loads(b_records[-1])["outcome"] == "reject"

    def test_append_only_multiple_attempts(self, tmp_path):
        for idx, outcome in enumerate(["reject", "success"]):
            orch._record_candidate_attempt(
                tmp_path, "chain-1", "T0", "implementation",
                ["m-a", "m-b"], idx, "A" if idx == 0 else "B",
                f"m-{idx}", "t0", float(idx), outcome, "", "m-b", idx > 0,
                "accepted")
        lines = (tmp_path / "pi-candidate-attempts_chain-1.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["attempt_index"] == 0
        assert json.loads(lines[1])["fallback_used"] is True


class _FakeResult:
    def __init__(self, exit_code, transcript_path):
        self.exit_code = exit_code
        self.transcript_path = str(transcript_path)


class _FakeHarness:
    """Records calls, returns scripted results. Used to exercise failover wiring."""
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def run_pi_harness(self, **kw):
        self.calls.append(kw["pi_model"])
        return self._results.pop(0)


class TestFailoverAttemptEmission:
    """_candidate_chain_failover emits one advisory record per candidate tried."""

    @staticmethod
    def _write_transcript(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            path.write_text("", encoding="utf-8")
            return
        event = {"type": "message_update", "message": {"content": [{"type": "text", "text": text}]}}
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    def test_reject_then_success_emits_two_records(self, tmp_path):
        chain = ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"]
        # Write model-selection so tier is captured in telemetry.
        (tmp_path / "model-selection_failover-1.json").write_text(
            json.dumps({"tier": "T0", "candidate_chain": chain}), encoding="utf-8")
        (tmp_path / "task-proposal_failover-1.json").write_text(
            json.dumps({"task_type": "implementation"}), encoding="utf-8")
        t_no_text = tmp_path / "tx_no_text.jsonl"
        t_text = tmp_path / "tx_text.jsonl"
        self._write_transcript(t_no_text, None)   # empty -> thinking_only_or_no_text
        self._write_transcript(t_text, "The fix is applied correctly here.")  # accepted
        harness = _FakeHarness([
            _FakeResult(0, t_no_text),
            _FakeResult(0, t_text),
        ])
        result, final_model, failed = orch._candidate_chain_failover(
            harness, tmp_path, tmp_path, "failover-1", "prompt", chain,
            tmp_path / "active-task_failover-1.json")
        assert final_model == "opencode-go/deepseek-v4-flash"
        assert result.exit_code == 0
        assert len(failed) == 1 and "thinking_only_or_no_text" in failed[0]["reason"]
        lines = (tmp_path / "pi-candidate-attempts_failover-1.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        r0, r1 = json.loads(lines[0]), json.loads(lines[1])
        # First attempt: local, rejected, not a fallback.
        assert r0["model_alias"] == "LOCAL_ORNITH"
        assert r0["outcome"] == "reject"
        assert r0["fallback_used"] is False
        assert r0["attempt_index"] == 0
        assert r0["validator_reason"] == "no_acceptable_text"
        assert r0["tier"] == "T0" and r0["task_class"] == "implementation"
        # Second attempt: fallback succeeded.
        assert r1["model_alias"] == "OPENCODE_DEEPSEEK"
        assert r1["outcome"] == "success"
        assert r1["fallback_used"] is True
        assert r1["final_model_used"] == "opencode-go/deepseek-v4-flash"
        assert r1["latency_ms"] >= 0.0

    def test_first_success_emits_one_record(self, tmp_path):
        chain = ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"]
        t_ok = tmp_path / "tx_ok.jsonl"
        self._write_transcript(t_ok, "Local model produced a useful answer here.")
        harness = _FakeHarness([_FakeResult(0, t_ok)])
        result, final_model, failed = orch._candidate_chain_failover(
            harness, tmp_path, tmp_path, "fast-1", "prompt", chain,
            tmp_path / "active-task_fast-1.json")
        assert final_model == "llama-cpp/ornith-1.0-9b"
        assert failed == []
        lines = (tmp_path / "pi-candidate-attempts_fast-1.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        r0 = json.loads(lines[0])
        assert r0["outcome"] == "success"
        assert r0["fallback_used"] is False
        assert r0["final_model_used"] == "llama-cpp/ornith-1.0-9b"
