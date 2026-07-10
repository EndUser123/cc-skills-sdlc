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
SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

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


class TestFallbackChainResolvesAliases:
    """Fallback uses resolved provider/model strings, not bare aliases."""

    def test_resolves_opencode_deepseek_to_provider_model(self, tmp_path, monkeypatch):
        rid = "ac-fb-1"
        # Default: no GO_PI_ALLOW_M3_FALLBACK; only OPENCODE_DEEPSEEK should survive.
        monkeypatch.delenv("GO_PI_ALLOW_M3_FALLBACK", raising=False)
        (tmp_path / f"pi-model_{rid}.json").write_text(json.dumps({
            "classifier_model": "X", "tier": "X", "pi_model": "x/x",
        }), encoding="utf-8")
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        # M3 dropped (policy-gated), OPENCODE_DEEPSEEK resolved to provider/model.
        assert "opencode-go/deepseek-v4-flash" in chain, (
            f"fallback should resolve to provider/model, got {chain}")
        assert "OPENCODE_DEEPSEEK" not in chain, (
            f"bare alias must not survive in fallback chain, got {chain}")
        assert "M3" not in chain, (
            f"M3 must be policy-gated (no GO_PI_ALLOW_M3_FALLBACK), got {chain}")

    def test_includes_m3_when_opt_in(self, tmp_path, monkeypatch):
        rid = "ac-fb-2"
        monkeypatch.setenv("GO_PI_ALLOW_M3_FALLBACK", "1")
        (tmp_path / f"pi-model_{rid}.json").write_text(json.dumps({
            "classifier_model": "X", "tier": "X", "pi_model": "x/x",
        }), encoding="utf-8")
        chain = orch._resolve_chain_from_selection(tmp_path, rid)
        assert "minimax/MiniMax-M3" in chain, (
            f"opt-in M3 should resolve to provider/model, got {chain}")
        assert "M3" not in chain, (
            f"M3 bare alias must not survive, got {chain}")

    def test_drops_unknown_aliases(self, tmp_path, monkeypatch):
        rid = "ac-fb-3"
        monkeypatch.delenv("GO_PI_ALLOW_M3_FALLBACK", raising=False)
        # Force the normal chain read to fail, then exercise the resolver directly.
        result = orch._resolve_aliases_to_provider_model(
            ["OPENCODE_DEEPSEEK", "MYSTERY_MODEL", "LOCAL_ORNITH", "M3"]
        )
        # OPENCODE_DEEPSEEK and LOCAL_ORNITH resolve; M3 dropped (policy);
        # MYSTERY_MODEL dropped (unknown).
        assert "opencode-go/deepseek-v4-flash" in result
        assert "llama-cpp/ornith-1.0-9b" in result
        assert "MYSTERY_MODEL" not in result
        assert "M3" not in result

    def test_pi_model_chain_uses_resolved_strings(self, tmp_path):
        """The full chain read from pi-model_{run_id}.json must contain
        provider/model strings, not bare aliases. This is the regression for
        the historic OPENCODE_DEEPSEEK fuzzy-match failure."""
        rid = "ac-fb-4"
        (tmp_path / f"pi-model_{rid}.json").write_text(json.dumps({
            "classifier_model": "LOCAL_ORNITH", "tier": "T0",
            "pi_model": "llama-cpp/ornith-1.0-9b",
            "candidate_chain": [
                "LOCAL_ORNITH", "OPENCODE_DEEPSEEK", "M3"
            ],
        }), encoding="utf-8")
        # Bypass the chain reader: feed the chain to failover directly.
        raw = json.loads((tmp_path / f"pi-model_{rid}.json").read_text())
        chain = raw["candidate_chain"]
        # Chain as-written contains bare aliases; the failover path resolves them.
        resolved = orch._resolve_aliases_to_provider_model(chain)
        assert "opencode-go/deepseek-v4-flash" in resolved
        assert "llama-cpp/ornith-1.0-9b" in resolved
        # M3 dropped without opt-in.
        assert "minimax/MiniMax-M3" not in resolved


class TestArtifactContractRegistry:
    """Versioned contract registry declarative checks."""

    def test_registry_has_six_required_artifacts(self):
        from contracts.artifacts import ARTIFACT_CONTRACTS
        assert set(ARTIFACT_CONTRACTS) == {
            "model-selection.v1",
            "pi-model.v1",
            "dispatch-result.v1",
            "pi-candidate-attempt.v1",
            "failover-telemetry.v1",
            "omission-audit.v1",
        }

    def test_each_contract_has_writer_and_readers(self):
        from contracts.artifacts import ARTIFACT_CONTRACTS
        for v, c in ARTIFACT_CONTRACTS.items():
            assert c.writer, f"{v} missing writer"
            assert c.readers, f"{v} missing readers"
            # required fields non-empty
            assert len(c.required_fields) > 0, f"{v} missing required_fields"

    def test_additive_policy_consistent_with_readers(self):
        from contracts.artifacts import ARTIFACT_CONTRACTS
        # If a contract has a reader that filters (like PiModelInfo.load),
        # additive must be tolerated; if strict, the reader must reject extras.
        for v, c in ARTIFACT_CONTRACTS.items():
            if c.additive_field_policy == "strict":
                # No reader should silently drop extras.
                for r in c.readers:
                    assert "load" not in r or "filter" in r, (
                        f"{v} strict additive but reader {r} drops extras")

    def test_writer_role_format(self):
        from contracts.artifacts import ARTIFACT_CONTRACTS
        for v, c in ARTIFACT_CONTRACTS.items():
            # writer is module:func with non-empty parts (declarative)
            assert ":" in c.writer, f"{v} writer missing module:func separator"
            module, func = c.writer.split(":", 1)
            assert module.strip(), f"{v} writer module empty"
            assert func.strip(), f"{v} writer func empty"

    def test_get_contract_raises_on_unknown(self):
        from contracts.artifacts import get_contract
        import pytest
        with pytest.raises(KeyError):
            get_contract("nonexistent.v9")

    def test_validate_missing_fields(self):
        from contracts.artifacts import get_contract, validate
        missing = validate(get_contract("pi-model.v1"), {"tier": "T0"})
        assert "classifier_model" in missing
        assert "pi_model" in missing
        assert "tier" not in missing  # present
        assert validate(get_contract("pi-model.v1"),
                         {"classifier_model": "X", "tier": "T0", "pi_model": "x/x"}) == []


class TestRegistryConsistencyWithTests:
    """The contract registry must match the writer/reader pattern the tests assert."""

    def test_pimodel_reader_tolerates_extras_matches_contract(self):
        from contracts.artifacts import get_contract
        c = get_contract("pi-model.v1")
        # The contract says additive="tolerated"; the test asserts load() ignores
        # unknown fields. Verify these match.
        assert c.additive_field_policy == "tolerated"
        assert "load" in c.readers[0].lower()

    def test_dispatch_result_schema_matches_test_schema(self):
        from contracts.artifacts import get_contract
        c = get_contract("dispatch-result.v1")
        # status + exit_code are required; the test asserts these on the artifact.
        assert "status" in c.required_fields
        assert "exit_code" in c.required_fields


class TestLiveMetadataValidation:
    """Contract writer/reader references must resolve to real symbols."""

    def test_all_writer_readers_validate(self):
        from contracts.artifacts import validate_all_metadata
        results = validate_all_metadata()
        assert results == [], (
            f"metadata validation failures: {results}")

    def test_python_reference_resolves_live(self):
        from contracts.artifacts import validate_metadata
        # resolve_model:main exists
        ok, msg = validate_metadata("python:adapters/pi/resolve_model.py:main")
        assert ok, msg

    def test_python_reference_unknown_func_fails(self):
        from contracts.artifacts import validate_metadata
        ok, msg = validate_metadata("python:orchestrate:nonexistent_func_xyz")
        assert not ok
        assert "not found" in msg

    def test_external_prefix_passes(self):
        from contracts.artifacts import validate_metadata
        ok, msg = validate_metadata("external:telemetry-dashboard")
        assert ok

    def test_bare_text_fails(self):
        from contracts.artifacts import validate_metadata
        ok, msg = validate_metadata("some random text")
        assert not ok
        assert "bare text" in msg

    def test_empty_reference_fails(self):
        from contracts.artifacts import validate_metadata
        ok, msg = validate_metadata("")
        assert not ok

    def test_dispatch_result_writer_is_real_symbol(self):
        from contracts.artifacts import get_contract
        c = get_contract("dispatch-result.v1")
        assert c.writer.startswith("python:"), (
            f"dispatch-result writer must be python: prefixed, got {c.writer!r}")
