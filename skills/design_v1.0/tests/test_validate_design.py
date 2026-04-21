"""Tests for schemas.py and validate_design.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
VALIDATE_SCRIPT = SKILL_DIR / "validate_design.py"


def _state_dir() -> Path:
    return SKILL_DIR.parent.parent / ".claude" / "arch_decisions"


def _flag_path(run_id: str) -> Path:
    return _state_dir() / f".verified_{run_id}"


def _attempt_path(run_id: str) -> Path:
    return _state_dir() / f".attempt_{run_id}"


def _minimal_payload(**overrides) -> dict:
    """Build a valid minimal DesignPayload dict."""
    data = {
        "run_id": "test-run-001",
        "mode": "system",
        "scope": "all",
        "user_query": "test query",
        "ast_summary": "file.py: classes=[Foo], funcs=[bar]",
        "sop": "MODE=system, SCOPE=all, DOMAIN=general",
        "template_name": "system_precedent_deep",
        "cap": {
            "boundaries": [
                {
                    "boundary_id": "b1",
                    "producer": "module_a",
                    "consumer": "module_b",
                    "input_schema_id": "s1",
                    "output_schema_id": "s2",
                }
            ]
        },
        "critic_findings": [
            {"severity": "low", "category": "style", "description": "minor style issue"}
        ],
        "adr_markdown": "# ADR: Test Decision\n\nThis is a complete architecture decision record with enough content to pass validation.",
        "claim_verification": [
            {"claim": "Module A exists", "evidence": "Verified module_a.py at line 42", "verified": True}
        ],
        "domain": "general",
    }
    data.update(overrides)
    return data


def _write_draft(payload: dict, tmpdir: Path) -> Path:
    path = tmpdir / "design_draft_test-run.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_validate(draft_path: str, mode: str, run_id: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["python", str(VALIDATE_SCRIPT), str(draft_path), mode, run_id],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestDesignPayloadSchema:
    def test_minimal_payload_roundtrip(self):
        from schemas import DesignPayload

        data = _minimal_payload()
        payload = DesignPayload.from_dict(data)
        assert payload.run_id == "test-run-001"
        assert payload.mode == "system"
        assert payload.domain == "general"
        assert len(payload.claim_verification) == 1
        assert payload.claim_verification[0].claim == "Module A exists"

        exported = payload.to_dict()
        assert exported["run_id"] == "test-run-001"
        assert exported["domain"] == "general"

    def test_from_dict_missing_required_field(self):
        from schemas import DesignPayload

        with pytest.raises(KeyError):
            DesignPayload.from_dict({"mode": "system"})

    def test_bottleneck_evidence_roundtrip(self):
        from schemas import DesignPayload

        data = _minimal_payload(
            domain="performance",
            bottleneck_evidence={
                "measurement_basis": "sleep constants in main.py",
                "primary_path": "yt-dlp WEB client",
                "fallback_positions": {"web_client": 1, "api_fallback": 2},
                "timing_constants": {"sleep_interval": 15, "cooldown": 300},
                "estimated_reach_pct": 0.85,
            },
        )
        payload = DesignPayload.from_dict(data)
        assert payload.bottleneck_evidence is not None
        assert payload.bottleneck_evidence.primary_path == "yt-dlp WEB client"
        assert payload.bottleneck_evidence.fallback_positions == {"web_client": 1, "api_fallback": 2}

        exported = payload.to_dict()
        assert "bottleneck_evidence" in exported
        assert exported["bottleneck_evidence"]["estimated_reach_pct"] == 0.85

    def test_bottleneck_none_not_in_export(self):
        from schemas import DesignPayload

        data = _minimal_payload()
        payload = DesignPayload.from_dict(data)
        assert payload.bottleneck_evidence is None
        exported = payload.to_dict()
        assert "bottleneck_evidence" not in exported

    def test_critic_finding_severity_enum(self):
        from schemas import DesignPayload

        data = _minimal_payload(
            critic_findings=[
                {"severity": "critical", "category": "safety", "description": "data leak"},
                {"severity": "medium", "category": "performance", "description": "slow query"},
            ]
        )
        payload = DesignPayload.from_dict(data)
        assert len(payload.critic_findings) == 2
        assert payload.critic_findings[0].severity.value == "critical"

    def test_cap_boundaries(self):
        from schemas import DesignPayload

        data = _minimal_payload(
            cap={
                "identity_model": "uuid",
                "boundaries": [
                    {
                        "boundary_id": "api-edge",
                        "producer": "gateway",
                        "consumer": "backend",
                        "input_schema_id": "req-v1",
                        "output_schema_id": "resp-v1",
                        "required_fields": ["user_id", "action"],
                    }
                ]
            }
        )
        payload = DesignPayload.from_dict(data)
        assert payload.cap.identity_model == "uuid"
        assert len(payload.cap.boundaries) == 1
        assert payload.cap.boundaries[0].required_fields == ["user_id", "action"]


class TestValidateLogic:
    """Tests for _validate_logic business rules."""

    def _validate(self, **overrides) -> list[str]:
        from schemas import DesignPayload
        from validate_design import _validate_logic

        data = _minimal_payload(**overrides)
        payload = DesignPayload.from_dict(data)
        return _validate_logic(payload)

    def test_valid_payload_no_errors(self):
        errors = self._validate()
        assert errors == []

    def test_rejects_empty_run_id(self):
        errors = self._validate(run_id="")
        assert any("run_id" in e for e in errors)

    def test_rejects_bad_mode(self):
        errors = self._validate(mode="invalid")
        assert any("mode" in e for e in errors)

    def test_rejects_bad_scope(self):
        errors = self._validate(scope="invalid")
        assert any("scope" in e for e in errors)

    def test_rejects_empty_ast_summary(self):
        errors = self._validate(ast_summary="")
        assert any("ast_summary" in e for e in errors)

    def test_rejects_short_adr(self):
        errors = self._validate(adr_markdown="too short")
        assert any("too short" in e for e in errors)

    def test_rejects_missing_critic_findings(self):
        errors = self._validate(critic_findings=[])
        assert any("critic_findings" in e for e in errors)

    def test_rejects_missing_claim_verification(self):
        errors = self._validate(claim_verification=[])
        assert any("claim_verification" in e for e in errors)

    def test_rejects_claim_without_evidence(self):
        errors = self._validate(
            claim_verification=[
                {"claim": "Something exists", "evidence": "", "verified": False}
            ]
        )
        assert any("missing evidence" in e for e in errors)

    def test_rejects_unverified_claim_with_counterexample(self):
        errors = self._validate(
            claim_verification=[
                {
                    "claim": "X handles errors",
                    "evidence": "read file.py",
                    "verified": False,
                    "counterexample": "line 42 has no try/except",
                }
            ]
        )
        assert any("counterexample" in e for e in errors)

    def test_performance_domain_requires_bottleneck(self):
        errors = self._validate(domain="performance", bottleneck_evidence=None)
        assert any("bottleneck_evidence" in e for e in errors)

    def test_performance_domain_bottleneck_missing_fields(self):
        errors = self._validate(
            domain="performance",
            bottleneck_evidence={
                "measurement_basis": "",
                "primary_path": "",
                "fallback_positions": {},
                "timing_constants": {},
            },
        )
        assert any("measurement_basis" in e for e in errors)
        assert any("primary_path" in e for e in errors)
        assert any("fallback_positions" in e for e in errors)

    def test_boundary_missing_producer(self):
        errors = self._validate(
            cap={
                "boundaries": [
                    {
                        "boundary_id": "b1",
                        "producer": "",
                        "consumer": "module_b",
                        "input_schema_id": "s1",
                        "output_schema_id": "s2",
                    }
                ]
            }
        )
        assert any("missing producer" in e for e in errors)

    def test_boundary_missing_consumer(self):
        errors = self._validate(
            cap={
                "boundaries": [
                    {
                        "boundary_id": "b1",
                        "producer": "module_a",
                        "consumer": "",
                        "input_schema_id": "s1",
                        "output_schema_id": "s2",
                    }
                ]
            }
        )
        assert any("missing consumer" in e for e in errors)


class TestValidateDesignScript:
    """Integration tests running validate_design.py as subprocess."""

    def test_valid_payload_succeeds(self, tmp_path):
        run_id = f"val-test-{time.time_ns()}"
        try:
            payload = _minimal_payload(run_id=run_id)
            draft = _write_draft(payload, tmp_path)

            exit_code, stdout, stderr = _run_validate(str(draft), "system", run_id)
            assert exit_code == 0, f"Validation failed: {stderr}"
            assert "SUCCESS" in stdout

            # Flag file should exist
            assert _flag_path(run_id).exists()
        finally:
            for p in (_flag_path(run_id), _attempt_path(run_id)):
                if p.exists():
                    p.unlink()

    def test_invalid_payload_fails(self, tmp_path):
        run_id = f"val-fail-{time.time_ns()}"
        try:
            payload = _minimal_payload(run_id=run_id, adr_markdown="too short")
            draft = _write_draft(payload, tmp_path)

            exit_code, stdout, stderr = _run_validate(str(draft), "system", run_id)
            assert exit_code != 0
            assert "too short" in stderr

            # Attempt counter should be incremented
            assert _attempt_path(run_id).exists()
        finally:
            for p in (_flag_path(run_id), _attempt_path(run_id)):
                if p.exists():
                    p.unlink()

    def test_missing_file_fails(self, tmp_path):
        run_id = f"val-missing-{time.time_ns()}"
        exit_code, stdout, stderr = _run_validate(
            str(tmp_path / "nonexistent.json"), "system", run_id
        )
        assert exit_code != 0
        assert "not found" in stderr

    def test_invalid_json_fails(self, tmp_path):
        run_id = f"val-badjson-{time.time_ns()}"
        try:
            draft = tmp_path / "bad.json"
            draft.write_text("not json {{{")
            exit_code, stdout, stderr = _run_validate(str(draft), "system", run_id)
            assert exit_code != 0
            assert "JSON parse error" in stderr
        finally:
            for p in (_flag_path(run_id), _attempt_path(run_id)):
                if p.exists():
                    p.unlink()

    def test_attempt_limit_enforced(self, tmp_path):
        run_id = f"val-limit-{time.time_ns()}"
        try:
            payload = _minimal_payload(run_id=run_id, adr_markdown="short")
            draft = _write_draft(payload, tmp_path)

            # Burn through 3 attempts
            for _ in range(3):
                _run_validate(str(draft), "system", run_id)

            # 4th should fail with attempt limit
            exit_code, stdout, stderr = _run_validate(str(draft), "system", run_id)
            assert exit_code != 0
            assert "Maximum" in stderr
        finally:
            for p in (_flag_path(run_id), _attempt_path(run_id)):
                if p.exists():
                    p.unlink()

    def test_success_cleans_up_attempt_file(self, tmp_path):
        run_id = f"val-cleanup-{time.time_ns()}"
        try:
            payload = _minimal_payload(run_id=run_id)
            draft = _write_draft(payload, tmp_path)

            # First attempt fails (short ADR) to create attempt file
            bad_payload = _minimal_payload(run_id=run_id, adr_markdown="short")
            bad_draft = _write_draft(bad_payload, tmp_path)
            _run_validate(str(bad_draft), "system", run_id)
            assert _attempt_path(run_id).exists()

            # Second attempt succeeds — should clean up
            good_draft = _write_draft(payload, tmp_path)
            exit_code, stdout, stderr = _run_validate(str(good_draft), "system", run_id)
            assert exit_code == 0
            assert not _attempt_path(run_id).exists()
        finally:
            for p in (_flag_path(run_id), _attempt_path(run_id)):
                if p.exists():
                    p.unlink()

    def test_usage_error_on_missing_args(self):
        result = subprocess.run(
            ["python", str(VALIDATE_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Usage" in result.stderr

    def test_adr_saved_on_success(self, tmp_path):
        run_id = f"val-adr-{time.time_ns()}"
        try:
            payload = _minimal_payload(run_id=run_id)
            draft = _write_draft(payload, tmp_path)

            exit_code, stdout, stderr = _run_validate(str(draft), "system", run_id)
            assert exit_code == 0
            assert "ADR saved" in stdout
            assert "ADR-SYSTEM-" in stdout
        finally:
            for p in (_flag_path(run_id), _attempt_path(run_id)):
                if p.exists():
                    p.unlink()
