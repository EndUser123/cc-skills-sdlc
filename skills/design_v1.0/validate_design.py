"""Design artifact validator for design_v1.0.

Validates design_draft_<RUNID>.json against DesignPayload schema and business logic.
On SUCCESS: writes .verified_<RUNID> flag to .claude/arch_decisions/.
On FAIL: prints errors for user to fix.
Max 3 attempts per RUN ID.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from schemas import DesignPayload

ATTEMPT_FILE = ".attempt_{run_id}"
MAX_ATTEMPTS = 3


def _state_dir() -> Path:
    """Resolve the arch_decisions directory for verification state files."""
    skill_root = Path(__file__).resolve().parent
    return skill_root.parent.parent / ".claude" / "arch_decisions"


def _load_payload(path: str) -> tuple[DesignPayload | None, list[str]]:
    """Load and parse a DesignPayload from JSON."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as e:
        return None, [f"JSON parse error: {e}"]
    except OSError as e:
        return None, [f"File read error: {e}"]

    try:
        payload = DesignPayload.from_dict(raw)
    except (KeyError, TypeError, ValueError) as e:
        return None, [f"Schema validation error: {e}"]

    return payload, []


def _validate_logic(payload: DesignPayload) -> list[str]:
    """Business-logic validation beyond schema parsing."""
    errors: list[str] = []

    if not payload.run_id:
        errors.append("run_id is required and non-empty")

    if payload.mode not in ("system", "rca", "component"):
        errors.append(f"mode must be one of system/rca/component, got '{payload.mode}'")

    if payload.scope not in ("backend", "frontend", "data", "all"):
        errors.append(f"scope must be one of backend/frontend/data/all, got '{payload.scope}'")

    if not payload.ast_summary:
        errors.append("ast_summary is required and non-empty")

    if not payload.sop:
        errors.append("sop is required and non-empty")

    if not payload.template_name:
        errors.append("template_name is required and non-empty")

    if not payload.adr_markdown:
        errors.append("adr_markdown is required and non-empty")
    elif len(payload.adr_markdown) < 50:
        errors.append("adr_markdown appears too short — must be a complete ADR")

    if not payload.critic_findings:
        errors.append("critic_findings must contain at least one finding (even if severity=low)")

    # CAP boundary checks
    for b in payload.cap.boundaries:
        if not b.boundary_id:
            errors.append("Every ContractBoundary must have a boundary_id")
        if not b.producer:
            errors.append(f"Boundary '{b.boundary_id}' missing producer")
        if not b.consumer:
            errors.append(f"Boundary '{b.boundary_id}' missing consumer")

    # Claim verification (all domains)
    if not payload.claim_verification:
        errors.append(
            "claim_verification must contain at least one entry — "
            "each pattern recommendation must cite evidence"
        )
    else:
        for i, claim in enumerate(payload.claim_verification):
            if not claim.claim:
                errors.append(f"claim_verification[{i}] missing claim")
            if not claim.evidence:
                errors.append(
                    f"claim_verification[{i}] '{claim.claim[:40]}' missing evidence — "
                    "state the file, function, or documentation that supports this claim"
                )
            if not claim.verified and claim.counterexample:
                errors.append(
                    f"claim_verification[{i}] '{claim.claim[:40]}' has counterexample "
                    "but is not marked verified — either verify the claim or revise it"
                )

    # Bottleneck evidence (performance domain only)
    if payload.domain == "performance":
        if payload.bottleneck_evidence is None:
            errors.append(
                "bottleneck_evidence is required for performance-domain ADRs — "
                "state what was measured, the primary path, and timing constants"
            )
        else:
            bn = payload.bottleneck_evidence
            if not bn.measurement_basis:
                errors.append("bottleneck_evidence.measurement_basis is required")
            if not bn.primary_path:
                errors.append("bottleneck_evidence.primary_path is required")
            if not bn.fallback_positions:
                errors.append(
                    "bottleneck_evidence.fallback_positions is required — "
                    "map each method to its position in the fallback chain"
                )

    return errors


def _check_attempt_limit(run_id: str) -> tuple[bool, int]:
    """Check if max attempts exceeded. Returns (allowed, current_attempt)."""
    state_dir = _state_dir()
    attempt_file = state_dir / ATTEMPT_FILE.format(run_id=run_id)
    if attempt_file.exists():
        try:
            count = int(attempt_file.read_text().strip())
        except (OSError, ValueError):
            count = 0
    else:
        count = 0

    return count < MAX_ATTEMPTS, count + 1


def _increment_attempt(run_id: str, count: int) -> None:
    """Write attempt count."""
    state_dir = _state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    attempt_file = state_dir / ATTEMPT_FILE.format(run_id=run_id)
    attempt_file.write_text(str(count))


def _write_flag(run_id: str) -> str:
    """Write .verified_<run_id> flag file. Returns flag path."""
    state_dir = _state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    flag_file = state_dir / f".verified_{run_id}"

    record = {
        "run_id": run_id,
        "validation_source": "validate_design.py",
        "timestamp": time.time(),
    }
    flag_file.write_text(json.dumps(record), encoding="utf-8")
    return str(flag_file)


def _save_adr(run_id: str, adr_markdown: str, mode: str) -> str:
    """Save ADR markdown to docs/architecture/. Returns saved path."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    docs_dir = repo_root / "docs" / "architecture"
    docs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    filename = f"ADR-{mode.upper()}-{timestamp}.md"
    filepath = docs_dir / filename
    filepath.write_text(adr_markdown, encoding="utf-8")
    return str(filepath)


def validate(draft_path: str, mode: str, run_id: str) -> bool:
    """Run full validation. Returns True on SUCCESS, False on FAIL."""
    allowed, attempt = _check_attempt_limit(run_id)
    if not allowed:
        print(
            f"VALIDATION FAILED: Maximum {MAX_ATTEMPTS} attempts reached for RUN ID {run_id}.\n"
            "Please restart with a new RUN ID or ask the user for help.",
            file=sys.stderr,
        )
        return False

    print(f"Validation attempt {attempt}/{MAX_ATTEMPTS} for RUN ID {run_id}")

    payload, parse_errors = _load_payload(draft_path)
    if parse_errors:
        for err in parse_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        _increment_attempt(run_id, attempt)
        return False

    logic_errors = _validate_logic(payload)
    if logic_errors:
        for err in logic_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        _increment_attempt(run_id, attempt)
        return False

    # SUCCESS
    flag_path = _write_flag(run_id)
    print(f"SUCCESS: Schema and logic valid.")
    print(f"Verified flag written: {flag_path}")

    adr_path = _save_adr(run_id, payload.adr_markdown, mode)
    print(f"ADR saved: {adr_path}")

    # Clean up attempt counter
    state_dir = _state_dir()
    attempt_file = state_dir / ATTEMPT_FILE.format(run_id=run_id)
    if attempt_file.exists():
        attempt_file.unlink()

    return True


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "Usage: validate_design.py <draft_json_path> <mode> <run_id>\n"
            "  draft_json_path: path to design_draft_<RUNID>.json\n"
            "  mode: system|rca|component\n"
            "  run_id: the RUN ID for this session",
            file=sys.stderr,
        )
        sys.exit(1)

    draft_path = sys.argv[1]
    mode = sys.argv[2]
    run_id = sys.argv[3]

    if not os.path.exists(draft_path):
        print(f"ERROR: Draft file not found: {draft_path}", file=sys.stderr)
        sys.exit(1)

    success = validate(draft_path, mode, run_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
