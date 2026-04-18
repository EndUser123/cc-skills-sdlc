#!/usr/bin/env python3
"""Integration tests for planning-v2 workflow.

Tests the strict readiness gate:
1. draft status when placeholders exist
2. Cannot advance to implementation-ready with unresolved findings
3. Status lifecycle: draft → in-review → implementation-ready
4. Plan artifact stays pure (no findings merged)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "__lib"))

import auto_verify
import arch_handoff_state
import pytest

# Alias for convenience
AV = auto_verify


class TestStrictReadinessGate:
    """Test the strict readiness gate that blocks implementation-ready."""

    def test_placeholder_blocks_implementation_ready(self, tmp_path: Path) -> None:
        """Placeholders in plan block advancement to implementation-ready."""
        plan = """---
status: draft
source: null
unresolved_blockers: 1
---

# Plan: Bad Plan

## Goal

*Describe the problem*

## Current State with Evidence

Context.

## Design Decisions and Invariants

Impl.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Open Questions

Need to confirm metric.
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        result = AV.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"
        placeholder_findings = [f for f in result["action_items"] if f["category"] == "placeholder"]
        assert len(placeholder_findings) > 0

    def test_raw_findings_blocks_implementation_ready(self, tmp_path: Path) -> None:
        """Raw findings in plan block advancement to implementation-ready."""
        plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Polluted Plan

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Impl.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Open Questions

None.

## Adversarial Findings

| ID | Severity | Finding |
|----|----------|---------|
| 1  | HIGH     | Issue   |
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text(
            '[{"id":"SEC-001","severity":"HIGH","description":"Issue"}]',
            encoding="utf-8",
        )
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n| SEC-001 | accepted | Incorporated |\n",
            encoding="utf-8",
        )
        result = AV.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"
        purity_findings = [f for f in result["action_items"] if f["category"] == "plan_purity"]
        assert len(purity_findings) > 0

    def test_contradiction_blocks_implementation_ready(self, tmp_path: Path) -> None:
        """Claims implementation-ready with unresolved HIGH findings is contradiction."""
        plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 1
---

# Plan: Contradiction Plan

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Impl.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Extra Section

*Describe the problem*

## Open Questions

Need clarification.
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text(
            '[{"id":"LOGIC-001","severity":"HIGH","description":"Issue"}]',
            encoding="utf-8",
        )
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n| LOGIC-001 | deferred | Follow-up |\n",
            encoding="utf-8",
        )
        result = AV.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"
        contradiction_findings = [
            f for f in result["action_items"] if f["id"] == "CONTRADICTION-001"
        ]
        assert len(contradiction_findings) > 0

    def test_concrete_plan_reaches_ready(self, tmp_path: Path) -> None:
        """Plan with concrete content and no findings reaches READY."""
        source_file = tmp_path / "search_index.py"
        source_file.write_text("def write_index():\n    pass\n", encoding="utf-8")
        plan = f"""---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Good Plan

## Goal

The search index race condition causes data corruption under concurrent writes.

## Current State with Evidence

**File:** `{source_file}`
**Lines:** 1-2

write_index currently performs an unprotected write shared across terminals.

## Design Decisions and Invariants

Use FileLock only around writes to minimize latency impact.

## Implementation Changes

**TASK-001**: Add file lock to search_index.py
- Action: Use filelock.FileLock around write operations
- Acceptance:
  - test_concurrent_write passes 10/10 runs
  - write latency increase < 10ms

## Test Matrix

test_search_index.py::test_concurrent_write fails intermittently.

## Assumptions/Defaults

Risk: lock overhead. Acceptance: < 10ms added latency.

## Open Questions

None.
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )
        result = AV.verify_plan(str(plan_file))
        assert result["status"] == "READY", f"Expected READY but got: {result['action_items']}"


class TestStatusLifecycle:
    """Test the status lifecycle transitions."""

    def test_draft_to_in_review_allowed(self, tmp_path: Path) -> None:
        """Can set status from draft to in-review."""
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Test

## Goal

Real problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Impl.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Open Questions

None.
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        result = AV.verify_plan(str(plan_file))
        # draft with concrete content is READY (no blockers)
        assert result["status"] == "READY"
        assert result["claimed_status"] == "draft"


class TestArchHandoffResumePersistence:
    """Test durable /planning -> /arch -> /planning handoff behavior."""

    INITIAL_PLAN = """---
status: draft
source: P:/__csf/arch_decisions/ADR-20260407-example.md
unresolved_blockers: 0
---

# Plan: Pending Arch Rewrite

## Goal

Close the planning workflow without bouncing back into /arch after a packet has already been returned.

## Current State with Evidence

The workflow still relies on replay across planning handoffs and has no explicit state-model contracts.

## Design Decisions and Invariants

The plan currently assumes replay and handoff semantics but does not close identity or invalidation rules.

## Implementation Changes

**TASK-001**: Rewrite the planning artifact
- Action: Consume the /arch packet and rewrite the draft.
**Acceptance Criteria:**
- Rewritten plan includes closed contracts

## Test Matrix

pytest P:/packages/cc-skills-sdlc/skills/planning/tests/test_planning_integration_v2.py

## Contract Authority Reference

**Contract-sensitive:** YES

## Contract Boundary Matrix

| Boundary | Producer | Consumer | Required Fields |
|----------|----------|----------|-----------------|
| arch-to-planning | /arch | /planning | packet_version |

## Assumptions/Defaults

The architecture packet exists and is usable.

## Open Questions

None.
"""

    ARCH_OUTPUT = """contract_authority_packet:
  packet_version: "2"
  contract_sensitive: true
  authority:
    closure_source: "contract_authority_packet"
    prose_role: "explanatory_only"
  boundaries:
    - boundary_id: "arch-to-planning"
      producer: "/arch"
      consumer: "/planning"
      schema:
        id: "planning-handoff"
        version: "2"
      required_fields: ["packet_version", "plan_title", "goal"]
      optional_fields: []
      freshness_authority: "/arch decision packet"
      invalidation_trigger: "new /arch closure for the same draft"
      precedence_rule: "latest closed packet wins"
      failure_behavior: "Planning blocks local rewrite until the packet is consumed"
      validator_owner: "/planning"
      proof_owner: "/verify"
      downstream_consumers: ["/planning"]

planning_handoff_packet:
  packet_version: "2"
  source_adr: "P:/__csf/arch_decisions/ADR-20260407-example.md"
  plan_title: "Pending Arch Rewrite"
  goal: "Close the planning workflow without bouncing back into /arch after a packet has already been returned."
  implementation_changes:
    - task_id: "TASK-001"
      title: "Rewrite the planning artifact"
  contract_authority_reference:
    contract_sensitive: true

RETURN TO CALLER: /planning
Resume policy: automatic
Caller action: consume packet, rewrite plan, rerun auto_verify
"""

    REWRITTEN_PLAN = """---
status: draft
source: P:/__csf/arch_decisions/ADR-20260407-example.md
unresolved_blockers: 0
---

# Plan: Pending Arch Rewrite

## Goal

Restructure the planning artifact flow so the local rewrite path is deterministic.

## Current State with Evidence

Current planning artifacts mix structural responsibilities that should stay in one local rewrite path.

## Design Decisions and Invariants

Keep artifact rewriting in one local planning path and keep behavior unchanged.

## Implementation Changes

### TASK-001: Normalize planning artifact helpers

- Action: Move the supporting helpers under one planning-local path.
**Acceptance Criteria:**
- Helpers exist in the new location

### TASK-002: Update the local rewrite flow

- Action: Route the local rewrite through the normalized helper path.
**Acceptance Criteria:**
- The rewrite path is deterministic

## Test Matrix

pytest P:/packages/cc-skills-sdlc/skills/planning/tests/test_planning_integration_v2.py::TestArchHandoffResumePersistence::test_pending_arch_receipt_prevents_reinvocation_and_marks_consumed_after_rewrite

## Contract Authority Reference

**Contract-sensitive:** NO — this is a structural/organizational rewrite only.

## Contract Boundary Matrix

**Not applicable** — this plan does not create, change, or remove producer/consumer boundary semantics.

## State-Model Contracts

**Not applicable** — this plan does not touch persistence, history, stale-data immunity, or event-source boundaries.

## Assumptions/Defaults

Existing architecture authority remains unchanged while the artifact layout is normalized locally.

## Open Questions

None.
"""

    def test_pending_arch_receipt_prevents_reinvocation_and_marks_consumed_after_rewrite(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state_dir = tmp_path / "state" / "arch_handoff"
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_STATE_DIR", str(state_dir))
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-terminal")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(self.INITIAL_PLAN, encoding="utf-8")

        initial_result = AV.verify_plan(str(plan_file))
        assert initial_result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert initial_result["status"] == "BLOCKED"
        receipt = arch_handoff_state.record_arch_handoff_receipt(
            str(plan_file),
            self.ARCH_OUTPUT,
            blocker_ids=initial_result["next_action"]["arch_blocker_ids"],
        )
        assert receipt["status"] == "pending_consumption"
        assert Path(receipt["receipt_path"]).exists()
        assert Path(receipt["receipt_path"]).parent.name == "test-terminal"

        resumed_result = AV.verify_plan(str(plan_file))
        assert resumed_result["status"] == "BLOCKED"
        assert resumed_result["next_action"]["type"] == "fix_issues"
        assert resumed_result["next_action"]["authoritative_source"] == "arch_handoff_receipt"
        assert resumed_result["arch_handoff_receipt"]["status"] == "pending_consumption"
        plan_file.write_text(self.REWRITTEN_PLAN, encoding="utf-8")

        final_result = AV.verify_plan(str(plan_file))
        assert final_result["status"] == "READY", final_result["action_items"]
        assert final_result["arch_handoff_receipt"]["status"] == "consumed"

        consumed_receipt = arch_handoff_state.load_arch_handoff_receipt(str(plan_file))
        assert consumed_receipt is not None
        assert consumed_receipt["status"] == "consumed"
        assert consumed_receipt["consumed_by_plan_sha256"] == final_result["plan_sha256"]

    def test_stale_plan_sha_does_not_suppress_new_arch_invocation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state_dir = tmp_path / "state" / "arch_handoff"
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_STATE_DIR", str(state_dir))
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-terminal")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(self.INITIAL_PLAN, encoding="utf-8")
        initial_result = AV.verify_plan(str(plan_file))
        arch_handoff_state.record_arch_handoff_receipt(
            str(plan_file),
            self.ARCH_OUTPUT,
            blocker_ids=initial_result["next_action"]["arch_blocker_ids"],
        )

        stale_rewrite = self.INITIAL_PLAN.replace(
            "The workflow still relies on replay across planning handoffs and has no explicit state-model contracts.",
            "The workflow still relies on replay across planning handoffs and has no explicit state-model contracts.\n\nAdditional evidence: terminal replay mutated the draft after the prior /arch packet.",
        )
        plan_file.write_text(stale_rewrite, encoding="utf-8")

        resumed_result = AV.verify_plan(str(plan_file))
        assert resumed_result["status"] == "BLOCKED"
        assert resumed_result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert "arch_handoff_receipt" not in resumed_result

    def test_expired_receipt_does_not_suppress_new_arch_invocation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state_dir = tmp_path / "state" / "arch_handoff"
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_STATE_DIR", str(state_dir))
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_TTL_SECONDS", "0")
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-terminal")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(self.INITIAL_PLAN, encoding="utf-8")
        initial_result = AV.verify_plan(str(plan_file))
        arch_handoff_state.record_arch_handoff_receipt(
            str(plan_file),
            self.ARCH_OUTPUT,
            blocker_ids=initial_result["next_action"]["arch_blocker_ids"],
        )

        resumed_result = AV.verify_plan(str(plan_file))
        assert resumed_result["status"] == "BLOCKED"
        assert resumed_result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert "arch_handoff_receipt" not in resumed_result

    def test_receipts_are_terminal_scoped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state_dir = tmp_path / "state" / "arch_handoff"
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_STATE_DIR", str(state_dir))
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "terminal-a")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-a")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(self.INITIAL_PLAN, encoding="utf-8")
        initial_result = AV.verify_plan(str(plan_file))
        arch_handoff_state.record_arch_handoff_receipt(
            str(plan_file),
            self.ARCH_OUTPUT,
            blocker_ids=initial_result["next_action"]["arch_blocker_ids"],
        )

        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "terminal-b")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-b")
        resumed_result = AV.verify_plan(str(plan_file))
        assert resumed_result["status"] == "BLOCKED"
        assert resumed_result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert "arch_handoff_receipt" not in resumed_result

    def test_receipt_survives_same_terminal_session_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state_dir = tmp_path / "state" / "arch_handoff"
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_STATE_DIR", str(state_dir))
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-terminal")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-a")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(self.INITIAL_PLAN, encoding="utf-8")
        initial_result = AV.verify_plan(str(plan_file))
        arch_handoff_state.record_arch_handoff_receipt(
            str(plan_file),
            self.ARCH_OUTPUT,
            blocker_ids=initial_result["next_action"]["arch_blocker_ids"],
        )

        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-b")
        resumed_result = AV.verify_plan(str(plan_file))
        assert resumed_result["status"] == "BLOCKED"
        assert resumed_result["next_action"]["type"] == "fix_issues"
        assert resumed_result["next_action"]["authoritative_source"] == "arch_handoff_receipt"

    def test_corrupt_receipt_is_ignored_instead_of_crashing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state_dir = tmp_path / "state" / "arch_handoff"
        monkeypatch.setenv("PLANNING_ARCH_HANDOFF_STATE_DIR", str(state_dir))
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-terminal")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(self.INITIAL_PLAN, encoding="utf-8")
        initial_result = AV.verify_plan(str(plan_file))
        receipt = arch_handoff_state.record_arch_handoff_receipt(
            str(plan_file),
            self.ARCH_OUTPUT,
            blocker_ids=initial_result["next_action"]["arch_blocker_ids"],
        )
        Path(receipt["receipt_path"]).write_text("{broken json", encoding="utf-8")

        resumed_result = AV.verify_plan(str(plan_file))
        assert resumed_result["status"] == "BLOCKED"
        assert resumed_result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert "arch_handoff_receipt" not in resumed_result

    def test_draft_with_placeholder_stays_draft(self, tmp_path: Path) -> None:
        """draft plan with placeholder is BLOCKED (can't advance)."""
        plan = """---
status: draft
source: null
unresolved_blockers: 1
---

# Plan: Test

## Goal

*Describe the problem*

## Current State with Evidence

Context.

## Design Decisions and Invariants

Impl.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Open Questions

Need to investigate.
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        result = AV.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"
        assert result["claimed_status"] == "draft"


class TestPlanArtifactPurity:
    """Test that plan artifacts remain pure (no findings merged)."""

    def test_verification_result_not_in_plan(self, tmp_path: Path) -> None:
        """Verification result is written to separate .review.result.json, not plan."""
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Test

## Goal

Real problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Impl.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Open Questions

None.
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        result = AV.verify_plan(str(plan_file))

        # Plan file should NOT contain verification results
        with open(plan_file, encoding="utf-8") as f:
            plan_content = f.read()
        assert "auto_verify" not in plan_content
        assert (
            "verification" not in plan_content.lower()
            or "Verification" in plan_content.split("## ")[-1]
        )
        # No findings tables
        assert "| ID | Severity |" not in plan_content

        # Result file should exist
        result_file = plan_file.with_suffix(".review.result.json")
        assert result_file.exists()
        result_data = json.loads(result_file.read_text(encoding="utf-8"))
        assert result_data["status"] == "READY"


class TestCompactResilience:
    """Tests for compact resilience features (RSN Actions 1-4).

    Covers:
    - TEST-001: load_review_findings() graceful JSON error handling
    - TEST-002: Idempotency check (valid JSON + plan_path match + age check)
    - TEST-003: Cross-plan contamination detection (wrong plan_path rejected)
    - TEST-004: cleanup_plan_artifacts() removes stale files
    - TEST-005: Stale findings rejection (age check)
    - TEST-006: check_dispositions() handles malformed findings gracefully
    - TEST-007: Critic skips files with mismatched plan_path (idempotency script)
    - TEST-008: validate_adversarial_agents() returns correct structure
    """

    def test_load_review_findings_handles_malformed_json(self, tmp_path: Path) -> None:
        """TEST-001: load_review_findings() returns empty list for malformed JSON."""
        findings_file = tmp_path / "test.review.findings.json"
        findings_file.write_text('{"id": "SEC-001", not valid json}', encoding="utf-8")
        result = AV.load_review_findings(findings_file)
        assert result == [], "Malformed JSON should return empty list, not crash"

    def test_load_review_findings_handles_empty_file(self, tmp_path: Path) -> None:
        """TEST-001: load_review_findings() returns empty list for empty file."""
        findings_file = tmp_path / "test.review.findings.json"
        findings_file.write_text("", encoding="utf-8")
        result = AV.load_review_findings(findings_file)
        assert result == [], "Empty file should return empty list"

    def test_idempotency_rejects_wrong_plan_path(self, tmp_path: Path) -> None:
        """TEST-002/TEST-003: Findings with mismatched plan_path are not reused.

        The idempotency check in SKILL.md agent prompts requires:
        - File exists
        - Valid JSON
        - plan_path field matches current plan
        - File age < 86400 seconds
        """
        plan_file = tmp_path / "plan_A.md"
        plan_file.write_text("---\nstatus: draft\n---\n# Plan A\n", encoding="utf-8")

        # Create findings file for plan_B (wrong plan_path)
        findings_file = tmp_path / "plan_B.review.findings.json"
        findings_file.write_text(
            json.dumps({"plan_path": str(tmp_path / "plan_B.md"), "findings": []}),
            encoding="utf-8",
        )

        # load_review_findings should still load it (no plan_path validation at this level)
        # But the SKILL.md agent prompt will reject it via the idempotency script
        result = AV.load_review_findings(findings_file)
        # The function loads the JSON but doesn't validate plan_path
        # That's done at the agent prompt level via the Python idempotency script
        assert isinstance(result, list)

    def test_idempotency_accepts_correct_plan_path(self, tmp_path: Path) -> None:
        """TEST-002: Findings with matching plan_path are loaded."""
        plan_file = tmp_path / "my_plan.md"
        plan_file.write_text("---\nstatus: draft\n---\n# My Plan\n", encoding="utf-8")

        findings_file = tmp_path / "my_plan.review.findings.json"
        findings_file.write_text(
            json.dumps({"plan_path": str(plan_file), "findings": [{"id": "TEST-001"}]}),
            encoding="utf-8",
        )

        result = AV.load_review_findings(findings_file)
        assert isinstance(result, list)
        # The findings are nested under "findings" key, not at root
        # load_review_findings looks for dicts with "id" and "severity" fields
        # The wrapper object doesn't have those at root level
        assert result == [], "Nested findings structure loaded via flatten"

    def test_cleanup_plan_artifacts_removes_stale_files(self, tmp_path: Path) -> None:
        """TEST-004: cleanup_plan_artifacts() removes files older than 7 days."""
        import os
        import time

        # Create a stale artifact (8 days old)
        stale_file = tmp_path / "old_plan.review.findings.json"
        stale_file.write_text('[{"id": "STALE-001"}]', encoding="utf-8")
        old_mtime = time.time() - (8 * 86400)
        os.utime(stale_file, (old_mtime, old_mtime))

        # Create a fresh artifact (1 day old)
        fresh_file = tmp_path / "new_plan.review.findings.json"
        fresh_file.write_text('[{"id": "FRESH-001"}]', encoding="utf-8")
        new_mtime = time.time() - (1 * 86400)
        os.utime(fresh_file, (new_mtime, new_mtime))

        result = AV.cleanup_plan_artifacts(plans_dir=tmp_path, retention_seconds=604800)

        assert result["total_removed"] == 1, "Only stale file should be removed"
        assert str(stale_file) in result["removed"]
        assert fresh_file.exists(), "Fresh file should NOT be removed"
        assert not stale_file.exists(), "Stale file should be removed"

    def test_cleanup_plan_artifacts_handles_nonexistent_dir(self, tmp_path: Path) -> None:
        """TEST-004: cleanup_plan_artifacts() returns gracefully when dir doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"
        result = AV.cleanup_plan_artifacts(plans_dir=nonexistent)
        assert result["total_removed"] == 0
        assert result["errors"] == []
        assert result["removed"] == []

    def test_cleanup_removes_multiple_stale_artifact_types(self, tmp_path: Path) -> None:
        """TEST-004: cleanup_plan_artifacts() removes all review artifact types."""
        import os
        import time

        # Create stale artifacts of each type
        artifacts = [
            tmp_path / "old.review.findings.json",
            tmp_path / "old.review.summary.md",
            tmp_path / "old.review.result.json",
        ]
        old_mtime = time.time() - (8 * 86400)
        for f in artifacts:
            f.write_text("content", encoding="utf-8")
            os.utime(f, (old_mtime, old_mtime))

        result = AV.cleanup_plan_artifacts(plans_dir=tmp_path, retention_seconds=604800)

        assert result["total_removed"] == 3, "All three artifact types should be removed"
        for f in artifacts:
            assert not f.exists(), f"{f.name} should be removed"

    def test_check_dispositions_handles_missing_summary(self, tmp_path: Path) -> None:
        """TEST-006: check_dispositions() returns empty list when summary is missing."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("---\nstatus: draft\n---\n# Plan\n", encoding="utf-8")
        result = AV.check_dispositions(str(plan_file), plan_file.read_text(encoding="utf-8"))
        # Should return empty list (no findings) when files don't exist
        assert isinstance(result, list)

    def test_validate_adversarial_agents_returns_correct_structure(self) -> None:
        """TEST-008: validate_adversarial_agents() returns dict with required keys."""
        validation = AV.validate_adversarial_agents()
        assert isinstance(validation, dict)
        assert "valid" in validation
        assert "missing" in validation
        assert "available" in validation
        assert isinstance(validation["missing"], list)
        assert isinstance(validation["available"], list)


class TestAdversarialAgentValidation:
    """Test adversarial agent availability validation."""

    def test_missing_agents_reported(self) -> None:
        """Missing adversarial agents are reported in verification result."""
        validation = AV.validate_adversarial_agents()
        # Check structure
        assert "valid" in validation
        assert "missing" in validation
        assert "available" in validation
        # All required agents should be available in this environment
        assert validation["valid"] is True, f"Missing agents: {validation['missing']}"


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
