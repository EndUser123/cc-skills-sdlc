"""
TDD validator v3.2 — receipt-based.
Windows 11 optimized (no global file locks).
Multi-terminal isolated via run-id partitioning.
"""

import sys
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_models import SessionState, TddEvidence, PhaseReceipt  # type: ignore
from pydantic import ValidationError

STATE_ROOT = Path(os.getcwd()) / ".claude-state" / "tdd"
ACTIVE_PTR = STATE_ROOT / ".active_run"
MAX_RETRIES = 3

_FAIL_PATTERN = re.compile(
    r"(?:\d+\s+failed|FAILED\s+\S+|ERRORS?\s+collecting|"
    r"AssertionError|assert\s+.+==|FAIL:\s+|---\s+FAIL|panic:\s+)",
    re.IGNORECASE,
)
_PASS_PATTERN = re.compile(
    r"(?:\d+\s+passed|test result:\s*ok|Tests:\s+\d+\s+passed|^ok\s+\S+|^PASS$)",
    re.IGNORECASE | re.MULTILINE,
)
_RESIDUAL_FAIL = re.compile(r"(\d+)\s+failed", re.IGNORECASE)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _output_shows_failure(text: str) -> bool:
    return bool(_FAIL_PATTERN.search(text))


def _output_shows_pass(text: str) -> bool:
    if not _PASS_PATTERN.search(text):
        return False
    m = _RESIDUAL_FAIL.search(text)
    return False if m and int(m.group(1)) > 0 else True


def _parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def validate_run(run_id: str) -> None:
    run_dir = STATE_ROOT / run_id
    session_path = run_dir / "session.json"
    evidence_path = run_dir / "evidence.json"

    # Early exit if run_dir doesn't exist - prevents stale pointer issues
    if not run_dir.exists():
        print(f"ERROR: Run directory not found for run_id {run_id}")
        sys.exit(1)

    if not session_path.exists():
        print(f"ERROR: session.json not found for run_id {run_id}")
        sys.exit(1)

    try:
        session = SessionState.model_validate_json(
            session_path.read_text(encoding="utf-8")
        )
    except ValidationError as e:
        print(f"SCHEMA ERROR: session.json invalid.\n{e}")
        sys.exit(1)

    # Verify run_id matches session to prevent cross-run contamination
    if session.run_id != run_id:
        print(f"ERROR: session.run_id ({session.run_id}) != run_id ({run_id})")
        sys.exit(1)

    if session.retries >= MAX_RETRIES:
        print(
            f"HARD STOP: {MAX_RETRIES} validation attempts exhausted. "
            "Ask user for help."
        )
        sys.exit(1)

    def fail_with_errors(errs: list[str]) -> None:
        session.retries += 1
        session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        print("VALIDATION FAILED. Fix the following and retry:\n")
        for i, msg in enumerate(errs, 1):
            print(f"  {i}. {msg}")
        print(f"\n(Attempt {session.retries}/{MAX_RETRIES})")
        sys.exit(1)

    if not evidence_path.exists():
        fail_with_errors(["evidence.json not found. Did you draft it first?"])

    try:
        evidence = TddEvidence.model_validate_json(
            evidence_path.read_text(encoding="utf-8")
        )
    except ValidationError as e:
        fail_with_errors([f"evidence.json invalid schema.\n{e}"])

    errors: list[str] = []
    receipts: dict[str, PhaseReceipt] = {}
    logs: dict[str, str] = {}

    def load_and_verify(ref_path: str, phase: str) -> bool:
        rp = run_dir / ref_path
        if not rp.exists():
            errors.append(f"{phase.upper()}: Receipt not found: {rp}")
            return False
        try:
            receipt = PhaseReceipt.model_validate_json(
                rp.read_text(encoding="utf-8")
            )
        except ValidationError as e:
            errors.append(f"{phase.upper()}: Schema invalid.\n{e}")
            return False

        if not receipt.verify_signature(session.hmac_secret):
            errors.append(
                f"{phase.upper()}: Signature INVALID. "
                "Receipt tampered with or fabricated."
            )
            return False

        log_path = run_dir / receipt.stdout_path
        if not log_path.exists() or _sha256_file(log_path) != receipt.stdout_sha256:
            errors.append(
                f"{phase.upper()}: Log file missing or hash mismatch "
                "(tampered post-run)."
            )
            return False

        receipts[phase] = receipt
        logs[phase] = log_path.read_text(encoding="utf-8")
        return True

    # RED
    if load_and_verify(evidence.red.receipt_path, "red"):
        if receipts["red"].exit_code == 0:
            errors.append("RED: Tests passed (exit 0). RED must fail.")
        if not _output_shows_failure(logs["red"]):
            errors.append("RED: stdout shows no clear failure.")
        if len(logs["red"].strip().splitlines()) < 3:
            errors.append("RED: stdout is suspiciously short (<3 lines).")

    # GREEN
    if load_and_verify(evidence.green.receipt_path, "green"):
        if receipts["green"].exit_code != 0:
            errors.append("GREEN: Tests failed (exit non-zero).")
        if not _output_shows_pass(logs["green"]):
            errors.append("GREEN: stdout shows no clear pass.")
        if len(logs["green"].strip().splitlines()) < 3:
            errors.append("GREEN: stdout is suspiciously short (<3 lines).")

    # Cross-phase
    if "red" in receipts and "green" in receipts:
        if _parse_iso(receipts["green"].started_at) < _parse_iso(
            receipts["red"].finished_at
        ):
            errors.append("ORDERING: GREEN started before RED finished.")
        if logs.get("red", "").strip() == logs.get("green", "").strip():
            errors.append("LOGIC: RED and GREEN stdout are identical.")

    # REFACTOR
    if evidence.files_refactored or evidence.refactor:
        if not evidence.refactor:
            errors.append(
                "REFACTOR: files_refactored listed but no refactor receipt."
            )
        elif load_and_verify(evidence.refactor.receipt_path, "refactor"):
            if receipts["refactor"].exit_code != 0:
                errors.append("REFACTOR: Tests failed (exit non-zero).")
            if not _output_shows_pass(logs["refactor"]):
                errors.append("REFACTOR: stdout shows no clear pass.")
            if (
                "green" in logs
                and logs["green"].strip() == logs["refactor"].strip()
            ):
                errors.append(
                    "REFACTOR: stdout identical to GREEN. "
                    "You must re-run tests after refactor, not reuse GREEN output."
                )

    if errors:
        fail_with_errors(errors)

    # Success
    validated_state = {
        "run_id": run_id,
        "validated": True,
        "target_component": evidence.target_component,
        "mode": evidence.metadata.mode,
    }
    (run_dir / "validated.json").write_text(
        json.dumps(validated_state, indent=2), encoding="utf-8"
    )

    session.phase = "validated"
    session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    if ACTIVE_PTR.exists():
        ACTIVE_PTR.unlink()

    print(f"SUCCESS: TDD Validated — run {run_id[:8]}…")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_tdd.py <RUN_ID>")
        sys.exit(1)
    validate_run(sys.argv[1])