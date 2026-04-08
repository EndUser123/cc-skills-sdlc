"""Contract validation helpers for producer/consumer boundary enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ValidationResult:
    """Result of a contract validation check."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    boundary_id: str = ""
    schema_id: str = ""
    schema_version: str = ""
    freshness_authority: str = ""
    checked_at: int = 0


def validate_contract(
    schema: dict[str, Any],
    payload: dict[str, Any],
    *,
    boundary_id: str = "",
) -> ValidationResult:
    """Validate a payload against a contract schema.

    Parameters
    ----------
    schema : dict
        Schema definition containing required fields and version info.
        Expected keys: ``schema_id``, ``schema_version``, ``required_fields``,
        ``freshness_authority``.
    payload : dict
        The actual payload to validate against the schema.
    boundary_id : str
        Optional boundary identifier for logging and error reporting.

    Returns
    -------
    ValidationResult
        ``valid`` is ``True`` when all required fields are present and
        schema version matches. ``errors`` is a non-empty list describing
        each failure when ``valid`` is ``False``.
    """
    errors: list[str] = []
    schema_id = schema.get("schema_id", "")
    schema_version = schema.get("schema_version", "")
    required_fields: list[str] = schema.get("required_fields", [])
    freshness_authority = schema.get("freshness_authority", "")

    # Check required fields
    missing = [f for f in required_fields if f not in payload or payload[f] is None]
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    # Schema version match
    payload_version = payload.get("schema_version", "")
    if schema_version and payload_version and payload_version != schema_version:
        errors.append(
            f"Schema version mismatch: expected '{schema_version}', "
            f"got '{payload_version}'"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        boundary_id=boundary_id,
        schema_id=schema_id,
        schema_version=schema_version,
        freshness_authority=freshness_authority,
        checked_at=0,
    )


def validate_boundary_contract(
    contract: Any,
    payload: dict[str, Any],
) -> ValidationResult:
    """Validate a payload against a BoundaryContract dataclass.

    Parameters
    ----------
    contract : BoundaryContract
        Parsed boundary contract from ContractAuthorityPacket.
    payload : dict
        The payload to validate.

    Returns
    -------
    ValidationResult
        ``valid`` when required fields are present and schema version matches.
    """
    schema = {
        "schema_id": contract.schema_id,
        "schema_version": contract.schema_version,
        "required_fields": contract.required_fields,
        "freshness_authority": contract.freshness_authority,
    }
    return validate_contract(schema, payload, boundary_id=contract.boundary_id)
