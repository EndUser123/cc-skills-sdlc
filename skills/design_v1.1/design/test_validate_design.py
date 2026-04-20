"""Smoke tests for NTP v1.1 validate_design.py."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# Add design/ to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from schemas import (
    ContractAuthorityPacket,
    ContractBoundary,
    CriticFinding,
    DesignPayload,
    Severity,
)
from validate_design import validate, _validate_logic, _check_attempt_limit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_payload(run_id: str = "test-run-001") -> DesignPayload:
    cap = ContractAuthorityPacket()
    finding = CriticFinding(
        severity=Severity.LOW,
        category="test",
        description="Smoke-test finding",
    )
    return DesignPayload(
        run_id=run_id,
        mode="system",
        scope="all",
        user_query="test query",
        ast_summary="workspace: test/",
        sop="1. Draft\n2. Validate",
        template_name="system_precedent_deep",
        cap=cap,
        critic_findings=[finding],
        adr_markdown="# ADR-Test\n\n## Status\nAccepted\n\n## Context\nTest.",
    )


# ---------------------------------------------------------------------------
# Schema / logic validation
# ---------------------------------------------------------------------------

def test_validate_logic_accepts_minimal_valid_payload():
    payload = _minimal_payload()
    errors = _validate_logic(payload)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_validate_logic_rejects_missing_run_id():
    payload = _minimal_payload(run_id="")
    errors = _validate_logic(payload)
    assert any("run_id" in e for e in errors)


def test_validate_logic_rejects_bad_mode():
    payload = _minimal_payload()
    payload.mode = "invalid"
    errors = _validate_logic(payload)
    assert any("mode" in e for e in errors)


def test_validate_logic_rejects_bad_scope():
    payload = _minimal_payload()
    payload.scope = "invalid"
    errors = _validate_logic(payload)
    assert any("scope" in e for e in errors)


def test_validate_logic_rejects_empty_ast_summary():
    payload = _minimal_payload()
    payload.ast_summary = ""
    errors = _validate_logic(payload)
    assert any("ast_summary" in e for e in errors)


def test_validate_logic_rejects_short_adr():
    payload = _minimal_payload()
    payload.adr_markdown = "Short"
    errors = _validate_logic(payload)
    assert any("adr_markdown" in e for e in errors)


def test_validate_logic_rejects_missing_critic_findings():
    payload = _minimal_payload()
    payload.critic_findings = []
    errors = _validate_logic(payload)
    assert any("critic_findings" in e for e in errors)


def test_validate_logic_rejects_boundary_missing_producer():
    cap = ContractAuthorityPacket(
        boundaries=[
            ContractBoundary(
                boundary_id="b1",
                producer="",  # missing
                consumer="c1",
                input_schema_id="s1",
                output_schema_id="s2",
            )
        ]
    )
    payload = _minimal_payload()
    payload.cap = cap
    errors = _validate_logic(payload)
    assert any("producer" in e for e in errors)


# ---------------------------------------------------------------------------
# Round-trip through JSON
# ---------------------------------------------------------------------------

def test_design_payload_serializes_and_deserializes():
    original = _minimal_payload()
    round_trip = DesignPayload.from_dict(original.to_dict())
    assert round_trip.run_id == original.run_id
    assert round_trip.mode == original.mode
    assert round_trip.scope == original.scope
    assert round_trip.template_name == original.template_name
    assert round_trip.adr_markdown == original.adr_markdown


# ---------------------------------------------------------------------------
# validate() with a real temp file
# ---------------------------------------------------------------------------

def test_validate_succeeds_with_valid_payload():
    payload = _minimal_payload(run_id="smoke-test-001")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(payload.to_dict(), fh)
        tmp_path = fh.name

    try:
        # Clean up any stale flag/attempt files first
        for f in [f".verified_{payload.run_id}", f".attempt_{payload.run_id}"]:
            p = Path(__file__).parent / f
            if p.exists():
                p.unlink()

        result = validate(tmp_path, "system", payload.run_id)
        assert result is True
    finally:
        os.unlink(tmp_path)


def test_validate_fails_with_missing_file():
    result = validate("/nonexistent/design_draft.json", "system", "bad-run-001")
    assert result is False


def test_validate_fails_with_invalid_json():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("{ not valid json }")
        tmp_path = fh.name

    try:
        result = validate(tmp_path, "system", "bad-run-002")
        assert result is False
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
