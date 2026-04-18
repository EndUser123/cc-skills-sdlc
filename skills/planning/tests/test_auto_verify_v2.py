#!/usr/bin/env python3
"""Tests for auto_verify.py v2 - placeholder detection and contradiction checks.

New checks in v2:
1. Placeholder detection — FAIL if any placeholder residue found
2. Section completeness — all required sections present
3. Solo-dev violations — no team coordination patterns
4. RTM coverage — requirements mapped to tasks
5. Contradiction checks — FAIL if plan claims ready but has unresolved blockers
6. Disposition checks — every blocker/high finding has machine-readable disposition
7. Plan-purity checks — FAIL if plan contains raw findings tables or verification dumps
8. Status header — FAIL if status header missing or malformed
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "__lib"))

import auto_verify

# =============================================================================
# Test: check_placeholders
# =============================================================================


class TestPlaceholderDetection:
    """Test that placeholders are detected and block readiness."""

    @pytest.mark.parametrize(
        "placeholder",
        [
            "TODO",
            "TBD",
            "Describe the problem",
            "Add risk analysis",
            "path/to/",
            "Component A",
            "Component B",
            "Criteria one",
            "Criteria two",
            "Describe the solution",
            "Add test coverage",
            "*Add risk analysis*",
            "[ ] Unchecked box",
        ],
    )
    def test_placeholder_detected(self, placeholder: str) -> None:
        """Each placeholder pattern is detected as HIGH priority."""
        plan = f"""---
status: draft
---

# Plan: Test

## Problem

{placeholder}

## Context

Context.

## Existing Implementation

Impl.

## Test Coverage

Tests.

## Solution

Solution.

## Implementation Plan

**TASK-001**: Do something
- Action: Do it
- Acceptance:
  - Done

## Risks, Success Criteria, Dependencies

Risks.
"""
        findings = auto_verify.check_placeholders(plan)
        assert len(findings) > 0, f"Placeholder '{placeholder}' should be detected"
        # All placeholder findings are HIGH priority
        for f in findings:
            assert f["priority"] == "HIGH", "Placeholder findings must be HIGH"

    def test_concrete_content_not_flagged(self) -> None:
        """Concrete content is not flagged as placeholder."""
        plan = """---
status: draft
---

# Plan: Real Plan

## Problem

The search indexing has a race condition.

## Context

Multiple terminals write to the same index.

## Existing Implementation

search_index.py handles writes.

## Test Coverage

test_search_index.py covers basic cases.

## Solution

Add file locking to index writes.

## Implementation Plan

**TASK-001**: Add file lock
- Action: Use filelock library
- Acceptance:
  - Concurrent writes don't corrupt index

## Risks, Success Criteria, Dependencies

Risk: lock overhead on write-heavy workloads.
"""
        findings = auto_verify.check_placeholders(plan)
        assert len(findings) == 0, "Concrete content should not be flagged"


# =============================================================================
# Test: check_status_header
# =============================================================================


class TestStatusHeader:
    """Test status header validation."""

    def test_valid_status_draft(self) -> None:
        """status: draft is valid."""
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Test
"""
        findings = auto_verify.check_status_header(plan)
        assert len(findings) == 0

    def test_valid_status_in_review(self) -> None:
        """status: in-review is valid."""
        plan = """---
status: in-review
source: some/path.md
unresolved_blockers: 1
---

# Plan: Test
"""
        findings = auto_verify.check_status_header(plan)
        assert len(findings) == 0

    def test_valid_status_implementation_ready(self) -> None:
        """status: implementation-ready is valid."""
        plan = """---
status: implementation-ready
source: some/path.md
unresolved_blockers: 0
---

# Plan: Test
"""
        findings = auto_verify.check_status_header(plan)
        assert len(findings) == 0

    def test_missing_status_header(self) -> None:
        """Missing status header is HIGH priority finding."""
        plan = """---
source: some/path
unresolved_blockers: 0
---

# Plan: Test
"""
        findings = auto_verify.check_status_header(plan)
        assert len(findings) == 1
        assert findings[0]["priority"] == "HIGH"
        assert findings[0]["id"] == "STATUS-002"

    def test_invalid_status_value(self) -> None:
        """Invalid status value is rejected."""
        plan = """---
status: done
source: some/path
unresolved_blockers: 0
---

# Plan: Test
"""
        findings = auto_verify.check_status_header(plan)
        assert len(findings) == 1
        assert findings[0]["priority"] == "HIGH"


# =============================================================================
# Test: check_plan_purity
# =============================================================================


class TestPlanPurity:
    """Test that raw findings don't leak into plan artifact."""

    def test_raw_findings_header_detected(self) -> None:
        """Raw findings headers are blocked."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Problem.

## Adversarial Findings

| ID | Severity | Finding |
|----|----------|---------|
| 1  | HIGH     | Issue   |
"""
        findings = auto_verify.check_plan_purity(plan)
        assert len(findings) > 0
        assert findings[0]["priority"] == "HIGH"

    def test_verification_results_detected(self) -> None:
        """Verification result tables are blocked."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Problem.

## Verification Results

auto_verify: READY
"""
        findings = auto_verify.check_plan_purity(plan)
        assert len(findings) > 0

    def test_blocker_high_headers_detected(self) -> None:
        """### BLOCKER and ### HIGH subheaders are blocked."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Problem.

### BLOCKER

Must fix this.
"""
        findings = auto_verify.check_plan_purity(plan)
        assert len(findings) > 0

    def test_pure_plan_passes(self) -> None:
        """Plan without findings tables passes purity check."""
        plan = """---
status: draft
---

# Plan: Real Plan

## Problem

Real problem with concrete details.

## Context

Real context.

## Solution

Real solution.

## Implementation Plan

**TASK-001**: Real task
- Action: Do real work
- Acceptance:
  - Real acceptance criteria

## Risks, Success Criteria, Dependencies

Real risks.
"""
        findings = auto_verify.check_plan_purity(plan)
        assert len(findings) == 0


# =============================================================================
# Test: check_status_readiness (contradiction)
# =============================================================================


class TestStatusReadiness:
    """Test contradiction check: implementation-ready with unresolved blockers."""

    def test_claims_ready_but_has_high_findings(self) -> None:
        """implementation-ready with HIGH findings is a contradiction."""
        plan = """---
status: implementation-ready
---

# Plan: Test

## Problem

Problem.
"""
        findings = [
            {"id": "TEST-001", "priority": "HIGH", "title": "Test issue"},
        ]
        contradictions = auto_verify.check_status_readiness(plan, findings)
        assert len(contradictions) == 1
        assert contradictions[0]["id"] == "CONTRADICTION-001"
        assert contradictions[0]["priority"] == "HIGH"

    def test_claims_ready_with_no_findings_passes(self) -> None:
        """implementation-ready with no findings passes."""
        plan = """---
status: implementation-ready
---

# Plan: Test

## Problem

Problem.
"""
        contradictions = auto_verify.check_status_readiness(plan, [])
        assert len(contradictions) == 0

    def test_draft_with_high_findings_passes(self) -> None:
        """draft status with HIGH findings is not a contradiction."""
        plan = """---
status: draft
---

# Plan: Test
"""
        findings = [
            {"id": "TEST-001", "priority": "HIGH", "title": "Test issue"},
        ]
        contradictions = auto_verify.check_status_readiness(plan, findings)
        assert len(contradictions) == 0


# =============================================================================
# Test: contract-sensitive plan enforcement
# =============================================================================


class TestContractSensitiveReadiness:
    """Test matrix shape and authority-drift checks for contract-sensitive plans."""

    def test_open_questions_blocker_detected(self) -> None:
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 1
---

# Plan: Contract-sensitive

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

| Phase | Test |
|-------|------|
| 1 | pytest |

## Contract Authority Reference

**Contract-sensitive:** YES

## Contract Boundary Matrix

| Boundary | Contract authority packet | Producer | Consumer | Input schema | Output schema | Required fields | Freshness authority | Invalidation trigger | Failure behavior | Packet alignment | Test binding |
|----------|---------------------------|----------|----------|--------------|---------------|-----------------|--------------------|----------------------|------------------|-----------------|--------------|
| plan-artifact | boundary_id: plan-artifact | /planning | /code | in | out | goals | plan file | new write | Blocking gate in /planning before implementation-ready; blocker for /code and /verify | Exact match to CAP | integration:test-plan |

## Assumptions/Defaults

Defaults.

## Open Questions

| Question | Impact | Blocker? |
|----------|--------|----------|
| Does harness read enforcement field? | Phase 2 blocking | **BLOCKER-1** |
"""
        findings = auto_verify.check_open_question_blockers(plan)
        assert len(findings) == 1
        assert findings[0]["id"] == "OPEN-QUESTION-002"

    def test_missing_contract_matrix_fields_detected(self) -> None:
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Contract-sensitive

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

| Phase | Test |
|-------|------|
| 1 | pytest |

## Contract Authority Reference

**Contract-sensitive:** YES

## Contract Boundary Matrix

| Boundary | Producer | Consumer | Input schema | Output schema | Required fields | Freshness authority | Invalidation trigger | Failure behavior | Packet alignment |
|----------|----------|----------|--------------|---------------|-----------------|--------------------|----------------------|------------------|-----------------|
| plan-artifact | /planning | /code | in | out | goals | plan file | new write | advisory warning | Exact match to CAP |

## Assumptions/Defaults

Defaults.

## Open Questions

None.
"""
        findings = auto_verify.check_contract_boundary_matrix(plan)
        assert len(findings) == 1
        assert findings[0]["id"] == "CONTRACT-MATRIX-002"
        assert "Contract authority packet" in findings[0]["description"]
        assert "Test Binding" in findings[0]["description"]

    def test_plan_artifact_authority_drift_detected(self) -> None:
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Contract-sensitive

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

| Phase | Test |
|-------|------|
| 1 | pytest |

## Contract Authority Reference

**Contract-sensitive:** YES

## Contract Boundary Matrix

| Boundary | Contract authority packet | Producer | Consumer | Input schema | Output schema | Required fields | Freshness authority | Invalidation trigger | Failure behavior | Packet alignment | Test binding |
|----------|---------------------------|----------|----------|--------------|---------------|-----------------|--------------------|----------------------|------------------|-----------------|--------------|
| plan-artifact | boundary_id: plan-artifact | /planning | /code, /verify | Plan artifact schema | Plan artifact | goals, tasks, acceptance_criteria | Plan file | New plan version written by /planning | Blocker for /code and /verify; advisory warning in /planning | Exact match to CAP | contract:test |

## Assumptions/Defaults

Defaults.

## Open Questions

None.
"""
        findings = auto_verify.check_planning_contract_authority_drift(plan)
        assert len(findings) == 1
        assert findings[0]["id"] == "AUTHORITY-DRIFT-001"


# =============================================================================
# Test: check_section_completeness
# =============================================================================


class TestSectionCompleteness:
    """Test required sections are present."""

    def test_all_required_sections_present(self) -> None:
        """Plan with all required sections passes."""
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Complete

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
"""
        findings = auto_verify.check_section_completeness(plan)
        section_findings = [f for f in findings if f["id"].startswith("SECTION-")]
        assert len(section_findings) == 0

    def test_missing_problem_section(self) -> None:
        """Missing Goal section is detected."""
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Incomplete

## Current State with Evidence

Context.
"""
        findings = auto_verify.check_section_completeness(plan)
        assert any("Goal" in f["title"] for f in findings)


# =============================================================================
# Test: check_solo_dev_violations
# =============================================================================


class TestSoloDevViolations:
    """Test solo-dev constraint violations."""

    def test_team_coordination_detected(self) -> None:
        """team coordination pattern is detected."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Problem requires team coordination.
"""
        findings = auto_verify.check_solo_dev_violations(plan)
        assert len(findings) > 0

    def test_stakeholder_approval_detected(self) -> None:
        """stakeholder approval pattern is detected."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Needs stakeholder approval.
"""
        findings = auto_verify.check_solo_dev_violations(plan)
        assert len(findings) > 0

    def test_negation_excludes_false_positive(self) -> None:
        """'no team coordination' does not trigger violation."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

This is solo work with no team coordination needed.
"""
        findings = auto_verify.check_solo_dev_violations(plan)
        # Should not have team coordination finding
        team_findings = [f for f in findings if "team" in f["title"].lower()]
        assert len(team_findings) == 0


# =============================================================================
# Test: RTM coverage
# =============================================================================


class TestRTM:
    """Test requirements traceability."""

    def test_no_tasks_blocked(self) -> None:
        """No tasks in implementation plan is HIGH priority."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Problem with requirements:
1. Requirement one
2. Requirement two

## Context

Context.

## Existing Implementation

Impl.

## Test Coverage

Tests.

## Solution

Solution.

## Implementation Plan

No tasks defined.

## Risks, Success Criteria, Dependencies

Risks.
"""
        requirements = auto_verify.extract_requirements(plan)
        tasks = auto_verify.extract_tasks(plan)
        findings = auto_verify.check_rtm_coverage(requirements, tasks)
        assert any(f["id"] == "RTM-005" for f in findings)

    def test_tasks_without_acceptance_detected(self) -> None:
        """Tasks without acceptance criteria are flagged."""
        plan = """---
status: draft
---

# Plan: Test

## Problem

Problem.

## Context

Context.

## Existing Implementation

Impl.

## Test Coverage

Tests.

## Solution

Solution.

## Implementation Plan

**TASK-001**: Task without acceptance

## Risks, Success Criteria, Dependencies

Risks.
"""
        requirements = auto_verify.extract_requirements(plan)
        tasks = auto_verify.extract_tasks(plan)
        findings = auto_verify.check_rtm_coverage(requirements, tasks)
        assert any(f["id"] == "RTM-003" for f in findings)

    def test_acceptance_criteria_with_bold_colon_inside_is_recognized(self) -> None:
        """Bold acceptance headers with colon inside the emphasis count."""
        plan = """---
status: draft
---

# Plan: Test

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Valid task
- Action: Do real work
**Acceptance Criteria:**
- Result is correct

## Test Matrix

Tests.

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        tasks = auto_verify.extract_tasks(plan)
        assert tasks[0]["has_acceptance_criteria"] is True

    def test_acceptance_placeholder_body_does_not_count(self) -> None:
        """Acceptance placeholders should not satisfy RTM-003."""
        plan = """---
status: draft
---

# Plan: Test

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Placeholder task
- Action: Do real work
- Acceptance:
  - TBD

## Test Matrix

Tests.

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        tasks = auto_verify.extract_tasks(plan)
        assert tasks[0]["has_acceptance_criteria"] is False

    def test_goal_paragraph_falls_back_to_single_requirement(self) -> None:
        """A substantial Goal paragraph should become a requirement even without bullets."""
        plan = """---
status: draft
---

# Plan: Test

## Goal

Add a provider adapter for a local model backend without changing the public protocol.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Valid task
- Action: Do real work
- Acceptance:
  - Result is correct

## Test Matrix

Tests.

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        requirements = auto_verify.extract_requirements(plan)
        assert requirements == [
            {
                "id": "REQ-001",
                "text": "Add a provider adapter for a local model backend without changing the public protocol.",
            }
        ]

    def test_task_block_blank_lines_do_not_hide_acceptance(self) -> None:
        """Blank lines inside a task block should not truncate acceptance parsing."""
        plan = """---
status: draft
---

# Plan: Test

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Valid task

**File:** `src/example.py`

- Action: Do real work
- Acceptance:
  - Result is correct

## Test Matrix

Tests.

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        tasks = auto_verify.extract_tasks(plan)
        assert tasks[0]["has_acceptance_criteria"] is True


# =============================================================================
# Test: full verify_plan integration
# =============================================================================


class TestVerifyPlanIntegration:
    """Integration tests for verify_plan."""

    def test_plan_with_placeholders_blocked(self, tmp_path: Path) -> None:
        """Plan with placeholders is BLOCKED."""
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

**TASK-001**: Do something
- Action: Do it
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Risks.

## Open Questions

Need to confirm perf threshold.
"""
        plan_file = tmp_path / "bad-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"
        placeholder_findings = [f for f in result["action_items"] if f["category"] == "placeholder"]
        assert len(placeholder_findings) > 0

    def test_pure_plan_with_acceptance_ready(self, tmp_path: Path) -> None:
        """Pure plan with acceptance criteria is READY."""
        plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Good Plan

## Goal

The search indexing has a race condition that causes data corruption.

## Current State with Evidence

Two terminals writing simultaneously corrupt the index.

## Design Decisions and Invariants

Use file locking on writes and keep read paths unlocked.

## Implementation Changes

**TASK-001**: Add file lock to search_index.py
- Action: Wrap index write in FileLock context
- Acceptance:
  - test_concurrent_write passes reliably
  - No performance regression >10%

## Test Matrix

test_search_index.py::test_concurrent_write fails intermittently.

## Assumptions/Defaults

Risk: lock overhead on write-heavy workloads.
Acceptance: <10% latency increase.

## Open Questions

None.
"""
        plan_file = tmp_path / "good-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )
        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "READY", f"Should be READY but got: {result['action_items']}"

    def test_contradiction_blocks_ready(self, tmp_path: Path) -> None:
        """implementation-ready with unresolved findings is BLOCKED."""
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

Need to clarify.
"""
        plan_file = tmp_path / "contradiction-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text(
            '[{"id":"LOGIC-001","severity":"HIGH","description":"Example"}]',
            encoding="utf-8",
        )
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n| LOGIC-001 | deferred | Follow-up |\n",
            encoding="utf-8",
        )
        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"

    def test_explicit_stateless_provider_plan_skips_state_model_gates(self, tmp_path: Path) -> None:
        """Provider plans with explicit stateless declaration should not trip stateful-only gates."""
        plan = """---
status: draft
source: some/adr.md
unresolved_blockers: 0
---

# Plan: LocalModelProvider

## Goal

Add a provider adapter for a local model backend.

## Current State with Evidence

The provider protocol expects an analyze(video_id, video_url) method.

## Design Decisions and Invariants

Use a stateless HTTP client implementation.

## State Model Contracts

**This plan is NOT stateful.** Each analyze call is independent, there is no shared mutable state, and no persistence.

- **identity model**: Not applicable
- **ordering contract**: Not applicable
- **dedupe contract**: Not applicable
- **freshness/invalidation contract**: Not applicable
- **event source of truth**: Not applicable
- **isolation boundary**: Call-scoped isolation

## Implementation Changes

**TASK-001**: Add provider
- Action: Implement the provider class
- Acceptance:
  - Provider returns the expected result shape

## Test Matrix

pytest tests/test_provider.py

## Assumptions/Defaults

No shared state at this layer.

## Open Questions

None.
"""
        plan_file = tmp_path / "stateless-provider-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        state_findings = [f for f in result["action_items"] if f["id"].startswith("STATE-")]
        assert not state_findings, state_findings
        assert result["status"] == "READY", result["action_items"]

    def test_stateless_plan_with_real_state_signals_is_blocked(self, tmp_path: Path) -> None:
        """Stateless declarations cannot hide real stateful semantics."""
        plan = """---
status: draft
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Contradictory Stateless Plan

## Goal

Add a provider router with persistent identity semantics.

## Current State with Evidence

The pipeline will route between providers and persist provider_instance_id per session.

## Design Decisions and Invariants

Use provider_instance_id plus session_id for replay and source of truth.

## State Model Contracts

**This plan is NOT stateful.** Each request is stateless.

- **identity model**: provider_instance_id + session_id
- **event source of truth**: provider event log

## Implementation Changes

**TASK-001**: Add router
- Action: Implement routing
- Acceptance:
  - Routing works

## Test Matrix

pytest tests/test_router.py

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "contradictory-stateless-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        assert any(f["id"] == "STATE-004" for f in result["action_items"]), result["action_items"]

    def test_provider_coordination_signals_still_trigger_state_model_checks(self, tmp_path: Path) -> None:
        """Provider coordination plans should still be treated as stateful."""
        plan = """---
status: draft
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Provider Coordination

## Goal

Add multi-provider routing with persistent provider identities.

## Current State with Evidence

The router will coordinate a fallback chain across providers.

## Design Decisions and Invariants

Use provider_instance_id to track provider routing decisions across the fallback chain.

## Implementation Changes

**TASK-001**: Add router
- Action: Implement routing
- Acceptance:
  - Routing works

## Test Matrix

pytest tests/test_router.py

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "provider-coordination-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        assert any(f["id"] == "STATE-001" for f in result["action_items"]), result["action_items"]

    def test_infers_phase_ready_through_from_deferred_blockers(self, tmp_path: Path) -> None:
        """Deferred blocker phases should produce bounded readiness for early execution."""
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 2
---

# Plan: Phased Rollout

## Goal

1. Implement a phased rollout safely.

## Current State with Evidence

Phases 2 and 3 are gated by deferred blockers.

## Design Decisions and Invariants

Phase 1 is allowed to proceed first.

## Implementation Changes

### Phase 1: Foundation

**TASK-001**: Implement phased rollout foundation
- Action: Do early work
- Acceptance:
  - phase 1 passes

### Phase 2: Blocking Integration

**TASK-002**: Implement phased rollout integration
- Action: Do later work
- Acceptance:
  - phase 2 passes

### Phase 3: Finalization

**TASK-003**: Implement phased rollout finalization
- Action: Finish rollout
- Acceptance:
  - phase 3 passes

## Test Matrix

phase1_test.py::test_phase_1

## Assumptions/Defaults

None.

## Deferred Blockers

| Blocker | Phase | Rationale | Resolution |
|---------|-------|-----------|-----------|
| BLOCKER-1 | Phase 2 | Needs extra wiring | Later |
| BLOCKER-2 | Phase 3 | Needs final proof | Later |

## Open Questions

None.
"""
        plan_file = tmp_path / "phased-rollout-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "READY", result["action_items"]
        assert result["readiness"]["phase_ready_through"] == 1

    def test_infers_phase_ready_through_from_phase_preconditions(self, tmp_path: Path) -> None:
        """Legacy phaseN_preconditions metadata should map to bounded readiness."""
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 2
phase3_preconditions: 2
---

# Plan: Frontmatter Phased Rollout

## Goal

1. Implement a phased rollout safely.

## Current State with Evidence

Phase 3 is gated on explicit preconditions.

## Design Decisions and Invariants

Phases 1 and 2 are allowed to proceed first.

## Implementation Changes

### Phase 1: Foundation

**TASK-001**: Implement phased rollout foundation
- Action: Do early work
- Acceptance:
  - phase 1 passes

### Phase 2: Integration

**TASK-002**: Implement phased rollout integration
- Action: Do intermediate work
- Acceptance:
  - phase 2 passes

### Phase 3: Finalization

**TASK-003**: Implement phased rollout finalization
- Action: Finish rollout
- Acceptance:
  - phase 3 passes

## Test Matrix

phase2_test.py::test_phase_2

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "frontmatter-phased-rollout-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        plan_file.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
        plan_file.with_suffix(".review.summary.md").write_text(
            "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "READY", result["action_items"]
        assert result["readiness"]["phase_ready_through"] == 2

    def test_missing_disposition_artifacts_block_ready(self, tmp_path: Path) -> None:
        """implementation-ready without review artifacts is BLOCKED."""
        plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Ready Plan

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Task
- Action: Do
- Acceptance:
  - Done

## Test Matrix

Tests.

## Assumptions/Defaults

Assume default config.

## Open Questions

None.
"""
        plan_file = tmp_path / "missing-disposition-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "BLOCKED"
        assert any(f["id"] == "DISPOSITION-002" for f in result["action_items"])

    def test_organizational_restructure_plan_with_not_applicable_sections_is_not_stateful_or_contract_sensitive(
        self, tmp_path: Path
    ) -> None:
        """Structural plans should honor explicit negative declarations and heading-style tasks."""
        plan = """---
status: draft
source: some/adr.md
unresolved_blockers: 0
---

# Plan: SDLC Group Package

## Goal

Restructure the SDLC skill cluster to share a canonical package via junction points.

## Current State with Evidence

Current skills import shared primitives through sys.path hacks.

## Design Decisions and Invariants

Use Windows junction points and keep skill behavior unchanged.

## Implementation Changes

### TASK-001: Create package directory

- Action: Create the package root
**Acceptance Criteria:**
- Directory exists

### TASK-002: Migrate shared package

- Action: Move the shared package under the SDLC parent
**Acceptance Criteria:**
- Files exist at the new path

## Test Matrix

pytest P:/packages/cc-skills-sdlc/contract-primitives/tests/

## Contract Authority Reference

**Contract-sensitive:** NO — this is a structural/organizational decision, not a producer/consumer boundary change.

## Contract Boundary Matrix

**Not applicable** — this plan does not create, change, or remove producer/consumer boundaries. Existing boundaries such as handoff-envelope, evidence-artifact, plan-artifact, and hook-output are untouched.

## State-Model Contracts

**Not applicable** — this plan does not touch persistence, history, stale-data immunity, or event-source boundaries.

## Assumptions/Defaults

Windows junctions are available in this environment.

## Open Questions

None.
"""
        plan_file = tmp_path / "organizational-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "READY", result["action_items"]
        ids = {finding["id"] for finding in result["action_items"]}
        assert "STATE-001" not in ids
        assert "CONTRACT-MATRIX-001" not in ids
        assert "AMBIGUITY-001" not in ids
        assert "RTM-005" not in ids

    def test_structural_restructure_plan_ignores_negative_sections_and_rollback_restore_text(
        self, tmp_path: Path
    ) -> None:
        """Rollback instructions should not make a stateless structural plan look stateful."""
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 0
---

# Plan: SDLC Group Package

## Goal

Restructure the SDLC skill cluster to share a canonical package via junction points.

## Current State with Evidence

Current skills import shared primitives through sys.path hacks.

## Design Decisions and Invariants

Use Windows junction points and keep skill behavior unchanged.

## Implementation Changes

### TASK-001: Migrate shared package

- Action: Move the package to its new parent directory.
**Acceptance Criteria:**
- Package exists at the new location

**Rollback (if TASK-007 fails):** Move source back to `P:/packages/contract-primitives/`, restore original directory.

### TASK-002: Create junctions

- Action: Link the old skill paths to the new package layout.
**Acceptance Criteria:**
- Junctions resolve correctly

## Test Matrix

| Test | Coverage | Run By |
|------|----------|--------|
| TASK-002 | Junction resolution | Developer |

## Contract Authority Reference

**Contract-sensitive:** NO — this is a structural/organizational decision, not a producer/consumer boundary change.

## Contract Boundary Matrix

**Not applicable** — this plan does not create, change, or remove producer/consumer boundaries. Existing boundaries such as handoff-envelope, evidence-artifact, plan-artifact, and hook-output are untouched.

## State-Model Contracts

**Not applicable** — this plan does not touch persistence, history, multi-terminal state, stale-data immunity, or event-source boundaries. It is a pure directory restructure.

## Assumptions/Defaults

Windows junctions are available in this environment.

## Open Questions

None.
"""
        plan_file = tmp_path / "structural-restructure-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        assert result["status"] == "READY", result["action_items"]
        ids = {finding["id"] for finding in result["action_items"]}
        assert "STATE-001" not in ids
        assert "AMBIGUITY-001" not in ids
        assert result["summary"]["tasks_found"] == 2

    def test_real_boundary_table_overrides_negative_contract_sensitive_declaration(
        self, tmp_path: Path
    ) -> None:
        """A real boundary matrix table cannot be hidden by saying contract-sensitive NO."""
        plan = """---
status: draft
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Boundary Drift

## Goal

Change the plan artifact contract.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Update boundary
- Action: Rewrite the contract row
- Acceptance:
  - Contract row updated

## Test Matrix

contract:test

## Contract Authority Reference

**Contract-sensitive:** NO

## Contract Boundary Matrix

| Boundary | Contract authority packet | Producer | Consumer | Input schema | Output schema | Required fields | Freshness authority | Invalidation trigger | Failure behavior | Packet alignment | Test binding |
|----------|---------------------------|----------|----------|--------------|---------------|-----------------|--------------------|----------------------|------------------|-----------------|--------------|
| plan-artifact | boundary_id: plan-artifact | /planning | /code | in | out | goals | plan file | new write | advisory warning | Exact match to CAP | contract:test |

## Assumptions/Defaults

Defaults.

## Open Questions

None.
"""
        plan_file = tmp_path / "negative-contract-sensitive-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        ids = {finding["id"] for finding in result["action_items"]}
        assert "CONTRACT-DECL-001" in ids

    def test_contradictory_review_summary_is_marked_stale(self, tmp_path: Path) -> None:
        """auto_verify should stamp stale summaries when they contradict the current result."""
        plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Structural

## Goal

Move files into the new directory layout without changing behavior.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Keep behavior unchanged.

## Implementation Changes

### TASK-001: Move files

- Action: Move files.
**Acceptance Criteria:**
- Files moved

## Test Matrix

| Test | Coverage | Run By |
|------|----------|--------|
| TASK-001 | File move | Developer |

## Contract Authority Reference

**Contract-sensitive:** NO

## Contract Boundary Matrix

**Not applicable** — structural only.

## State-Model Contracts

**Not applicable** — structural only.

## Assumptions/Defaults

Defaults.

## Open Questions

None.
"""
        plan_file = tmp_path / "stale-summary-plan.md"
        plan_file.write_text(plan, encoding="utf-8")
        sibling_summary = plan_file.with_suffix(".review.summary.md")
        sibling_summary.write_text(
            "## Status: draft (blocked by auto_verify false positives)\n\nThis plan is ready for implementation.\n",
            encoding="utf-8",
        )
        adversarial_dir = tmp_path / "adversarial"
        adversarial_dir.mkdir()
        adversarial_summary = adversarial_dir / f"{plan_file.stem}.review.summary.md"
        adversarial_summary.write_text(
            "## Status: draft (blocked by auto_verify false positives)\n\nThis plan is ready for implementation.\n",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        summary_text = sibling_summary.read_text(encoding="utf-8")
        adversarial_text = adversarial_summary.read_text(encoding="utf-8")

        assert result["status"] == "READY", result["action_items"]
        assert result["artifact_consistency"]["stale_review_summary"] is True
        assert "STALE REVIEW ARTIFACT" in summary_text
        assert "STALE REVIEW ARTIFACT" in adversarial_text


class TestAdrIngestionRouting:
    """ADR-derived drafts should be canonicalized locally before /arch routing."""

    def test_shallow_adr_transcription_stays_local_to_planning(self, tmp_path: Path) -> None:
        adr = tmp_path / "arch_decisions" / "003-example.md"
        adr.parent.mkdir()
        adr.write_text(
            """# ADR-003: Example

## Context

Example context.

## Design

Example design.

## Contract Boundaries

| Boundary | Producer | Consumer |
|----------|----------|----------|
| cache | A | B |

## Implementation Sequence

| Order | Component |
|-------|-----------|
| 1 | Do the thing |
""",
            encoding="utf-8",
        )

        plan = f"""# Plan: Example

**Source ADR:** `{adr}`
**Status:** draft
**Unresolved blockers:** 0 (pre-verification)

## Context

Copied ADR context.

## Design

Copied ADR design.

## Implementation Tasks

## Contract Boundary Matrix

| Boundary | Producer | Consumer | Required Fields |
|----------|----------|----------|-----------------|
| cache | A | B | key |
"""
        plan_file = tmp_path / "plan-example.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        finding_ids = {finding["id"] for finding in result["action_items"]}
        categories = {finding["category"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert result["next_action"]["type"] == "fix_issues"
        assert "ADR-INGEST-001" in finding_ids
        assert "state_model" not in categories
        assert "contract_ambiguity" not in categories


class TestSourceIngestionRouting:
    """Non-ADR source artifacts should normalize locally before other routing."""

    def test_current_adr_artifact_is_treated_as_local_normalization_issue(
        self, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "arch_decisions"
        source_dir.mkdir()
        plan_file = source_dir / "ADR-20260407-example.md"
        plan_file.write_text(
            """# ADR: Example implementation

## Goal

Deliver a stateful workflow improvement.

## Current State with Evidence

Current implementation has no explicit source-of-truth contract.

## Design Decisions and Invariants

The workflow uses replay and handoff semantics across runs.

## Implementation Changes

**TASK-001**: Add the new workflow
- Action: Implement it
- Acceptance:
  - Workflow runs

## Contract Boundary Matrix

| Boundary | Producer | Consumer | Required Fields |
|----------|----------|----------|-----------------|
| state | /plan | /code | task_id |

## Test Matrix

pytest tests/test_example.py

## Assumptions/Defaults

None.

## Open Questions

None.
""",
            encoding="utf-8",
        )

        result = auto_verify.verify_plan(str(plan_file))
        finding_ids = {finding["id"] for finding in result["action_items"]}
        categories = {finding["category"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert result["next_action"]["type"] == "fix_issues"
        assert "ADR-INGEST-001" in finding_ids
        assert "state_model" not in categories
        assert "schema_consistency" not in categories

    def test_solution_notes_with_source_packet_stay_local_to_planning(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "solution-notes.md"
        source.write_text(
            """# Solution Notes

```yaml
planning_source_packet:
  packet_version: "1"
  source_path: "notes/solution-notes.md"
  source_kind: "solution-notes"
  plan_title: "Normalize Notes"
  goal: "Turn solution notes into a canonical implementation plan."
  implementation_changes:
    - task_id: "TASK-001"
```

## Background

Source context.

## Proposed Flow

Implementation sketch.
""",
            encoding="utf-8",
        )

        plan = f"""# Plan: Normalize Notes

**Source:** `{source}`
**Status:** draft
**Unresolved blockers:** 0 (pre-verification)

## Background

Copied notes.

## Proposed Flow

Copied source structure.
"""
        plan_file = tmp_path / "plan-notes.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        finding_ids = {finding["id"] for finding in result["action_items"]}
        categories = {finding["category"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert result["next_action"]["type"] == "fix_issues"
        assert "SOURCE-INGEST-001" in finding_ids
        assert "state_model" not in categories
        assert "contract_ambiguity" not in categories


class TestExecutionSemanticsAndEvidence:
    """Execution-policy and evidence-reference checks."""

    def test_explicit_file_reference_must_exist(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Evidence Check

## Goal

Tighten a hook.

## Current State with Evidence

**File:** `missing_module.py`
**Lines:** 10-20

The current implementation needs refinement.

## Design Decisions and Invariants

Keep behavior unchanged.

## Implementation Changes

**TASK-001**: Update evidence-driven code path
- Action: Edit the existing implementation.
**Acceptance Criteria:**
- Existing code path updated safely

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "evidence-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        ids = {finding["id"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert "EVIDENCE-001" in ids

    def test_explicit_line_reference_must_be_in_range(self, tmp_path: Path) -> None:
        source_file = tmp_path / "existing_module.py"
        source_file.write_text("one\ntwo\nthree\n", encoding="utf-8")
        plan = f"""---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Stale Lines

## Goal

Tighten a hook.

## Current State with Evidence

**File:** `{source_file}`
**Lines:** 9-12

Current behavior is described here.

## Design Decisions and Invariants

Keep behavior unchanged.

## Implementation Changes

**TASK-001**: Update evidence-driven code path
- Action: Edit the existing implementation.
**Acceptance Criteria:**
- Existing code path updated safely

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "stale-lines-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        ids = {finding["id"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert "EVIDENCE-002" in ids

    def test_layered_plan_requires_explicit_execution_semantics(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Layer Semantics

## Goal

Improve navigator safety.

## Current State with Evidence

Current behavior is manual.

## Design Decisions and Invariants

Layer 1 performs lexical routing.

Layer 2 uses sequential thinking for deeper analysis.

## Implementation Changes

**TASK-001**: Implement layered navigation
- Action: Wire the layered flow.
**Acceptance Criteria:**
- Layers run in the intended order

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "layer-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        ids = {finding["id"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert result["next_action"]["nested_subworkflow"] is True
        assert result["next_action"]["resume_skill"] == "/planning"
        assert result["next_action"]["resume_policy"] == "automatic_return_to_caller"
        assert result["next_action"]["user_reentry_required"] is False
        assert "EXECUTION-001" in ids

    def test_vague_conditional_layer_requires_trigger_signal(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Conditional Layer

## Goal

Improve navigator safety.

## Current State with Evidence

Current behavior is manual.

## Design Decisions and Invariants

Layer 3 runs only if needed after Layers 1 and 2.

## Implementation Changes

**TASK-001**: Implement conditional escalation
- Action: Wire the escalation path.
**Acceptance Criteria:**
- Escalation occurs only under the intended signal

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "conditional-layer-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        ids = {finding["id"] for finding in result["action_items"]}

        assert result["status"] == "BLOCKED"
        assert result["next_action"]["type"] == "invoke_arch_then_rewrite_plan"
        assert "EXECUTION-002" in ids

    def test_defined_trigger_signal_passes_execution_checks(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Conditional Layer

## Goal

Improve navigator safety.

## Current State with Evidence

Current behavior is manual.

## Design Decisions and Invariants

Layer 2 is advisory and runs after Layer 1.

Layer 3 is optional fallback-only. Trigger: run Layer 3 only when both Layer 1 and Layer 2 fail to classify the request within one pass.

## Implementation Changes

**TASK-001**: Implement conditional escalation
- Action: Wire the escalation path.
**Acceptance Criteria:**
- Escalation occurs only under the stated trigger

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        plan_file = tmp_path / "well-specified-layer-plan.md"
        plan_file.write_text(plan, encoding="utf-8")

        result = auto_verify.verify_plan(str(plan_file))
        ids = {finding["id"] for finding in result["action_items"]}

        assert "EXECUTION-001" not in ids
        assert "EXECUTION-002" not in ids

    def test_existing_mode_system_overlap_requires_explicit_coexistence_or_replacement(
        self, tmp_path: Path
    ) -> None:
        hook_file = tmp_path / "StopHook_sequential_thinking.py"
        hook_file.write_text(
            '_INVESTIGATION_PHASES = ("hypotheses", "testing", "conclusion")\n'
            'if mode == "investigation":\n'
            "    return None\n",
            encoding="utf-8",
        )
        plan = f"""---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Multi Hypothesis Tracking

## Goal

Add a multi-hypothesis workflow to the existing sequential thinking flow.

## Current State with Evidence

**File:** `{hook_file}`

The current stop hook already supports a separate alternate flow.

## Design Decisions and Invariants

Route `current_iteration == 0` to multi_hypothesis mode, `current_iteration == 1` to critique mode, and `current_iteration == 2` to resolution mode.

## Implementation Changes

**TASK-001**: Extend iteration mapping
- Action: Add the new mode transitions.
**Acceptance Criteria:**
- The new mapping is active

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Happy path only | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        findings = auto_verify.check_existing_flow_overlap(plan)
        assert any(f["id"] == "STATE-010" for f in findings), findings

    def test_hook_visible_field_requires_provenance_contract(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Hook Visible Fields

## Goal

Extend the sequential thinking state safely.

## Current State with Evidence

The workflow already stores session_id and current_iteration across turns.

## Design Decisions and Invariants

Add `hypothesis_mode`: false to session state.
Add `hypotheses`: [] to session state.
StopHook reads `hypothesis_details` during resolution.
current_iteration == 0 enters multi_hypothesis mode.

## Implementation Changes

**TASK-001**: Extend state handling
- Action: Update hook reads and writes.
**Acceptance Criteria:**
- New fields are available during the hypothesis flow

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Happy path only | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        findings = auto_verify.check_state_extension_contracts(plan)
        ids = {finding["id"] for finding in findings}
        assert "STATE-011" in ids
        assert "STATE-012" in ids
        assert "STATE-013" in ids

    def test_stateful_extension_requires_failure_mode_tests(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Stateful Failure Modes

## Goal

Add a hypothesis workflow to the stateful sequential thinking loop.

## Current State with Evidence

The loop stores session_id and intermediate_answers between turns.

## Design Decisions and Invariants

Add `hypothesis_mode`: false to session state.
When `hypothesis_mode` is true, current_iteration selects the hypothesis flow.

## Implementation Changes

**TASK-001**: Extend state handling
- Action: Update hook reads and writes.
**Acceptance Criteria:**
- New fields are available during the hypothesis flow

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Happy path only | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        findings = auto_verify.check_stateful_failure_mode_tests(plan)
        assert any(f["id"] == "TEST-STATE-002" for f in findings), findings

    def test_well_specified_state_extension_avoids_new_state_extension_findings(
        self, tmp_path: Path
    ) -> None:
        hook_file = tmp_path / "StopHook_sequential_thinking.py"
        hook_file.write_text(
            '_INVESTIGATION_PHASES = ("hypotheses", "testing", "conclusion")\n'
            'if mode == "investigation":\n'
            "    return None\n",
            encoding="utf-8",
        )
        plan = f"""---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Well Specified Hypothesis Flow

## Goal

Add a hypothesis workflow without breaking the existing investigation flow.

## Current State with Evidence

**File:** `{hook_file}`

The current hook already exposes an investigation flow that remains available.

## Design Decisions and Invariants

The existing investigation mode remains unchanged. The new hypothesis flow coexists with it and is selected only when `hypothesis_mode` is true; otherwise the standard investigation flow remains unchanged.
Add `hypothesis_mode`: false to session state. Producer: UserPromptSubmit writes the boolean selector. Consumer: PreToolUse reads it before mode selection. Format: boolean. When `hypothesis_mode` is absent or false, stay in the standard investigation flow.
Add `hypotheses`: [] to session state. Producer: StopHook writes a structured object list parsed from the LLM response. Consumer: PreToolUse reads the list to render critique prompts. Format: structured object list. When `hypotheses` is absent, default to an empty list.
StopHook reads `hypothesis_details`. Source: parsed by StopHook from the LLM response and stored in state before hypothesis_resolution.
When `hypothesis_mode` is true, current_iteration routes 0 -> multi_hypothesis, 1 -> hypothesis_critique, 2 -> hypothesis_resolution.

## Implementation Changes

**TASK-001**: Extend state handling
- Action: Update hook reads and writes.
**Acceptance Criteria:**
- New fields are available during the hypothesis flow

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Backward compatibility with old state files | Dev |
| TASK-001 | Interruption and resume during critique phase | Dev |
| TASK-001 | TTL expiry on inactive hypothesis sessions | Dev |
| TASK-001 | Malformed hypotheses payload is rejected safely | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        overlap_ids = {finding["id"] for finding in auto_verify.check_existing_flow_overlap(plan)}
        extension_ids = {finding["id"] for finding in auto_verify.check_state_extension_contracts(plan)}
        failure_ids = {
            finding["id"] for finding in auto_verify.check_stateful_failure_mode_tests(plan)
        }

        assert "STATE-010" not in overlap_ids
        assert "STATE-011" not in extension_ids
        assert "STATE-012" not in extension_ids
        assert "STATE-013" not in extension_ids
        assert "TEST-STATE-002" not in failure_ids

    def test_change_block_component_mismatch_is_flagged(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Component Alignment

## Goal

Extend the hypothesis workflow safely.

## Current State with Evidence

Current hooks already split PreToolUse and StopHook responsibilities.

## Design Decisions and Invariants

Keep mode selection in PreToolUse and extraction in StopHook.

## Implementation Changes

**CHANGE-002**: Update StopHook extraction
- Action: Add extraction for hypotheses.

**CHANGE-004**: Update StopHook transitions
- Action: Add the `is_hypothesis_mode` branch in `pre_tool_use()` so `current_iteration` selects the right mode messages.
**Acceptance Criteria:**
- Mode selection works

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| CHANGE-004 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        findings = auto_verify.check_change_component_alignment(plan)
        assert any(f["id"] == "CHANGE-ALIGN-001" for f in findings), findings

    def test_parser_dependent_state_requires_failure_policy(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Parser Robustness

## Goal

Track multiple hypotheses in state.

## Current State with Evidence

The workflow stores session_id and intermediate_answers between turns.

## Design Decisions and Invariants

Add `hypotheses`: [] to session state.
Extract hypotheses from the LLM response by pattern-matching H1:, H2:, and H3: prefixes.

## Implementation Changes

**TASK-001**: Parse hypotheses
- Action: Add regex extraction from the response.
**Acceptance Criteria:**
- Hypotheses are captured

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Happy path only | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        findings = auto_verify.check_parser_failure_policy(plan)
        assert any(f["id"] == "STATE-014" for f in findings), findings

    def test_undefined_helper_reference_is_flagged(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Helper Clarity

## Goal

Render hypothesis context.

## Current State with Evidence

Current implementation renders investigation feedback.

## Design Decisions and Invariants

The new `_format_hypothesis_context(hypotheses)` helper will be used in prompt assembly.

## Implementation Changes

**TASK-001**: Update prompts
- Action: Use the helper in mode messages.
**Acceptance Criteria:**
- Prompts include the hypothesis context

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

None.

## Open Questions

None.
"""
        findings = auto_verify.check_helper_reference_clarity(plan)
        assert any(f["id"] == "HELPER-001" for f in findings), findings

    def test_assumption_schema_contradiction_is_flagged(self, tmp_path: Path) -> None:
        plan = """---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Assumption Drift

## Goal

Track structured hypotheses.

## Current State with Evidence

The workflow stores session state between turns.

## Design Decisions and Invariants

Add `hypotheses`: [] to session state.
`hypotheses` stores structured objects like {"id": "H1", "claim": "...", "status": "active"}.

## Implementation Changes

**TASK-001**: Store structured hypotheses
- Action: Persist structured objects.
**Acceptance Criteria:**
- Structured hypotheses are persisted

## Test Matrix

| Task | Test | Owner |
|------|------|-------|
| TASK-001 | Manual | Dev |

## Assumptions/Defaults

- `hypotheses` stores plain text only.

## Open Questions

None.
"""
        findings = auto_verify.check_assumption_schema_contradictions(plan)
        assert any(f["id"] == "ASSUMPTION-001" for f in findings), findings


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
