from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Any

_ROOT = Path(__file__).resolve().parents[4]
_PLANNING_LIB = _ROOT / ".claude" / "skills" / "planning" / "__lib"
if _PLANNING_LIB.exists() and str(_PLANNING_LIB) not in sys.path:
    sys.path.insert(0, str(_PLANNING_LIB))


@dataclass(slots=True)
class PlanConsumerValidationResult:
    allowed: bool
    consumer: str
    plan_path: str
    verify_status: str
    claimed_status: str
    reason: str
    readiness: dict[str, Any] = field(default_factory=dict)
    blocking_findings: list[dict[str, Any]] = field(default_factory=list)
    next_action: dict[str, Any] = field(default_factory=dict)


def discover_local_plan_path(
    *,
    explicit_path: str | None = None,
    project_dir: str | None = None,
    cwd: str | None = None,
) -> str | None:
    """Discover a local plan artifact intended for active execution.

    This is intentionally conservative: prefer explicit or project-local plan
    paths and avoid guessing from unrelated global plan history.
    """

    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))

    project_dir = project_dir or os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = cwd or os.getcwd()

    for base in [project_dir, cwd]:
        if not base:
            continue
        root = Path(base)
        candidates.extend(
            [
                root / "plan.md",
                root / ".claude" / "plan.md",
            ]
        )

    seen: set[str] = set()
    for candidate in candidates:
        resolved = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            return str(candidate)

    return None


def validate_plan_for_execution(
    plan_path: str,
    *,
    consumer: str,
    require_implementation_ready: bool = True,
    required_phase: int | None = None,
) -> PlanConsumerValidationResult:
    """Validate a plan before `/code` or `/tdd` consumes it.

    The authoritative source is `/planning`'s `verify_plan()` result.
    Consumer-side validation does not reinterpret plan semantics locally.
    """

    from auto_verify import verify_plan  # type: ignore  # noqa: E402

    result = verify_plan(plan_path=plan_path)
    verify_status = str(result.get("status", "BLOCKED"))
    claimed_status = str(result.get("claimed_status", "draft"))
    readiness = result.get("readiness", {}) or {}
    action_items = result.get("action_items", []) or []
    next_action = result.get("next_action", {}) or {}

    if verify_status != "READY":
        return PlanConsumerValidationResult(
            allowed=False,
            consumer=consumer,
            plan_path=plan_path,
            verify_status=verify_status,
            claimed_status=claimed_status,
            readiness=readiness,
            blocking_findings=action_items,
            next_action=next_action,
            reason=(
                f"{consumer} cannot consume the plan because /planning verification is "
                f"{verify_status}. Rewrite or revalidate the plan first."
            ),
        )

    if claimed_status == "implementation-ready":
        return PlanConsumerValidationResult(
            allowed=True,
            consumer=consumer,
            plan_path=plan_path,
            verify_status=verify_status,
            claimed_status=claimed_status,
            readiness=readiness,
            next_action=next_action,
            reason="Plan is validator-ready for implementation consumption.",
        )

    if not require_implementation_ready and required_phase is None:
        return PlanConsumerValidationResult(
            allowed=True,
            consumer=consumer,
            plan_path=plan_path,
            verify_status=verify_status,
            claimed_status=claimed_status,
            readiness=readiness,
            next_action=next_action,
            reason="Plan is validator-ready for phased consumer execution.",
        )

    if required_phase is not None:
        phase_ready_through = readiness.get("phase_ready_through")
        if isinstance(phase_ready_through, int) and phase_ready_through >= required_phase:
            return PlanConsumerValidationResult(
                allowed=True,
                consumer=consumer,
                plan_path=plan_path,
                verify_status=verify_status,
                claimed_status=claimed_status,
                readiness=readiness,
                next_action=next_action,
                reason=f"Plan is validator-ready through phase {phase_ready_through}.",
            )

    if required_phase is not None:
        target = f"validated readiness through phase {required_phase}"
    else:
        target = "implementation-ready" if require_implementation_ready else "phase-gated readiness"
    return PlanConsumerValidationResult(
        allowed=False,
        consumer=consumer,
        plan_path=plan_path,
        verify_status=verify_status,
        claimed_status=claimed_status,
        readiness=readiness,
        blocking_findings=action_items,
        next_action=next_action,
        reason=(
            f"{consumer} requires {target}, but the plan claims '{claimed_status}' and does not "
            "meet the validated readiness threshold."
        ),
    )
