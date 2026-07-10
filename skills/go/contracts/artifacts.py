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
        writer="python:classify_complexity:main",
        readers=("python:orchestrate:classify_and_resolve_pi",),
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
        writer="python:adapters/pi/resolve_model.py:main",
        readers=("python:orchestrate:PiModelInfo.load",
                  "python:orchestrate:_resolve_chain_from_selection"),
        failure_behavior="fallback",
        note="Missing or schema-invalid => fallback to resolved provider/model chain.",
    ),
    "dispatch-result.v1": ArtifactContract(
        version="dispatch-result.v1",
        artifact="dispatch-result_{run_id}.json",
        required_fields=("status", "exit_code"),
        optional_fields=("command", "session_id", "session_dir"),
        additive_field_policy="tolerated",
        writer="python:adapters/pi/harness.py:main",
        readers=("python:orchestrate:run_common_tail",),
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
        writer="python:orchestrate:_record_candidate_attempt",
        readers=("python:orchestrate:_candidate_chain_failover",
                  "external:telemetry-aggregation"),
        failure_behavior="document",
        note="Append-only JSONL; one record per attempt.",
    ),
    "failover-telemetry.v1": ArtifactContract(
        version="failover-telemetry.v1",
        artifact="failover-telemetry_{run_id}.jsonl",
        required_fields=("run_id", "attempted_model", "outcome", "final_model"),
        optional_fields=("provider", "failure_reason", "fallback_selected", "final_status"),
        additive_field_policy="tolerated",
        writer="python:preflight_propose:record_failover_telemetry",
        readers=("external:telemetry-dashboards",),
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
        writer="python:omission_audit:main",
        readers=("python:orchestrate:run_common_tail",
                  "external:telemetry-aggregation"),
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


_NON_SYMBOLIC_PREFIXES = frozenset({
    "external:", "script-step:", "manual:", "unknown:",
})


def _is_non_symbolic(ref):
    return any(ref.startswith(p) for p in _NON_SYMBOLIC_PREFIXES)


def _resolve_python_symbol(ref):
    """Resolve python:module:func to a live symbol via importlib."""
    import importlib.util, sys
    body = ref[len("python:"):]
    parts = body.rsplit(":", 1)
    if len(parts) != 2:
        return (False, f"missing module:func separator in {ref!r}")
    module_name, func_name = parts
    if not module_name.strip() or not func_name.strip():
        return (False, f"empty module or func in {ref!r}")
    file_rel = _MODULE_FILE_MAP.get(module_name)
    if file_rel is None:
        file_rel = module_name if module_name.endswith(".py") else module_name + ".py"
    file_path = _SCRIPTS / file_rel
    if not file_path.exists():
        return (False, f"module file not found: {file_path}")
    mod_id = f"_cv_{module_name.replace('/', '_').replace('.', '_')}"
    try:
        spec = importlib.util.spec_from_file_location(mod_id, file_path)
        if spec is None or spec.loader is None:
            return (False, f"cannot create spec for {file_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_id] = mod
        spec.loader.exec_module(mod)
    except Exception as exc:
        return (False, f"import error: {type(exc).__name__}: {exc}")
    if not hasattr(mod, func_name):
        return (False, f"function {func_name!r} not found in {module_name}")
    return (True, "ok")


def validate_metadata(ref):
    if not ref or not ref.strip():
        return (False, "empty reference")
    if ref.startswith("python:"):
        return _resolve_python_symbol(ref)
    if _is_non_symbolic(ref):
        return (True, "explicit non-symbolic")
    return (False, "bare text: use python:module:func or explicit prefix")


def validate_all_metadata():
    results = []
    for version, contract in ARTIFACT_CONTRACTS.items():
        ok, msg = validate_metadata(contract.writer)
        if not ok:
            results.append((version, "writer", contract.writer, ok, msg))
        for reader in contract.readers:
            ok, msg = validate_metadata(reader)
            if not ok:
                results.append((version, "reader", reader, ok, msg))
    return results
