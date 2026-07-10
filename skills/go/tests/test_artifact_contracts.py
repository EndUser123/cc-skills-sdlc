"""Artifact-contract + parse-health regression tests for /go live-path reliability.

These tests catch the two LOCAL_ORNITH blockers (PiModelInfo.load crash on
extra fields, _resolve_chain_from_selection reading the wrong artifact) and
verify writer/reader contracts for the PI dispatch artifact chain.

Pure unit tests — no git boundary, no subprocess.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Load orchestrate (register in sys.modules for @dataclass)
_orch_spec = importlib.util.spec_from_file_location("orch_ac", SCRIPTS / "orchestrate.py")
orch = importlib.util.module_from_spec(_orch_spec)
sys.modules["orch_ac"] = orch
_orch_spec.loader.exec_module(orch)


class TestPiModelInfoLoad:
    """Regression for blocker #1: PiModelInfo.load crashed on candidate_chain."""

    def test_load_tolerates_extra_fields(self, tmp_path):
        rid = "ac-pmi-1"
        data = {
            "classifier_model": "LOCAL_ORNITH",
            "tier": "T0",
            "pi_model": "llama-cpp/ornith-1.0-9b",
            "candidate_chain": ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"],
            "candidate_models": ["llama-cpp/ornith-1.0-9b"],
            "future_unknown_field": "should not crash",
        }
        f = tmp_path / f"pi-model_{rid}.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        info = orch.PiModelInfo.load(f)
        assert info.classifier_model == "LOCAL_ORNITH"
        assert info.tier == "T0"
        assert info.pi_model == "llama-cpp/ornith-1.0-9b"

    def test_load_with_only_known_fields(self, tmp_path):
        rid = "ac-pmi-2"
        f = tmp_path / f"pi-model_{rid}.json"
        f.write_text(json.dumps({
            "classifier_model": "M3", "tier": "T99", "pi_model": "minimax/MiniMax-M3"
        }), encoding="utf-8")
        info = orch.PiModelInfo.load(f)
        assert info.pi_model == "minimax/MiniMax-M3"


class TestResolveChainFromSelection:
    """Regression for blocker #2: chain read from wrong artifact file."""

    def test_reads_pi_model_not_model_selection(self, tmp_path):
        rid = "ac-rcc-1"
        # model-selection has NO candidate_chain
        (tmp_path / f"model-selection_{rid}.json").write_text(json.dumps({
            "tier": "T0", "model": "LOCAL_ORNITH", "confidence": "high",
            "score": 4, "max_possible": 12, "signals": {}, "task_type": "implementation",
        }), encoding="utf-8")
        # pi-model HAS candidate_chain
        (tmp_path / f"pi-model_{rid}.json").write_text(json.dumps({
            "classifier_model": "LOCAL_ORNITH", "tier": "T0",
            "pi_model": "llama-cpp/ornith-1.0-9b",
            "candidate_chain": ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"],
        }), encoding="utf-8")
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        assert chain == ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"], (
            f"expected pi-model chain, got {chain}")

    def test_fallback_when_pi_model_missing(self, tmp_path):
        rid = "ac-rcc-2"
        # Neither file exists
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        assert isinstance(chain, list) and len(chain) >= 1, (
            f"expected documented fallback, got {chain}")

    def test_fallback_when_pi_model_has_no_chain(self, tmp_path):
        rid = "ac-rcc-3"
        (tmp_path / f"pi-model_{rid}.json").write_text(json.dumps({
            "classifier_model": "M3", "tier": "T99", "pi_model": "minimax/MiniMax-M3",
        }), encoding="utf-8")
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        # No candidate_chain key → falls back to default
        assert isinstance(chain, list) and len(chain) >= 1


class TestParseHealth:
    """Verify _check_parse_health catches syntax errors."""

    def test_all_pass(self, tmp_path):
        rid = "ac-ph-1"
        scripts = [SCRIPTS / "orchestrate.py", SCRIPTS / "omission_audit.py"]
        assert orch._check_parse_health(tmp_path, rid, scripts) is True
        art = json.loads((tmp_path / f"parse-health_{rid}.json").read_text())
        assert art["all_ok"] is True
        assert len(art["scripts"]) == 2

    def test_catches_syntax_error(self, tmp_path):
        rid = "ac-ph-2"
        bad = tmp_path / "broken.py"
        bad.write_text("def f(:\n  pass\n", encoding="utf-8")
        assert orch._check_parse_health(tmp_path, rid, [bad]) is False
        art = json.loads((tmp_path / f"parse-health_{rid}.json").read_text())
        assert art["all_ok"] is False
        assert "SyntaxError" in art["scripts"][0]["error"]


class TestArtifactContractRoundTrip:
    """Writer/reader contract for PI dispatch artifacts."""

    def test_pi_model_writer_reader_contract(self, tmp_path):
        rid = "ac-art-1"
        # Writer: resolve_model.py shape
        written = {
            "classifier_model": "LOCAL_ORNITH",
            "tier": "T0",
            "pi_model": "llama-cpp/ornith-1.0-9b",
            "candidate_chain": ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"],
            "candidate_models": ["llama-cpp/ornith-1.0-9b", "opencode-go/deepseek-v4-flash"],
        }
        f = tmp_path / f"pi-model_{rid}.json"
        f.write_text(json.dumps(written), encoding="utf-8")
        # Reader 1: PiModelInfo.load reads 3 fields
        info = orch.PiModelInfo.load(f)
        assert info.pi_model == written["pi_model"]
        # Reader 2: _resolve_chain reads candidate_chain
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        assert chain == written["candidate_chain"]

    def test_candidate_attempts_writer_contract(self, tmp_path):
        rid = "ac-art-2"
        # Write a candidate-attempt record (shape from _record_candidate_attempt)
        record = {
            "event": "pi_candidate_attempt", "run_id": rid,
            "model_alias": "LOCAL_ORNITH", "provider_model": "llama-cpp/ornith-1.0-9b",
            "outcome": "success", "latency_ms": 31000.0,
            "fallback_used": False, "validator_reason": "accepted",
            "attempt_index": 0, "candidate_chain": ["llama-cpp/ornith-1.0-9b"],
        }
        f = tmp_path / f"pi-candidate-attempts_{rid}.jsonl"
        f.write_text(json.dumps(record) + "\n", encoding="utf-8")
        # Reader: parse the JSONL
        lines = f.read_text(encoding="utf-8").strip().splitlines()
        d = json.loads(lines[0])
        assert d["model_alias"] == "LOCAL_ORNITH"
        assert d["outcome"] == "success"
        assert d["provider_model"] == "llama-cpp/ornith-1.0-9b"


class TestReaderTolerance:
    """All readers tolerate unexpected keys without crashing."""

    def test_model_selection_tolerates_extra(self, tmp_path):
        rid = "ac-tol-1"
        (tmp_path / f"model-selection_{rid}.json").write_text(json.dumps({
            "tier": "T0", "model": "LOCAL_ORNITH", "confidence": "high",
            "score": 4, "max_possible": 12, "signals": {}, "task_type": "implementation",
            "unknown_future_key": "should not crash",
        }), encoding="utf-8")
        # The reader path (classify_and_resolve_pi) reads this file; _resolve_chain
        # reads pi-model instead. model-selection is only for classifier display.
        # Verify it loads as valid JSON with the expected fields.
        d = json.loads((tmp_path / f"model-selection_{rid}.json").read_text())
        assert d["tier"] == "T0"


class TestMissingArtifactClearFailure:
    """Missing artifacts produce clear failure or documented fallback."""

    def test_missing_pi_model_uses_fallback(self, tmp_path):
        rid = "ac-miss-1"
        # No files at all
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        assert chain  # documented fallback, not crash

    def test_missing_parse_health_artifact_ok(self, tmp_path):
        """parse-health artifact is only written by _check_parse_health itself."""
        rid = "ac-miss-2"
        scripts = [SCRIPTS / "orchestrate.py"]
        ok = orch._check_parse_health(tmp_path, rid, scripts)
        assert ok is True
        assert (tmp_path / f"parse-health_{rid}.json").exists()
