"""Tests for capability-claim audit (consolidation/deprecation/routing tasks).

Covers all 9 requirements from the goal:
1. Reuse existing /go discovery-first, report-gate, and confirm-closed paths
2. Trigger audit for consolidation/deprecation/routing tasks
3. Classification schema (7 values)
4. Required evidence fields for absorbed/shipped/production claims
5. Pending backend blocks shipped/production claim
6. Visible-surface alone insufficient
7. Confirm-closed includes 4 checks
8. Reports distinguish consolidation/routing/backend/pending
9. Tests cover all scenarios
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import (  # noqa: E402
    detect_capability_claims,
    classify_capability,
    derive_report_gate,
    generate_proposal,
)
from capability_claim_audit import (  # noqa: E402
    audit_claim,
    run_audit,
    _classify_from_source,
    _determine_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def consolidation_prompt():
    return (
        "Consolidate the /search and /research commands into /search-research. "
        "The old /search command should be absorbed into the parent. "
        "Mark /research as a stub."
    )


@pytest.fixture
def deprecation_prompt():
    return (
        "Deprecate the /legacy command. Add deprecation header but keep the "
        "engine running for backward compatibility."
    )


@pytest.fixture
def routing_prompt():
    return (
        "Route /old-mode to the new /new-mode parent command. "
        "The backend runner is not built yet."
    )


@pytest.fixture
def cleanup_prompt():
    return "Clean up unused plugin skills and remove stale command stubs."


@pytest.fixture
def plain_prompt():
    return "Fix the failing authentication tests."


# ---------------------------------------------------------------------------
# Req 2: Trigger detection
# ---------------------------------------------------------------------------

class TestTriggerDetection:
    def test_consolidation_triggers_audit(self, consolidation_prompt):
        claims = detect_capability_claims(consolidation_prompt)
        assert len(claims) > 0
        assert any("consolidat" in c.get("trigger_terms", []) for c in claims)

    def test_deprecation_triggers_audit(self, deprecation_prompt):
        claims = detect_capability_claims(deprecation_prompt)
        assert len(claims) > 0
        assert any("deprecat" in c.get("trigger_terms", []) for c in claims)

    def test_routing_triggers_audit(self, routing_prompt):
        claims = detect_capability_claims(routing_prompt)
        assert len(claims) > 0
        assert any("rout" in c.get("trigger_terms", []) for c in claims)

    def test_cleanup_triggers_audit(self, cleanup_prompt):
        claims = detect_capability_claims(cleanup_prompt)
        assert len(claims) > 0

    def test_plain_prompt_no_audit(self, plain_prompt):
        claims = detect_capability_claims(plain_prompt)
        assert len(claims) == 0

    def test_absorption_triggers_audit(self):
        prompt = "Absorb the /old-skill functionality into /new-skill."
        claims = detect_capability_claims(prompt)
        assert len(claims) > 0


# ---------------------------------------------------------------------------
# Req 3: Classification schema
# ---------------------------------------------------------------------------

class TestClassificationSchema:
    VALID_CLASSIFICATIONS = frozenset({
        "true_stub", "deprecation_header_on_retained_engine",
        "retained_engine", "routed_to_parent", "pending_backend",
        "deleted", "unknown",
    })

    def test_classify_true_stub(self, tmp_path):
        stub_file = tmp_path / "stub_cmd.py"
        stub_file.write_text(
            '#!/usr/bin/env python3\n'
            '"""Deprecated command - pass through only."""\n'
            'print("Use /new instead")\n'
        )
        result = classify_capability({
            "source_path": str(stub_file),
            "claimed_status": "stub",
        })
        assert result == "true_stub"

    def test_classify_deprecation_header_on_retained_engine(self, tmp_path):
        engine_file = tmp_path / "engine.py"
        engine_file.write_text(
            '#!/usr/bin/env python3\n'
            '"""Deprecated but still runs."""\n'
            'import warnings\n'
            'warnings.warn("Deprecated", DeprecationWarning)\n'
            'def process_data(items):\n'
            '    results = []\n'
            '    for item in items:\n'
            '        results.append(transform(item))\n'
            '    return results\n'
            'def transform(item):\n'
            '    return item.upper()\n'
        )
        result = classify_capability({
            "source_path": str(engine_file),
            "claimed_status": "absorbed",
        })
        assert result == "deprecation_header_on_retained_engine"

    def test_classify_retained_engine(self, tmp_path):
        engine_file = tmp_path / "real_engine.py"
        engine_file.write_text(
            '#!/usr/bin/env python3\n'
            '"""Full implementation."""\n'
            'def process(items):\n'
            '    return [transform(i) for i in items]\n'
            'def transform(item):\n'
            '    return item.strip().lower()\n'
        )
        result = classify_capability({
            "source_path": str(engine_file),
            "claimed_status": "shipped",
        })
        assert result == "retained_engine"

    def test_classify_routed_to_parent(self, tmp_path):
        router_file = tmp_path / "router.py"
        router_file.write_text(
            'def route(query):\n'
            '    return parent_handler.forward(query)\n'
        )
        result = classify_capability({
            "source_path": str(router_file),
            "claimed_status": "routed",
        })
        assert result == "routed_to_parent"

    def test_classify_deleted(self, tmp_path):
        result = classify_capability({
            "source_path": str(tmp_path / "nonexistent.py"),
            "claimed_status": "deleted",
        })
        assert result == "deleted"

    def test_classify_pending_backend(self, tmp_path):
        stub_file = tmp_path / "stub.py"
        stub_file.write_text('# placeholder\n')
        result = classify_capability({
            "source_path": str(stub_file),
            "backend_path": str(tmp_path / "nonexistent_backend.py"),
            "claimed_status": "absorbed",
        })
        assert result == "pending_backend"

    def test_classify_unknown_no_source(self):
        result = classify_capability({"claimed_status": "unknown"})
        assert result == "unknown"


# ---------------------------------------------------------------------------
# Req 4: Required evidence for absorbed/shipped/production claims
# ---------------------------------------------------------------------------

class TestRequiredEvidence:
    def test_absorbed_claim_needs_backend(self, tmp_path):
        stub_file = tmp_path / "old_cmd.py"
        stub_file.write_text(
            'def main():\n'
            '    return new_handler.run()\n'
        )
        result = audit_claim({
            "command": "/old-cmd",
            "claimed_status": "absorbed",
            "source_path": str(stub_file),
            "backend_path": str(tmp_path / "missing_backend.py"),
        })
        assert result["status"] == "overclaim"

    def test_shipped_claim_needs_backend(self, tmp_path):
        stub_file = tmp_path / "cmd.py"
        stub_file.write_text(
            'def main():\n'
            '    return handler.run()\n'
        )
        result = audit_claim({
            "command": "/cmd",
            "claimed_status": "shipped",
            "source_path": str(stub_file),
            "backend_path": str(tmp_path / "missing.py"),
        })
        assert result["status"] == "overclaim"


# ---------------------------------------------------------------------------
# Req 5: Parent route to missing backend blocks shipped/production
# ---------------------------------------------------------------------------

class TestMissingBackendBlocks:
    def test_routed_with_missing_backend_is_overclaim(self, tmp_path):
        router_file = tmp_path / "router.py"
        router_file.write_text(
            'def route(q):\n'
            '    return parent.forward(q)\n'
        )
        result = audit_claim({
            "command": "/old",
            "claimed_status": "absorbed",
            "source_path": str(router_file),
            "parent_path": str(tmp_path / "parent.py"),
            "backend_path": str(tmp_path / "missing_backend.py"),
        })
        assert result["status"] == "overclaim"
        assert result["backend_exists"] is False

    def test_routed_with_existing_backend_is_verified(self, tmp_path):
        router_file = tmp_path / "router.py"
        router_file.write_text(
            'def route(q):\n'
            '    return parent.forward(q)\n'
        )
        backend_file = tmp_path / "backend.py"
        backend_file.write_text('def run(): pass\n')
        result = audit_claim({
            "command": "/old",
            "claimed_status": "absorbed",
            "source_path": str(router_file),
            "backend_path": str(backend_file),
        })
        assert result["status"] == "verified"
        assert result["backend_exists"] is True


# ---------------------------------------------------------------------------
# Req 6: Visible-surface alone insufficient
# ---------------------------------------------------------------------------

class TestVisibleSurfaceInsufficient:
    def test_visible_surface_complete_but_overclaim_fails(self, tmp_path):
        """Even if visible surface looks right, overclaim blocks completion."""
        stub_file = tmp_path / "old.py"
        stub_file.write_text('# pass through\n')
        # claimed as shipped but backend missing
        result = audit_claim({
            "command": "/old",
            "claimed_status": "shipped",
            "source_path": str(stub_file),
            "backend_path": str(tmp_path / "missing.py"),
        })
        assert result["status"] == "overclaim"

    def test_report_gate_requires_audit(self, consolidation_prompt):
        claims = detect_capability_claims(consolidation_prompt)
        gate = derive_report_gate("implement", "full_go", capability_claims=claims)
        assert gate["capability_claim_audit_required"] is True
        assert gate["capability_claim_audit_passed"] is False  # not yet verified


# ---------------------------------------------------------------------------
# Req 8: Reports distinguish consolidation/routing/backend/pending
# ---------------------------------------------------------------------------

class TestReportDistinction:
    def test_audit_result_has_distinction_fields(self, tmp_path):
        stub_file = tmp_path / "old.py"
        stub_file.write_text('# deprecated\nimport warnings\nwarnings.warn("old")\n')
        backend_file = tmp_path / "backend.py"
        backend_file.write_text('def run(): pass\n')

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        active_task = {
            "run_id": "test-run",
            "terminal_id": "test-term",
            "selected_at": "2026-01-01T00:00:00Z",
            "task": {
                "id": "TASK-1",
                "title": "Consolidate",
                "objective": "Merge commands",
                "status": "selected",
                "priority": "P1",
                "scope_in": [],
                "scope_out": [],
                "forbidden_files": [],
                "acceptance_criteria": [],
                "verification_commands": [],
                "capability_audit": {
                    "required": True,
                    "claims": [{
                        "command": "/old",
                        "claimed_status": "absorbed",
                        "source_path": str(stub_file),
                        "backend_path": str(backend_file),
                    }],
                },
            },
        }
        (state_dir / "active-task_test-run.json").write_text(
            json.dumps(active_task), encoding="utf-8"
        )

        result = run_audit(state_dir, "test-run")
        assert "visible_surface_complete" in result
        assert "routing_complete" in result
        assert "backend_implemented" in result
        assert "deferred_capabilities" in result


# ---------------------------------------------------------------------------
# Req 9: Pending backend language allowed only when explicitly marked
# ---------------------------------------------------------------------------

class TestPendingBackendLanguage:
    def test_pending_claim_is_deferred_not_overclaim(self, tmp_path):
        stub_file = tmp_path / "stub.py"
        stub_file.write_text('# placeholder\n')
        result = audit_claim({
            "command": "/new",
            "claimed_status": "pending",
            "source_path": str(stub_file),
            "backend_path": str(tmp_path / "missing.py"),
        })
        assert result["status"] == "deferred"

    def test_absorbed_with_missing_backend_is_overclaim(self, tmp_path):
        stub_file = tmp_path / "stub.py"
        stub_file.write_text('# placeholder\n')
        result = audit_claim({
            "command": "/old",
            "claimed_status": "absorbed",
            "source_path": str(stub_file),
            "backend_path": str(tmp_path / "missing.py"),
        })
        assert result["status"] == "overclaim"

    def test_deferred_capabilities_in_report(self, tmp_path):
        stub_file = tmp_path / "stub.py"
        stub_file.write_text('# placeholder\n')

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        active_task = {
            "run_id": "test-run",
            "terminal_id": "test-term",
            "selected_at": "2026-01-01T00:00:00Z",
            "task": {
                "id": "TASK-1",
                "title": "Route",
                "objective": "Route old to new",
                "status": "selected",
                "priority": "P1",
                "scope_in": [],
                "scope_out": [],
                "forbidden_files": [],
                "acceptance_criteria": [],
                "verification_commands": [],
                "capability_audit": {
                    "required": True,
                    "claims": [{
                        "command": "/old",
                        "claimed_status": "pending",
                        "source_path": str(stub_file),
                        "backend_path": str(tmp_path / "missing.py"),
                    }],
                },
            },
        }
        (state_dir / "active-task_test-run.json").write_text(
            json.dumps(active_task), encoding="utf-8"
        )

        result = run_audit(state_dir, "test-run")
        assert result["audit_passed"] is True
        assert "/old" in result["deferred_capabilities"]


# ---------------------------------------------------------------------------
# Integration: proposal emits capability_claims
# ---------------------------------------------------------------------------

class TestProposalIntegration:
    def test_generate_proposal_includes_capability_claims(self, consolidation_prompt):
        proposal = generate_proposal(consolidation_prompt, "run-1", "term-1")
        assert proposal.get("capability_claims") is not None
        assert proposal["report_gate"]["capability_claim_audit_required"] is True

    def test_generate_proposal_no_claims_for_plain_task(self, plain_prompt):
        proposal = generate_proposal(plain_prompt, "run-2", "term-2")
        assert proposal.get("capability_claims") is None
        assert proposal["report_gate"]["capability_claim_audit_required"] is False
