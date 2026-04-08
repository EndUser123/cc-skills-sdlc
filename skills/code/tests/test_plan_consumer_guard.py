from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("P:/packages/contract-primitives/src")))

from contract_primitives import discover_local_plan_path, validate_plan_for_execution


def test_blocks_non_ready_plan(tmp_path: Path) -> None:
    plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 1
---

# Plan: Bad Plan

## Goal

Problem.

## Current State with Evidence

Context.

## Design Decisions and Invariants

Decision.

## Implementation Changes

**TASK-001**: Task
- Action: Do

## Test Matrix

pytest

## Assumptions/Defaults

Defaults.

## Open Questions

| Question | Impact | Blocker? |
|----------|--------|----------|
| unresolved | bad | **BLOCKER-1** |
"""
    plan_path = tmp_path / "bad-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    result = validate_plan_for_execution(str(plan_path), consumer="/code")
    assert result.allowed is False
    assert result.verify_status == "BLOCKED"


def test_allows_ready_plan_for_code(tmp_path: Path) -> None:
    plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Good Plan

## Goal

1. Implement file locking for concurrent writes.

## Current State with Evidence

Two terminals writing simultaneously corrupt the index.

## Design Decisions and Invariants

Use file locking on writes and keep read paths unlocked.

## Implementation Changes

**TASK-001**: Add file lock to search_index.py
- Action: Wrap index write in FileLock context
- Acceptance:
  - test_concurrent_write passes reliably

## Test Matrix

test_search_index.py::test_concurrent_write

## Assumptions/Defaults

Risk: lock overhead on write-heavy workloads.

## Open Questions

None.
"""
    plan_path = tmp_path / "good-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    plan_path.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
    plan_path.with_suffix(".review.summary.md").write_text(
        "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
        encoding="utf-8",
    )

    result = validate_plan_for_execution(str(plan_path), consumer="/code")
    assert result.allowed is True
    assert result.verify_status == "READY"
    assert result.claimed_status == "implementation-ready"


def test_allows_ready_plan_for_tdd_without_implementation_ready(tmp_path: Path) -> None:
    plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 0
phase_ready_through: 2
---

# Plan: Phased Ready Plan

## Goal

1. Implement a phased rollout safely.

## Current State with Evidence

There is enough evidence to begin early phases.

## Design Decisions and Invariants

Phases 1-2 are allowed before final rollout proof.

## Implementation Changes

**TASK-001**: Implement phased rollout phase 1
- Action: Do early rollout work
- Acceptance:
  - phase 1 checks pass

## Test Matrix

phase1_test.py::test_phase_1

## Assumptions/Defaults

None.

## Open Questions

None.
"""
    plan_path = tmp_path / "phased-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    plan_path.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
    plan_path.with_suffix(".review.summary.md").write_text(
        "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
        encoding="utf-8",
    )

    result = validate_plan_for_execution(
        str(plan_path),
        consumer="/tdd",
        require_implementation_ready=False,
        required_phase=1,
    )
    assert result.allowed is True
    assert result.verify_status == "READY"
    assert result.claimed_status == "in-review"


def test_allows_ready_phased_plan_for_code_phase_one(tmp_path: Path) -> None:
    plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 3
phase_ready_through: 1
---

# Plan: Phase One Ready

## Goal

1. Implement phase-bounded rollout safely.

## Current State with Evidence

Only phase 1 is ready to execute.

## Design Decisions and Invariants

Phase 2 remains blocked until additional proof exists.

## Implementation Changes

### Phase 1: Foundation

**TASK-001**: Implement phase-bounded rollout foundation
- Action: Do early rollout work
- Acceptance:
  - phase 1 checks pass

### Phase 2: Later Work

**TASK-002**: Implement phase-bounded rollout later phase
- Action: Do later rollout work
- Acceptance:
  - phase 2 checks pass

## Test Matrix

phase1_test.py::test_phase_1

## Assumptions/Defaults

None.

## Open Questions

None.
"""
    plan_path = tmp_path / "phase-one-ready-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    plan_path.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
    plan_path.with_suffix(".review.summary.md").write_text(
        "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
        encoding="utf-8",
    )

    result = validate_plan_for_execution(
        str(plan_path),
        consumer="/code",
        required_phase=1,
    )
    assert result.allowed is True
    assert result.verify_status == "READY"
    assert result.claimed_status == "in-review"
    assert result.readiness["phase_ready_through"] == 1


def test_blocks_code_when_required_phase_exceeds_validated_readiness(tmp_path: Path) -> None:
    plan = """---
status: in-review
source: some/adr.md
unresolved_blockers: 3
phase_ready_through: 1
---

# Plan: Phase One Only

## Goal

1. Implement phase-bounded rollout safely.

## Current State with Evidence

Only phase 1 is ready to execute.

## Design Decisions and Invariants

Phase 2 remains blocked until additional proof exists.

## Implementation Changes

**TASK-001**: Implement phase-bounded rollout foundation
- Action: Do early rollout work
- Acceptance:
  - phase 1 checks pass

## Test Matrix

phase1_test.py::test_phase_1

## Assumptions/Defaults

None.

## Open Questions

None.
"""
    plan_path = tmp_path / "phase-one-only-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    plan_path.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
    plan_path.with_suffix(".review.summary.md").write_text(
        "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
        encoding="utf-8",
    )

    result = validate_plan_for_execution(
        str(plan_path),
        consumer="/code",
        required_phase=2,
    )
    assert result.allowed is False
    assert "phase 2" in result.reason.lower()


def test_implementation_ready_plan_is_consumable_by_tdd(tmp_path: Path) -> None:
    plan = """---
status: implementation-ready
source: some/adr.md
unresolved_blockers: 0
---

# Plan: Fully Ready

## Goal

1. Implement complete rollout safely.

## Current State with Evidence

All phases are ready to execute.

## Design Decisions and Invariants

No later-phase blockers remain.

## Implementation Changes

**TASK-001**: Implement complete rollout work
- Action: Do the work
- Acceptance:
  - checks pass

## Test Matrix

phase1_test.py::test_phase_1

## Assumptions/Defaults

None.

## Open Questions

None.
"""
    plan_path = tmp_path / "implementation-ready-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    plan_path.with_suffix(".review.findings.json").write_text("[]", encoding="utf-8")
    plan_path.with_suffix(".review.summary.md").write_text(
        "## Finding Dispositions\n\n| Finding ID | Disposition | Rationale |\n",
        encoding="utf-8",
    )

    result = validate_plan_for_execution(
        str(plan_path),
        consumer="/tdd",
        require_implementation_ready=False,
        required_phase=1,
    )
    assert result.allowed is True
    assert result.claimed_status == "implementation-ready"


def test_discovers_project_local_plan_conservatively(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "plan.md").write_text("stub", encoding="utf-8")

    discovered = discover_local_plan_path(project_dir=str(project_dir), cwd=str(tmp_path))

    assert discovered == str(project_dir / "plan.md")
