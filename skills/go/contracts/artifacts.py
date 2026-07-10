"""Versioned artifact contract registry for /go run artifacts.

Each entry is a small dataclass-like record with the fields described in the
goal. Contracts are declarative — they say what a writer must emit, what a
reader must read, and what failure looks like. Tests in
test_artifact_contracts.py exercise writers + readers + tolerance behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class ArtifactContract:
    """One run-scoped artifact in the /go dispatch pipeline."""

    version: str               # schema name, e.g. "pi-model.v1"
    artifact: str               # filename pattern, e.g. "pi-model_{run_id}.json"
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()
    additive_field_policy: str = "tolerated"  # tolerated | strict
    writer: str = ""           # module:func that emits this artifact
    readers: tuple[str, ...] = ()  # module:func(s) that read it
    failure_behavior: str = "BLOCK"  # BLOCK | fallback | document
    note: str = ""


# Canonical registry. New artifacts get a new entry; do not mutate existing
# versions in place — bump to v2 when fields change.
ARTIFACT_CONTRACTS: dict[str, ArtifactContract] = {
    "model-selection.v1": ArtifactContract(
        version="model-selection.v1",
        artifact="model-selection_{run_id}.json",
        required_fields=("tier", "model", "confidence"),
        optional_fields=("score", "max_possible", "signals", "task_type"),
        additive_field_policy="tolerated",
        writer="preflight_propose:produce_model_selection",
        readers=("orchestrate:classify_and_resolve_pi",
                  "preflight_propose:derive_report_gate"),
        failure_behavior="fallback",
        note="Classify-complexity output; classifier display only.",
    ),
    "pi-model.v1": ArtifactContract(
        version="pi-model.v1",
        artifact="pi-model_{run_id}.json",
        required_fields=("classifier_model", "tier", "pi_model"),
        # candidate_chain + candidate_models are the resolution output;
        # PiModelInfo.load filters to known dataclass fields (tolerated extras).
        optional_fields=("candidate_chain", "candidate_models"),
        additive_field_policy="tolerated",
        writer="adapters/pi/resolve_model.py:main",
        readers=("orchestrate:PiModelInfo.load",
                  "orchestrate:_resolve_chain_from_selection"),
        failure_behavior="fallback",
        note="Missing or schema-invalid => fallback to resolved provider/model chain.",
    ),
    "dispatch-result.v1": ArtifactContract(
        version="dispatch-result.v1",
        artifact="dispatch-result_{run_id}.json",
        required_fields=("status", "exit_code"),
        optional_fields=("command", "session_id", "session_dir"),
        additive_field_policy="tolerated",
        writer="harness.py:_write_dispatch_result",
        readers=("orchestrate:run_common_tail"),
        failure_behavior="document",
    ),
    "pi-candidate-attempt.v1": ArtifactContract(
        version="pi-candidate-attempt.v1",
        artifact="pi-candidate-attempts_{run_id}.jsonl",
        required_fields=("run_id", "model_alias", "outcome"),
        # provider_model is required when present; tolerated when missing.
        optional_fields=("provider_model", "attempt_index", "latency_ms",
                          "fallback_used", "validator_reason", "candidate_chain",
                          "final_model_used"),
        additive_field_policy="tolerated",
        writer="orchestrate:_record_candidate_attempt (JSONL append)",
        readers=("orchestrate:_candidate_chain_failover",
                  "telemetry aggregation"),
        failure_behavior="document",
        note="Append-only JSONL; one record per attempt.",
    ),
    "failover-telemetry.v1": ArtifactContract(
        version="failover-telemetry.v1",
        artifact="failover-telemetry_{run_id}.jsonl",
        required_fields=("run_id", "attempted_model", "outcome", "final_model"),
        optional_fields=("provider", "failure_reason", "fallback_selected", "final_status"),
        additive_field_policy="tolerated",
        writer="preflight_propose:record_failover_telemetry",
        readers=("omission_audit, telemetry dashboards"),
        failure_behavior="document",
    ),
    "omission-audit.v1": ArtifactContract(
        version="omission-audit.v1",
        artifact="omission-audit_{run_id}.json",
        required_fields=("verdict", "completion_authority_level",
                          "omission_audit"),
        # commit_push_safe + overclaims + blocking_gaps are required for a
        # clean PASS, but the contract records their presence as optional so a
        # REVISE can still produce a valid artifact.
        optional_fields=("commit_push_safe", "overclaims", "blocking_gaps",
                          "commit_boundary_packet", "recommended_next_action"),
        additive_field_policy="tolerated",
        writer="orchestrate/omission_audit.py:main (run_audit -> to_dict)",
        readers=("orchestrate:run_common_tail", "telemetry aggregation"),
        failure_behavior="document",
    ),
}


def get_contract(version: str) -> ArtifactContract:
    """Lookup helper. Raises KeyError if unknown — caller decides on fallback."""
    if version not in ARTIFACT_CONTRACTS:
        raise KeyError(
            f"Unknown artifact contract version: {version!r}. "
            f"Known: {sorted(ARTIFACT_CONTRACTS)}"
        )
    return ARTIFACT_CONTRACTS[version]


def validate(contract: ArtifactContract, data: dict) -> list[str]:
    """Return a list of missing-required-field names. Empty = valid."""
    return [k for k in contract.required_fields if k not in data]


def writer_role_for(version: str) -> str:
    return get_contract(version).writer


def readers_for(version: str) -> tuple[str, ...]:
    return get_contract(version).readers
