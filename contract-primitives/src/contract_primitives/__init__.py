"""Shared schema helpers for contract-sensitive workflow artifacts.

These helpers intentionally stay lightweight so hook and skill validators can
share one authority for matrix shape, packet parsing, and readiness semantics
without importing a full application stack.
"""

from .schemas import (
    ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR,
    PLACEHOLDER_BINDINGS,
    REQUIRED_BOUNDARY_FIELDS,
    REQUIRED_PLAN_MATRIX_FIELDS,
    PlanningSourcePacket,
    PlanningHandoffPacket,
    BoundaryContract,
    ContractAuthorityPacket,
    adr_requires_planning_handoff,
    extract_markdown_table,
    find_contract_boundary_rows,
    parse_contract_authority_packet,
    parse_planning_source_packet,
    parse_planning_handoff_packet,
)
from .plan_consumption import PlanConsumerValidationResult, validate_plan_for_execution
from .plan_consumption import discover_local_plan_path
from .validators import ValidationResult, validate_contract, validate_boundary_contract
from .events import log_contract_event

__all__ = [
    "ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR",
    "PlanningSourcePacket",
    "PlanningHandoffPacket",
    "BoundaryContract",
    "ContractAuthorityPacket",
    "PLACEHOLDER_BINDINGS",
    "PlanConsumerValidationResult",
    "REQUIRED_BOUNDARY_FIELDS",
    "REQUIRED_PLAN_MATRIX_FIELDS",
    "ValidationResult",
    "adr_requires_planning_handoff",
    "discover_local_plan_path",
    "extract_markdown_table",
    "find_contract_boundary_rows",
    "log_contract_event",
    "parse_contract_authority_packet",
    "parse_planning_source_packet",
    "parse_planning_handoff_packet",
    "validate_boundary_contract",
    "validate_contract",
    "validate_plan_for_execution",
]
