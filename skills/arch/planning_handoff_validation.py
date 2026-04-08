from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# DEPTH RULE: When skills/ layer is added, increment parents[N] by 1.
_ROOT = Path(__file__).resolve()
_CONTRACT_PRIMITIVES_CANDIDATES = [
    _ROOT.parents[4] / "contract-primitives" / "src",
    Path(_ROOT.anchor) / "packages" / "sdlc" / "contract-primitives" / "src",
]
for _candidate in _CONTRACT_PRIMITIVES_CANDIDATES:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from contract_primitives import adr_requires_planning_handoff  # noqa: E402

PLANNING_EXECUTION_INSTRUCTION = "INSTRUCTION: Execute skill planning"
PLANNING_RETURN_TO_CALLER = "RETURN TO CALLER: /planning"

_PLANNING_INSTRUCTION_PATTERN = re.compile(
    rf"(?im)^{re.escape(PLANNING_EXECUTION_INSTRUCTION)}\s*$"
)
_PLANNING_RETURN_TO_CALLER_PATTERN = re.compile(
    rf"(?im)^{re.escape(PLANNING_RETURN_TO_CALLER)}\s*$"
)


def is_planning_bound_adr(text: str, handoff_packet_version: str | None) -> bool:
    """Return True when the ADR is intended to feed /planning."""
    return adr_requires_planning_handoff(text) or bool(handoff_packet_version)


def validate_planning_handoff_contract(
    text: str,
    packet: Any,
    handoff: Any,
) -> list[dict[str, object]]:
    """Validate the /arch -> /planning handoff packet and routing surface."""
    findings: list[dict[str, object]] = []
    if not is_planning_bound_adr(text, getattr(handoff, "packet_version", None)):
        return findings

    if not handoff.packet_version:
        findings.append(
            {
                "id": "ADR-003",
                "priority": "HIGH",
                "title": "Missing Planning Handoff Packet",
                "description": (
                    "Implementation-oriented ADRs that feed /planning must emit a "
                    "parseable planning_handoff_packet."
                ),
            }
        )
        return findings

    if not handoff.plan_title:
        findings.append(
            {
                "id": "ADR-HANDOFF-001",
                "priority": "HIGH",
                "title": "Planning Handoff Packet is missing plan_title",
            }
        )
    if not handoff.goal:
        findings.append(
            {
                "id": "ADR-HANDOFF-002",
                "priority": "HIGH",
                "title": "Planning Handoff Packet is missing goal",
            }
        )
    if not handoff.implementation_task_ids:
        findings.append(
            {
                "id": "ADR-HANDOFF-003",
                "priority": "HIGH",
                "title": "Planning Handoff Packet is missing implementation task units",
                "description": (
                    "implementation_changes must already be mapped into task_id entries "
                    "before /planning consumes the ADR."
                ),
            }
        )
    if packet.boundaries and handoff.contract_sensitive is not True:
        findings.append(
            {
                "id": "ADR-HANDOFF-004",
                "priority": "HIGH",
                "title": "Planning Handoff Packet contradicts contract-sensitive ADR state",
                "description": (
                    "When a Contract Authority Packet exists, the planning handoff "
                    "must declare contract_sensitive: true."
                ),
            }
        )

    has_planning_instruction = bool(_PLANNING_INSTRUCTION_PATTERN.search(text))
    has_return_to_planning = bool(_PLANNING_RETURN_TO_CALLER_PATTERN.search(text))
    if not has_planning_instruction and not has_return_to_planning:
        findings.append(
            {
                "id": "ADR-HANDOFF-005",
                "priority": "HIGH",
                "title": "Planning-bound ADR is missing the /planning routing handoff",
                "description": (
                    "Standalone /arch closures that feed /planning must emit "
                    f"`{PLANNING_EXECUTION_INSTRUCTION}`. Nested /arch remediation "
                    "under /planning must emit "
                    f"`{PLANNING_RETURN_TO_CALLER}`. At least one of those routing "
                    "surfaces must be present."
                ),
            }
        )

    return findings
