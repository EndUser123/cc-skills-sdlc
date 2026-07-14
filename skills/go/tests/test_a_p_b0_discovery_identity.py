#!/usr/bin/env python3
"""Tests for A-p + B0: discovery contract and identity/worktree foundation.

Proves the /go SKILL.md contains the required A-p and B0 sections.
"""
from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


# ── A-p: Discovery Contract ────────────────────────────────────────

class TestApDiscoveryContract:
    """SKILL.md must contain the mandatory discovery contract."""

    def test_has_step_0_contract_section(self):
        text = _skill_text()
        assert "STEP 0:" in text, "SKILL.md must have a Step 0 (Contract) section"

    def test_has_step_0_identity_envelope(self):
        text = _skill_text()
        assert "session_id" in text, "Step 0 must define session_id"
        assert "run_id" in text, "Step 0 must define run_id"
        assert "workspace_id" in text, "Step 0 must define workspace_id"

    def test_has_step_0_worktree_disposition(self):
        text = _skill_text()
        assert "USE_CURRENT_ISOLATED_WORKTREE" in text, "Step 0 must include worktree dispositions"
        assert "REUSE_OWNED_WORKTREE" in text
        assert "READ_ONLY_NO_WORKTREE_NEEDED" in text
        assert "BLOCKED_WORKTREE_OWNERSHIP_AMBIGUOUS" in text

    def test_has_step_0_contract_boundary(self):
        text = _skill_text()
        assert "contract_fingerprint" in text, "Step 0 must include contract_fingerprint"
        assert "In scope" in text
        assert "Out of scope" in text
        assert "Must not change" in text

    def test_has_step_0_5_discovery_section(self):
        text = _skill_text()
        assert "STEP 0.5:" in text, "SKILL.md must have a Step 0.5 (Discovery) section"

    def test_has_discovery_scope(self):
        text = _skill_text()
        assert "consumed source and runtime path" in text, "Discovery must include consumed path check"
        assert "cache vs source" in text.lower() or "SHA256" in text, "Discovery must include cache-vs-source"

    def test_has_discovery_path_tracing(self):
        text = _skill_text()
        assert "entry point" in text and "registration" in text and "implementation" in text and "storage" in text, "Discovery must include path tracing"

    def test_has_full_disposition_vocabulary(self):
        text = _skill_text()
        assert "ALREADY_EXISTS" in text, "Discovery must include ALREADY_EXISTS"
        assert "BLOCKED_DISCOVERY_INCOMPLETE" in text, "Discovery must include BLOCKED_DISCOVERY_INCOMPLETE"
        assert "NEW_MECHANISM_JUSTIFIED" in text
        assert "REPAIR_EXISTING" in text
        assert "REMOVE_DUPLICATE" in text

    def test_has_refresh_conditions(self):
        text = _skill_text()
        assert "stale" in text.lower() and "refreshed" in text.lower(), "Discovery must include refresh conditions"
        assert "contract_fingerprint changes" in text or "contract_fingerprint" in text

    def test_has_affected_surfaces_fingerprint(self):
        text = _skill_text()
        assert "affected_surfaces_fingerprint" in text, "Discovery must include affected_surfaces_fingerprint"

    def test_new_mechanism_requires_justification(self):
        text = _skill_text()
        assert "NOT justified" in text and "existing mechanisms" in text, "New mechanism must justify why existing mechanisms aren't sufficient"

    def test_foreign_state_fails_silent(self):
        text = _skill_text()
        assert "fail silent" in text.lower() or "FOREIGN" in text

    def test_ambiguous_identity_blocks(self):
        text = _skill_text()
        assert "ambiguous" in text.lower() and "BLOCK" in text

    def test_no_automatic_worktree_creation(self):
        text = _skill_text()
        assert "NOT automatically create" in text or "must NOT automatically" in text

    def test_has_mandatory_sequence_with_steps(self):
        text = _skill_text()
        assert "Step 0" in text and "Step 0.5" in text

    def test_session_id_source_is_hook_payload(self):
        text = _skill_text()
        assert "Hook payload" in text or "hook payload" in text


# ── Version ────────────────────────────────────────────────────────

class TestVersion:
    def test_version_bumped(self):
        text = _skill_text()
        assert "version: 2.13.0" in text, "Version must be bumped to 2.13.0"
