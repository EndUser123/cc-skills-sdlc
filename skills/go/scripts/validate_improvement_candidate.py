#!/usr/bin/env python3
"""Pure-stdlib validator for /go improvement-candidate JSON files.

Validates structure, enums, candidate_id format, and the cross-field rules the
contract requires:

  * mechanism_trace required (non-null) when target_layer is
    runtime_gate | hook | orchestrator | validation_script
  * hook target_layer requires the full hook promotion checklist
    (deterministic_decision, lifecycle_necessity, tested_script_underneath,
    safe_failure_direction, explicit_registration_plan)
  * runtime_gate target_layer requires the runtime-gate checklist
    (real_boundary_test, calibration_data, fail_direction_decision,
    owner_approval)
  * review_status='implemented' requires every promotion_requirements.items[i]
    to carry satisfied=true AND a non-empty evidence citation

Stdlib-only by design: no jsonschema dependency. The companion JSON Schema
file (schemas/improvement_candidate.schema.json) is the structural reference;
this script is the authoritative checker for cross-field rules.

A PASS here means the file is well-formed. It does NOT approve, schedule, or
auto-promote the candidate. Review is a separate human step.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------- enums (single source of truth; mirrored in the JSON schema) -----

SOURCE_SKILLS = {"go", "friction", "behave", "skeptic", "dne", "evolve", "genius", "manual"}

EVIDENCE_TIERS = {
    "execution_artifact",
    "official_doc_or_spec",
    "source_inspection",
    "test_result",
    "user_report",
    "inference",
    "memory_or_unverified",
}

CANDIDATE_TYPES = {
    "workflow_friction",
    "llm_behavior_failure",
    "semantic_coverage_gap",
    "overclaim_or_evidence_gap",
    "technical_debt",
    "risk_model",
    "hook_candidate",
    "skill_handoff_rule",
    "documentation_gap",
    "runtime_gate_candidate",
    "cleanup_candidate",
}

LAYERS = {
    "prompt_only",
    "docs",
    "report_contract",
    "validation_script",
    "advisory_review",
    "runtime_gate",
    "hook",
    "orchestrator",
    "skill_handoff",
    "modernization_campaign",
    "do_not_implement",
}

REVIEW_STATUSES = {"proposed", "needs_evidence", "accepted_for_backlog", "rejected", "implemented", "superseded"}

CONFIDENCE_LEVELS = {"low", "medium", "high"}
RISK_LEVELS = {"low", "medium", "high", "critical"}

# Layers for which mechanism_trace MUST be a real trace (not null/null-variant).
MECHANISM_TRACE_REQUIRED_LAYERS = {"runtime_gate", "hook", "orchestrator", "validation_script"}

# Hook promotion checklist (per the contract's hook rules).
HOOK_PROMOTION_KEYS = {
    "deterministic_decision",
    "lifecycle_necessity",
    "tested_script_underneath",
    "safe_failure_direction",
    "explicit_registration_plan",
}

# Runtime-gate promotion checklist.
RUNTIME_GATE_PROMOTION_KEYS = {
    "real_boundary_test",
    "calibration_data",
    "fail_direction_decision",
    "owner_approval",
}

REQUIRED_FIELDS = frozenset({
    "candidate_id",
    "created_at",
    "source_skill",
    "observed_problem",
    "evidence",
    "evidence_tier",
    "frequency",
    "affected_layer",
    "target_skill_or_system",
    "candidate_type",
    "proposed_change",
    "target_layer",
    "mechanism_trace",
    "confidence",
    "risk",
    "expected_benefit",
    "failure_mode_prevented",
    "falsification_condition",
    "promotion_requirements",
    "recommended_destination",
    "review_status",
})

CANDIDATE_ID_SOURCE_KEYS = frozenset({"BEH", "DNE", "EVL", "FRI", "GEN", "GO", "MAN", "SKP"})

_KEY_ALT = "|".join(sorted(CANDIDATE_ID_SOURCE_KEYS))
CANDIDATE_ID_PATTERN = re.compile(rf"^IC-(?:{_KEY_ALT})-[A-Za-z0-9._:-]{{1,64}}$")

ISO8601_HINT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$")


def _is_iso8601(s: str) -> bool:
    """Cheap ISO-8601 sanity check (presence of date+T+optional tz). Full parsing
    is unnecessary for a structural linter; semantic validation is the reviewer's job."""
    return bool(ISO8601_HINT.match(s))


def _is_null_trace(mt: Any) -> bool:
    """True if mechanism_trace is JSON null or the null-variant object."""
    if mt is None:
        return True
    if isinstance(mt, dict) and mt.get("null") is True:
        return True
    return False


# ---------- per-field structural checks -------------------------------------

def _check_required(payload: dict[str, Any], errors: list[str]) -> None:
    for field in REQUIRED_FIELDS:
        if field not in payload:
            errors.append(f"missing required field '{field}'")


def _check_enum(payload: dict[str, Any], field: str, allowed: set[str], errors: list[str]) -> None:
    val = payload.get(field)
    if val is None or field not in payload:
        return  # presence checked by _check_required
    if val not in allowed:
        errors.append(f"field '{field}' value {val!r} not in allowed enum {sorted(allowed)}")


def _check_candidate_id(payload: dict[str, Any], errors: list[str]) -> None:
    cid = payload.get("candidate_id")
    if not isinstance(cid, str):
        errors.append("field 'candidate_id' must be a string")
        return
    if not CANDIDATE_ID_PATTERN.match(cid):
        errors.append(
            f"field 'candidate_id' value {cid!r} does not match pattern "
            f"IC-<KEY>-<LOCAL> where KEY ∈ {sorted(CANDIDATE_ID_SOURCE_KEYS)} "
            "and LOCAL matches [A-Za-z0-9._:-]{1,64}"
        )


def _check_created_at(payload: dict[str, Any], errors: list[str]) -> None:
    val = payload.get("created_at")
    if isinstance(val, str) and not _is_iso8601(val):
        errors.append(
            f"field 'created_at' value {val!r} is not ISO-8601 "
            "(expected YYYY-MM-DDTHH:MM:SS[.fff][Z|+HH:MM])"
        )


def _check_evidence(payload: dict[str, Any], errors: list[str]) -> None:
    val = payload.get("evidence")
    if val is None:
        return
    if not isinstance(val, list) or not val:
        errors.append("field 'evidence' must be a non-empty list of citation strings")
        return
    for i, item in enumerate(val):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"field 'evidence[{i}]' must be a non-empty string")


def _check_promotion_requirements(payload: dict[str, Any], errors: list[str]) -> None:
    pr = payload.get("promotion_requirements")
    if pr is None:
        return
    if not isinstance(pr, dict):
        errors.append("field 'promotion_requirements' must be an object")
        return
    for key in ("reviewer_acceptance", "evidence_basis", "items"):
        if key not in pr:
            errors.append(f"field 'promotion_requirements' missing required sub-field '{key}'")
    items = pr.get("items")
    if items is None:
        return
    if not isinstance(items, list):
        errors.append("field 'promotion_requirements.items' must be a list")
        return
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"field 'promotion_requirements.items[{i}]' must be an object")
            continue
        if "key" not in item or "description" not in item:
            errors.append(f"field 'promotion_requirements.items[{i}]' missing 'key' or 'description'")


def _check_mechanism_trace(payload: dict[str, Any], errors: list[str]) -> None:
    if "mechanism_trace" not in payload:
        return  # required check handles absence
    mt = payload["mechanism_trace"]
    if mt is None:
        return  # JSON null literal; cross-field rule may still reject for high-risk layers
    if not isinstance(mt, dict):
        errors.append("field 'mechanism_trace' must be a JSON object, null, or null-variant")
        return
    if mt.get("null") is True:
        nr = mt.get("null_reason")
        if not (isinstance(nr, str) and nr.strip()):
            errors.append("mechanism_trace null-variant requires non-empty 'null_reason'")
        return
    # Full trace.
    full_required = {
        "producer", "artifact_or_state", "consumer", "authority_or_verdict",
        "freshness_check", "failure_direction", "real_boundary_test",
    }
    missing = full_required - set(mt.keys())
    if missing:
        errors.append(
            "mechanism_trace missing required keys: "
            f"{sorted(missing)} (producer, artifact_or_state, consumer, "
            "authority_or_verdict, freshness_check, failure_direction, real_boundary_test)"
        )
    for k, v in mt.items():
        if k in {"null", "null_reason"}:
            continue
        if not (isinstance(v, str) and v.strip()):
            errors.append(f"mechanism_trace.{k} must be a non-empty string")


# ---------- cross-field rules -----------------------------------------------

def _collect_promotion_item_keys(payload: dict[str, Any]) -> set[str]:
    pr = payload.get("promotion_requirements")
    if not isinstance(pr, dict):
        return set()
    items = pr.get("items")
    if not isinstance(items, list):
        return set()
    return {it["key"] for it in items if isinstance(it, dict) and isinstance(it.get("key"), str)}


def _check_cross_field(payload: dict[str, Any], errors: list[str]) -> None:
    target_layer = payload.get("target_layer")
    review_status = payload.get("review_status")
    mt = payload.get("mechanism_trace")

    # Rule 1: mechanism_trace required (non-null) for high-risk target layers.
    if target_layer in MECHANISM_TRACE_REQUIRED_LAYERS and _is_null_trace(mt):
        errors.append(
            f"target_layer='{target_layer}' requires a non-null mechanism_trace "
            "(full trace object: producer/artifact_or_state/consumer/"
            "authority_or_verdict/freshness_check/failure_direction/real_boundary_test)"
        )

    item_keys = _collect_promotion_item_keys(payload)

    # Rule 2: hook target_layer must enumerate the full hook promotion checklist.
    if target_layer == "hook":
        missing = HOOK_PROMOTION_KEYS - item_keys
        if missing:
            errors.append(
                "hook target_layer requires promotion_requirements.items keys: "
                f"missing {sorted(missing)}"
            )

    # Rule 3: runtime_gate target_layer must enumerate the runtime-gate checklist.
    if target_layer == "runtime_gate":
        missing = RUNTIME_GATE_PROMOTION_KEYS - item_keys
        if missing:
            errors.append(
                "runtime_gate target_layer requires promotion_requirements.items keys: "
                f"missing {sorted(missing)}"
            )

    # Rule 4: review_status='implemented' requires explicit promotion evidence on every item.
    if review_status == "implemented":
        items = payload.get("promotion_requirements", {}).get("items") if isinstance(payload.get("promotion_requirements"), dict) else None
        if not isinstance(items, list) or not items:
            errors.append(
                "review_status='implemented' requires non-empty promotion_requirements.items "
                "with satisfied=true and evidence on every item"
            )
            return
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                errors.append(
                    f"review_status='implemented' requires promotion_requirements.items[{i}] to be an object"
                )
                continue
            if it.get("satisfied") is not True:
                errors.append(
                    f"review_status='implemented' requires promotion_requirements.items[{i}].satisfied=true"
                )
            ev = it.get("evidence")
            if not (isinstance(ev, str) and ev.strip()):
                errors.append(
                    f"review_status='implemented' requires promotion_requirements.items[{i}].evidence "
                    "(non-empty citation)"
                )


# ---------- top-level validate ---------------------------------------------

def validate_payload(payload: Any) -> list[str]:
    """Return a list of human-readable errors. Empty list = PASS."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"payload must be a JSON object, got {type(payload).__name__}"]

    _check_required(payload, errors)
    _check_candidate_id(payload, errors)
    _check_created_at(payload, errors)
    _check_evidence(payload, errors)
    _check_promotion_requirements(payload, errors)
    _check_mechanism_trace(payload, errors)

    _check_enum(payload, "source_skill", SOURCE_SKILLS, errors)
    _check_enum(payload, "evidence_tier", EVIDENCE_TIERS, errors)
    _check_enum(payload, "affected_layer", LAYERS, errors)
    _check_enum(payload, "candidate_type", CANDIDATE_TYPES, errors)
    _check_enum(payload, "target_layer", LAYERS, errors)
    _check_enum(payload, "confidence", CONFIDENCE_LEVELS, errors)
    _check_enum(payload, "risk", RISK_LEVELS, errors)
    _check_enum(payload, "recommended_destination", LAYERS, errors)
    _check_enum(payload, "review_status", REVIEW_STATUSES, errors)

    # Cross-field rules only when the structural checks at least saw the fields;
    # otherwise the cross-field errors duplicate the "missing" errors and add noise.
    if "target_layer" in payload and "review_status" in payload:
        _check_cross_field(payload, errors)

    return errors


def validate_file(path: Path) -> tuple[bool, list[str]]:
    """Validate a single candidate file. Returns (ok, errors)."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"file not found: {path}"]
    except json.JSONDecodeError as e:
        return False, [f"invalid JSON: {e}"]
    errs = validate_payload(payload)
    return (not errs), errs


# ---------- CLI ------------------------------------------------------------

def _print_result(path: Path, ok: bool, errors: list[str]) -> None:
    if ok:
        print(f"PASS  {path}")
        return
    print(f"FAIL  {path}")
    for e in errors:
        print(f"  ERROR: {e}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Validate /go improvement-candidate JSON files (stdlib; no jsonschema dep)."
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Validate a single candidate JSON file.")
    src.add_argument("--dir", help="Validate every *.json file in a directory (non-recursive).")
    p.add_argument("--quiet", action="store_true", help="Suppress PASS lines; show only FAILs.")
    args = p.parse_args(argv)

    if args.file:
        path = Path(args.file).resolve()
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2
        ok, errs = validate_file(path)
        if ok and args.quiet:
            return 0
        _print_result(path, ok, errs)
        return 0 if ok else 1

    d = Path(args.dir).resolve()
    if not d.is_dir():
        print(f"ERROR: not a directory: {d}", file=sys.stderr)
        return 2
    files = sorted(p for p in d.iterdir() if p.is_file() and p.suffix == ".json")
    if not files:
        print(f"ERROR: no .json files in {d}", file=sys.stderr)
        return 2
    failures = 0
    for f in files:
        ok, errs = validate_file(f)
        if not ok:
            failures += 1
            _print_result(f, ok, errs)
        elif not args.quiet:
            _print_result(f, ok, errs)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())