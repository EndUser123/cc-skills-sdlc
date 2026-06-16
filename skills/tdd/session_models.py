"""
Session, receipt, and evidence models for TDD v3.2.
Optimized for Windows 11 (no fcntl).
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Session ──────────────────────────────────────────────────────────────────


class SessionState(BaseModel):
    """Structured session state persisted in session.json.

    Phase semantics:
      - "init"      : session created, no RED run yet
      - "red"       : RED completed at least once
      - "green"     : GREEN completed at least once
      - "refactor"  : REFACTOR completed at least once
      - "validated" : validate_tdd.py succeeded
    """

    run_id: str = Field(..., min_length=1)
    mode: Literal["feature", "bugfix", "refactor"]
    task: str = Field(..., min_length=1)
    cwd: str = Field(..., min_length=1)
    test_command: str = Field(..., min_length=1)
    phase: Literal["init", "red", "green", "refactor", "validated"] = "init"
    hmac_secret: str = Field(..., min_length=1)
    started_at: str = Field(default_factory=now_iso)
    # Localized retry tracking (replaces global lock file)
    retries: int = 0


# ── Phase Receipts ───────────────────────────────────────────────────────────


class PhaseReceipt(BaseModel):
    """Metadata about a single test run, written and signed by run_phase.py."""

    phase: Literal["red", "green", "refactor"]
    run_id: str
    test_command: str
    cwd: str
    exit_code: int
    started_at: str
    finished_at: str
    stdout_path: str
    stderr_path: Optional[str] = None
    stdout_sha256: str
    stderr_sha256: Optional[str] = None
    signature: str = Field(
        ...,
        min_length=1,
        description="HMAC-SHA256 of receipt content fields, signed by session secret.",
    )

    def compute_signature(self, secret: str) -> str:
        """Compute HMAC over the deterministic content of this receipt."""
        content = (
            f"{self.phase}|{self.run_id}|{self.test_command}|{self.cwd}|"
            f"{self.exit_code}|{self.started_at}|{self.finished_at}|"
            f"{self.stdout_sha256}|{self.stderr_sha256 or ''}"
        )
        return hmac.new(
            secret.encode(), content.encode(), hashlib.sha256
        ).hexdigest()

    def verify_signature(self, secret: str) -> bool:
        expected = self.compute_signature(secret)
        return hmac.compare_digest(self.signature, expected)


# ── Evidence ─────────────────────────────────────────────────────────────────


class PhaseReceiptRef(BaseModel):
    phase: Literal["red", "green", "refactor"]
    receipt_path: str = Field(..., min_length=1)


class MutationReceiptRef(BaseModel):
    """Pointer to a mutation-testing receipt (mutmut 3.x run)."""

    phase: Literal["mutation"] = "mutation"
    receipt_path: str = Field(..., min_length=1)
    module: str = Field(..., min_length=1)
    target_score: Optional[int] = None
    mutation_score: Optional[float] = None
    status: Literal["passed", "failed", "waived", "skipped", "timeout", "blocked"] = "blocked"


class MutationReceipt(BaseModel):
    """HMAC-signed receipt for a single mutation-testing run.

    Written and signed by run_phase.py when invoked with --phase mutation.
    Mirrors PhaseReceipt's signature model so the audit chain covers mutation
    runs with the same rigor as red/green/refactor.
    """

    phase: Literal["mutation"] = "mutation"
    run_id: str
    test_command: str  # the mutmut invocation, e.g. "mutmut run --use-coverage ..."
    cwd: str
    exit_code: int
    started_at: str
    finished_at: str
    stdout_path: str
    stderr_path: Optional[str] = None
    stdout_sha256: str
    stderr_sha256: Optional[str] = None
    module: str = Field(..., min_length=1)
    target_score: Optional[int] = None
    mutation_score: Optional[float] = None
    killed: int = 0
    survived: int = 0
    skipped: int = 0
    timeout: int = 0
    status: Literal["passed", "failed", "waived", "skipped", "timeout", "blocked"] = "blocked"
    signature: str = Field(..., min_length=1)

    def compute_signature(self, secret: str) -> str:
        """Compute HMAC over the deterministic content of this receipt."""
        content = (
            f"{self.phase}|{self.run_id}|{self.test_command}|{self.cwd}|"
            f"{self.exit_code}|{self.started_at}|{self.finished_at}|"
            f"{self.stdout_sha256}|{self.stderr_sha256 or ''}|"
            f"{self.module}|{self.target_score}|{self.mutation_score}|"
            f"{self.killed}|{self.survived}|{self.skipped}|{self.timeout}|"
            f"{self.status}"
        )
        return hmac.new(
            secret.encode(), content.encode(), hashlib.sha256
        ).hexdigest()

    def verify_signature(self, secret: str) -> bool:
        expected = self.compute_signature(secret)
        return hmac.compare_digest(self.signature, expected)


class RunMetadata(BaseModel):
    run_id: str = Field(..., min_length=1)
    mode: Literal["feature", "bugfix", "refactor"]
    task: str = Field(..., min_length=1)
    cwd: str = Field(..., min_length=1)
    test_command: str = Field(..., min_length=1)
    started_at: str = Field(default_factory=now_iso)


class TddEvidence(BaseModel):
    """Agent-authored evidence summary. References receipts — does NOT embed logs."""

    metadata: RunMetadata
    target_component: str = Field(..., min_length=1)
    expected_behavior: str = Field(..., min_length=1)
    test_files_modified: List[str] = Field(..., min_length=1)
    impl_files_modified: List[str] = Field(..., min_length=1)
    files_refactored: List[str] = Field(default_factory=list)

    red: PhaseReceiptRef
    green: PhaseReceiptRef
    refactor: Optional[PhaseReceiptRef] = None
    mutation: Optional[MutationReceiptRef] = None

    failure_summary: List[str] = Field(default_factory=list)

    @field_validator("test_files_modified")
    @classmethod
    def paths_must_look_like_test_files(cls, v: List[str]) -> List[str]:
        for p in v:
            stem = Path(p).name.lower()
            if not (
                stem.startswith("test_")
                or stem.endswith("_test.py")
                or stem.endswith(".test.ts")
                or stem.endswith(".test.js")
                or stem.endswith(".test.tsx")
                or stem.endswith(".test.jsx")
                or stem.endswith("_test.go")
                or stem.endswith(".spec.ts")
                or stem.endswith(".spec.js")
                or stem.endswith(".spec.tsx")
                or stem.endswith(".spec.jsx")
            ):
                raise ValueError(
                    f"'{p}' does not look like a test file. "
                    "Expected names like test_*.py, *_test.go, *.test.ts, *.spec.js."
                )
        return v
