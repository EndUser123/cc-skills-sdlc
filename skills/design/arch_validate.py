#!/usr/bin/env python3
"""Validate contract-sensitive ADRs produced by /arch.

This keeps the authoritative Contract Authority Packet honest by validating the
packet shape, required boundary fields, and a small set of cross-skill contract
alignment rules that must not drift.

Additionally validates that the LLM actually followed the SKILL.md execution
stages (process compliance) — not just that the output packets are well-formed.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# DEPTH RULE: When skills/ layer is added, increment parents[N] by 1.
# e.g. from arch/: parents[3]→[4] (sdlc/ is 4 levels up from arch/)
_ROOT = Path(__file__).resolve()
_CONTRACT_PRIMITIVES_CANDIDATES = [
    _ROOT.parents[4] / "contract-primitives" / "src",
    Path(_ROOT.anchor) / "packages" / "cc-skills-sdlc" / "contract-primitives" / "src",
]
for _candidate in _CONTRACT_PRIMITIVES_CANDIDATES:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

try:
    from contract_primitives import (  # noqa: E402
        ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR,
        REQUIRED_BOUNDARY_FIELDS,
        parse_contract_authority_packet,
        parse_planning_handoff_packet,
    )
    from planning_handoff_validation import validate_planning_handoff_contract

    CONTRACT_PRIMITIVES_AVAILABLE = True
except ImportError:
    CONTRACT_PRIMITIVES_AVAILABLE = False
    ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR = None
    REQUIRED_BOUNDARY_FIELDS = []
    parse_contract_authority_packet = None
    parse_planning_handoff_packet = None
    validate_planning_handoff_contract = None


# =============================================================================
# StageValidator — Process Compliance Checking
# =============================================================================
# The existing validate_adr() checks packet *shape*.  The StageValidator checks
# that the LLM actually *ran* the required SKILL.md stages — it looks for
# textual evidence in the ADR output that each stage was executed.
#
# This closes the asymmetry: contract packets are rigorously validated,
# template files are rigorously validated, but LLM process compliance was
# previously zero-validated.
# =============================================================================

StageName = Literal[
    "compliance_header",
    "stage_0_preflight",
    "stage_05_clarity",
    "stage_1_intent",
    "stage_14_contract_sensitivity",
    "stage_15_boundary_inventory",
    "stage_16_boundary_closure",
    "stage_17_packets",
    "stage_18_consistency",
    "adversarial_review",
]

CheckResult = Literal["pass", "warn", "fail"]


@dataclass
class StageCheck:
    """Result of checking a single stage for process compliance."""

    stage: StageName
    result: CheckResult
    detail: str = ""
    suggestion: str = ""


@dataclass
class StageValidationResult:
    """Aggregate result of validating all required stages."""

    checks: list[StageCheck] = field(default_factory=list)
    stages_required: list[StageName] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        return all(c.result != "fail" for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.result == "pass")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.result == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.result == "fail")

    def to_findings(self) -> list[dict[str, object]]:
        """Convert stage checks into validator findings (for merge with packet findings)."""
        findings: list[dict[str, object]] = []
        severity_map: dict[CheckResult, str] = {
            "fail": "HIGH",
            "warn": "MEDIUM",
            "pass": "INFO",
        }
        for check in self.checks:
            if check.result == "pass":
                continue  # Skip passing checks from findings to reduce noise
            finding: dict[str, object] = {
                "id": f"STAGE-{check.stage.upper()}",
                "priority": severity_map[check.result],
                "title": f"Stage '{check.stage}' process compliance: {check.result}",
                "detail": check.detail,
            }
            if check.suggestion:
                finding["suggestion"] = check.suggestion
            findings.append(finding)
        return findings


# ---------------------------------------------------------------------------
# Pattern definitions — what textual evidence indicates a stage was executed
# ---------------------------------------------------------------------------

# Stage 0: Pre-flight — out-of-scope detection was evaluated
_STAGE_0_PATTERNS = [
    r"(?i)out[- ]of[- ]scope",
    r"(?i)pre[- ]?flight",
    r"(?i)(?:prerequisite|gap)\s+(?:check|detect|analysis|assessment)",
    r"(?i)redirect(?:ed|ing)?\s+to\s+/",
    r"(?i)this\s+(?:query|request)\s+(?:is|appears)\s+(?:not\s+)?(out[- ]of[- ]scope|within\s+scope)",
    r"(?i)(?:no\s+)?(?:out[- ]of[- ]scope)\s+(?:pattern|indicator)\s+(?:detected|found|match)",
]

# Stage 0.5: Clarity gate — context inference or clarity assessment
_STAGE_05_PATTERNS = [
    r"(?i)clarity\s+(?:gate|check|assessment)",
    r"(?i)context\s+(?:infer|scan|check|analy)",
    r"(?i)(?:purpose|success\s+criteria|subject)\s+(?:present|inferred|identified|clear|absent)",
    r"(?i)insufficient\s+clarity",
    r"(?i)(?:proceed(?:ing)?\s+directly|proceed\s+to\s+stage\s+1|context\s+(?:found|exhausted|inferred))",
    r"(?i)(?:recent\s+(?:skill|file|architectural|turn)|prior\s+(?:context|turn|discussion))",
    r"(?i)clarif(?:y|ying|ication)",
]

# Stage 1: Intent classification — intent type detected
_STAGE_1_PATTERNS = [
    r"(?i)intent\s+(?:type|classification|detect|analysis)",
    r"(?i)(?:ARCHITECTURE_REVIEW|IMPROVE_SYSTEM|DEFAULT)",
    r"(?i)detected\s+(?:intent|intent\s+type|query\s+(?:type|class))",
    r"(?i)(?:review|improve|default)\s+(?:intent|path|branch)",
    r"(?i)classify\s+(?:intent|query|intent\s+type)",
]

# Stage 1.4: Contract sensitivity classification
_STAGE_14_PATTERNS = [
    r"(?i)contract[- ]sensitiv",
    r"(?i)(?:not\s+)?contract[- ]sensitive",
    r"(?i)boundary\s+(?:contract|artifact|handoff)",
    r"(?i)(?:touches|does\s+not\s+touch)\s+(?:contract|boundary|handoff)",
    r"(?i)classification:\s+(?:contract|not\s+contract)",
]

# Stage 1.5: Boundary inventory — boundaries listed
_STAGE_15_PATTERNS = [
    r"(?i)boundary\s+(?:inventory|list|mapping)",
    r"(?i)producer[/ ]consumer",
    r"(?i)handoff\s+(?:contract|boundary|artifact)",
    r"(?i)(?:boundary|handoff)\s+(?:name|id|identifier)\s*[:|]",
    r"(?i)inventor(?:y|ied)\s+(?:\d+\s+)?boundar",
]

# Stage 1.6: Boundary closure — boundaries closed with explicit fields
_STAGE_16_PATTERNS = [
    r"(?i)(?:boundary|contract)\s+(?:clos|complet|resolved|finalized)",
    r"(?i)freshness\s+authority",
    r"(?i)invalidation\s+trigger",
    r"(?i)precedence\s+rule",
    r"(?i)failure\s+behavior",
    r"(?i)(?:validator|proof)\s+owner",
    r"(?i)transcript[- ]vs[- ]artifact",
]

# Stage 1.7: Packets emitted
_STAGE_17_PATTERNS = [
    r"(?i)contract\s+authorit(?:y|ies?)\s+packet",
    r"(?i)planning\s+handoff\s+packet",
    r"(?i)contract_authority_packet",
    r"(?i)planning_handoff_packet",
]

# Stage 1.8: Consistency check
_STAGE_18_PATTERNS = [
    r"(?i)consistency\s+(?:check|pass|gate|review)",
    r"(?i)safety\s+policy\s+(?:gate|check)",
    r"(?i)router\s+precision\s+(?:gate|check)",
    r"(?i)packet[- ]to[- ]summary\s+(?:consistency|alignment|match)",
    r"(?i)validator\s+alignment\s+(?:gate|check)",
]

# Adversarial review: weakest assumption check
_ADVERSARIAL_PATTERNS = [
    r"(?i)(?:weakest|most\s+vulnerable|least\s+tested)\s+assumption",
    r"(?i)adversarial\s+(?:self[- ])?review",
    r"(?i)if\s+wrong:\s+",
    r"(?i)mitigation:\s+",
]


class StageValidator:
    """
    Validates that an ADR output shows textual evidence that required
    SKILL.md stages were actually executed — not just that output packets
    are well-shaped.

    This closes the gap between prompt-level process enforcement (SKILL.md
    prose) and code-level validation (arch_validate.py).

    Usage:
        validator = StageValidator(contract_sensitive=True)
        result = validator.validate(text)
        for finding in result.to_findings():
            ...
    """

    def __init__(self, contract_sensitive: bool = False) -> None:
        self.contract_sensitive = contract_sensitive

    # Mapping from stage name to pattern list
    _STAGE_PATTERNS: dict[StageName, list[str]] = {
        "compliance_header": [
            r"(?i)/arch\s+\[STANDARD\s+enforcement\]",
            r"(?i)ARCHITECTURE_REVIEW|/arch\s+\[",
        ],
        "stage_0_preflight": _STAGE_0_PATTERNS,
        "stage_05_clarity": _STAGE_05_PATTERNS,
        "stage_1_intent": _STAGE_1_PATTERNS,
        "stage_14_contract_sensitivity": _STAGE_14_PATTERNS,
        "stage_15_boundary_inventory": _STAGE_15_PATTERNS,
        "stage_16_boundary_closure": _STAGE_16_PATTERNS,
        "stage_17_packets": _STAGE_17_PATTERNS,
        "stage_18_consistency": _STAGE_18_PATTERNS,
        "adversarial_review": _ADVERSARIAL_PATTERNS,
    }

    def _check_stage(self, text: str, stage: StageName) -> StageCheck:
        """Check if text contains evidence that the given stage was executed."""
        patterns = self._STAGE_PATTERNS.get(stage, [])
        if not patterns:
            return StageCheck(stage=stage, result="warn", detail="No patterns defined for this stage")

        matches = [p for p in patterns if re.search(p, text)]
        match_count = len(matches)

        if match_count == 0:
            return StageCheck(
                stage=stage,
                result="fail",
                detail=f"No textual evidence found that stage '{stage}' was executed. "
                f"Checked {len(patterns)} patterns.",
                suggestion=f"Add a stage marker or evidence for '{stage}' in the ADR output.",
            )
        elif match_count < len(patterns) // 2 + 1:
            return StageCheck(
                stage=stage,
                result="warn",
                detail=f"Weak evidence for stage '{stage}': {match_count}/{len(patterns)} patterns matched.",
                suggestion="Consider adding more explicit stage markers.",
            )
        else:
            return StageCheck(
                stage=stage,
                result="pass",
                detail=f"Strong evidence for stage '{stage}': {match_count}/{len(patterns)} patterns matched.",
            )

    def validate(self, text: str) -> StageValidationResult:
        """
        Validate all required stages against the ADR text.

        Args:
            text: Full ADR markdown text to validate.

        Returns:
            StageValidationResult with checks for each stage.
        """
        result = StageValidationResult()

        # Always-required stages (every /arch invocation should show these)
        always_required: list[StageName] = [
            "compliance_header",
            "stage_1_intent",
        ]

        # Conditionally-required stages (only when contract-sensitive)
        conditional_required: list[StageName] = []
        if self.contract_sensitive:
            conditional_required = [
                "stage_14_contract_sensitivity",
                "stage_15_boundary_inventory",
                "stage_16_boundary_closure",
                "stage_17_packets",
                "stage_18_consistency",
            ]

        # Recommended stages (warn if missing, but not fail)
        recommended: list[StageName] = [
            "stage_0_preflight",
            "stage_05_clarity",
            "adversarial_review",
        ]

        # Check always-required stages (fail if missing)
        for stage in always_required:
            check = self._check_stage(text, stage)
            # For always-required stages, escalate warn → fail
            if check.result == "warn":
                check.result = "fail"
                check.detail = check.detail.replace("Weak evidence", "Insufficient evidence")
            result.checks.append(check)

        # Check conditional stages (fail if missing and contract-sensitive)
        for stage in conditional_required:
            check = self._check_stage(text, stage)
            if check.result == "warn":
                check.result = "fail"
                check.detail = (
                    check.detail.replace(
                        "Weak evidence",
                        "Insufficient evidence (contract-sensitive design requires this stage)",
                    )
                )
            result.checks.append(check)

        # Check recommended stages (warn if missing, never fail)
        for stage in recommended:
            check = self._check_stage(text, stage)
            # Keep warn as-is, don't escalate
            result.checks.append(check)

        result.stages_required = always_required + conditional_required + recommended
        return result


def validate_adr(
    path: str,
    *,
    check_stages: bool = True,
) -> dict[str, object]:
    """
    Validate an ADR file for both packet shape and process compliance.

    Args:
        path: Path to the ADR file.
        check_stages: If True, also validate that SKILL.md stages were
            actually executed (process compliance). Default True.

    Returns:
        Dict with status, packet info, stage info, and merged findings.
    """
    adr_path = Path(path)
    if not adr_path.exists():
        return {
            "status": "BLOCKED",
            "findings": [
                {
                    "id": "ADR-001",
                    "priority": "HIGH",
                    "title": f"ADR file not found: {path}",
                }
            ],
        }

    text = adr_path.read_text(encoding="utf-8")
    findings: list[dict[str, object]] = []

    if not CONTRACT_PRIMITIVES_AVAILABLE:
        findings.append(
            {
                "id": "ADR-000",
                "priority": "MEDIUM",
                "title": "contract_primitives package unavailable — packet validation skipped",
                "description": "Install contract-primitives package to enable full ADR validation.",
            }
        )
        return {
            "status": "READY",
            "packet_version": None,
            "boundary_count": 0,
            "planning_handoff_packet_version": None,
            "contract_sensitive": False,
            "stage_validation": _run_stage_validation(text, False) if check_stages else None,
            "findings": findings,
        }

    packet = parse_contract_authority_packet(text)
    handoff = parse_planning_handoff_packet(text)
    contract_sensitive = bool(packet.boundaries)

    if not packet.boundaries:
        findings.append(
            {
                "id": "ADR-002",
                "priority": "HIGH",
                "title": "Missing Contract Authority Packet boundaries",
                "description": "Contract-sensitive ADRs must emit a parseable contract_authority_packet.",
            }
        )

    findings.extend(validate_planning_handoff_contract(text, packet, handoff))

    for boundary_id, boundary in packet.boundaries.items():
        missing = []
        for field_name in REQUIRED_BOUNDARY_FIELDS:
            if field_name == "schema.id" and not boundary.schema_id:
                missing.append(field_name)
            elif field_name == "schema.version" and not boundary.schema_version:
                missing.append(field_name)
            elif field_name == "required_fields" and not boundary.required_fields:
                missing.append(field_name)
            elif field_name == "producer" and not boundary.producer:
                missing.append(field_name)
            elif field_name == "consumer" and not boundary.consumer:
                missing.append(field_name)
            elif field_name == "freshness_authority" and not boundary.freshness_authority:
                missing.append(field_name)
            elif field_name == "invalidation_trigger" and not boundary.invalidation_trigger:
                missing.append(field_name)
            elif field_name == "precedence_rule" and not boundary.precedence_rule:
                missing.append(field_name)
            elif field_name == "failure_behavior" and not boundary.failure_behavior:
                missing.append(field_name)
            elif field_name == "validator_owner" and not boundary.validator_owner:
                missing.append(field_name)
            elif field_name == "proof_owner" and not boundary.proof_owner:
                missing.append(field_name)

        if missing:
            findings.append(
                {
                    "id": f"ADR-{boundary_id}-MISSING",
                    "priority": "HIGH",
                    "title": f"Boundary '{boundary_id}' is missing required contract fields",
                    "description": ", ".join(missing),
                }
            )

        if "not yet specified" in boundary.validator_owner.lower():
            findings.append(
                {
                    "id": f"ADR-{boundary_id}-VALIDATOR",
                    "priority": "HIGH",
                    "title": f"Boundary '{boundary_id}' leaves validator ownership unresolved",
                    "description": "validator_owner cannot remain 'not yet specified' in a closed packet.",
                }
            )

        if boundary_id == "plan-artifact":
            behavior = boundary.failure_behavior.lower()
            if "/planning" not in behavior or "blocking" not in behavior:
                findings.append(
                    {
                        "id": "ADR-PLAN-001",
                        "priority": "HIGH",
                        "title": "plan-artifact boundary drifts from active /planning contract",
                        "description": (
                            "The packet must reflect the active planning contract, which blocks "
                            "before implementation-ready when packet consumption is missing or contradicted."
                        ),
                        "expected_failure_behavior": ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR,
                        "actual_failure_behavior": boundary.failure_behavior,
                    }
                )

    return {
        "status": "READY" if not findings else "BLOCKED",
        "packet_version": packet.packet_version,
        "boundary_count": len(packet.boundaries),
        "planning_handoff_packet_version": handoff.packet_version,
        "contract_sensitive": contract_sensitive,
        "stage_validation": _run_stage_validation(text, contract_sensitive) if check_stages else None,
        "findings": findings,
    }


def _run_stage_validation(
    text: str,
    contract_sensitive: bool,
) -> dict[str, object]:
    """Run stage validation and return a summary dict."""
    validator = StageValidator(contract_sensitive=contract_sensitive)
    stage_result = validator.validate(text)
    return {
        "all_pass": stage_result.all_pass,
        "pass_count": stage_result.pass_count,
        "warn_count": stage_result.warn_count,
        "fail_count": stage_result.fail_count,
        "stages_required": stage_result.stages_required,
        "findings": stage_result.to_findings(),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(json.dumps({"status": "BLOCKED", "error": "usage: arch_validate.py <adr_path> [--no-stages]"}))
        return 2

    adr_path = argv[1]
    check_stages = "--no-stages" not in argv[2:]

    result = validate_adr(adr_path, check_stages=check_stages)
    print(json.dumps(result, indent=2))

    # BLOCK if either packet findings or stage validation failed
    if result["status"] == "BLOCKED":
        return 2
    if result.get("stage_validation") and not result["stage_validation"]["all_pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
