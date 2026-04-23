"""Evidence collection for TDD phases.

Collects, stores, and retrieves test evidence across RED/GREEN/REGRESSION phases.
All evidence is stored in the refactor artifacts directory under `state/`.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ─── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass
class PhaseEvidence:
    """Evidence for a single TDD phase."""

    finding_id: str
    phase: str  # "RED" | "GREEN" | "REGRESSION"
    test_file: str
    test_passed: bool
    stdout: str
    stderr: str
    returncode: int
    duration_seconds: float
    timestamp: str
    git_commit: str | None = None


@dataclass
class FindingEvidence:
    """Complete evidence for a single finding across all phases."""

    finding_id: str
    file: str
    line: int
    description: str
    phases: list[PhaseEvidence]
    rollback_commits: list[str]
    overall_pass: bool


# ─── Core functions ────────────────────────────────────────────────────────────


def collect_test_evidence(
    test_path: str | Path,
    phase: str,
    finding_id: str,
    artifacts_dir: str | Path | None = None,
) -> PhaseEvidence:
    """Run a test and collect execution evidence.

    Args:
        test_path: Path to the test file or test directory.
        phase: TDD phase name (RED, GREEN, REGRESSION).
        finding_id: Unique identifier for the finding being tested.
        artifacts_dir: Base artifacts directory. Defaults to env var or CWD/.artifacts.

    Returns:
        PhaseEvidence with execution results.
    """
    test_path = Path(test_path)
    start = datetime.now(timezone.utc)

    result = subprocess.run(
        ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    duration = (datetime.now(timezone.utc) - start).total_seconds()

    git_commit = None
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        pass

    evidence = PhaseEvidence(
        finding_id=finding_id,
        phase=phase,
        test_file=str(test_path),
        test_passed=result.returncode == 0,
        stdout=result.stdout[:8000],  # Truncate to avoid bloat
        stderr=result.stderr[:4000],
        returncode=result.returncode,
        duration_seconds=duration,
        timestamp=datetime.now(timezone.utc).isoformat(),
        git_commit=git_commit,
    )

    if artifacts_dir:
        _store_phase_evidence(evidence, Path(artifacts_dir))

    return evidence


def verify_tdd_red(
    finding_id: str,
    test_path: str | Path,
    artifacts_dir: str | Path | None = None,
) -> tuple[bool, PhaseEvidence]:
    """Verify RED phase: characterization test must FAIL before changes.

    Args:
        finding_id: Unique identifier for the finding.
        test_path: Path to the characterization test.
        artifacts_dir: Base artifacts directory.

    Returns:
        (is_red, evidence) — is_red is True when test fails as expected.
    """
    evidence = collect_test_evidence(test_path, "RED", finding_id, artifacts_dir)
    # RED phase passes when the test FAILS (proving the bug exists)
    return (not evidence.test_passed, evidence)


def verify_tdd_green(
    finding_id: str,
    test_path: str | Path,
    artifacts_dir: str | Path | None = None,
) -> tuple[bool, PhaseEvidence]:
    """Verify GREEN phase: refactored code must PASS the characterization test.

    Args:
        finding_id: Unique identifier for the finding.
        test_path: Path to the characterization test.
        artifacts_dir: Base artifacts directory.

    Returns:
        (is_green, evidence) — is_green is True when test passes.
    """
    evidence = collect_test_evidence(test_path, "GREEN", finding_id, artifacts_dir)
    return (evidence.test_passed, evidence)


def verify_regression(
    finding_id: str,
    test_paths: list[str | Path],
    artifacts_dir: str | Path | None = None,
) -> tuple[bool, list[PhaseEvidence]]:
    """Verify REGRESSION phase: no existing tests should fail.

    Args:
        finding_id: Unique identifier for the finding.
        test_paths: List of test paths to run.
        artifacts_dir: Base artifacts directory.

    Returns:
        (no_regression, evidences) — no_regression is True when all tests pass.
    """
    evidences: list[PhaseEvidence] = []
    for path in test_paths:
        ev = collect_test_evidence(path, "REGRESSION", finding_id, artifacts_dir)
        evidences.append(ev)

    all_passed = all(e.test_passed for e in evidences)
    return (all_passed, evidences)


def get_evidence_collector(
    finding_id: str,
    artifacts_dir: str | Path,
) -> FindingEvidence | None:
    """Load all stored evidence for a finding.

    Args:
        finding_id: Unique identifier for the finding.
        artifacts_dir: Base artifacts directory.

    Returns:
        FindingEvidence if evidence exists, else None.
    """
    artifacts_dir = Path(artifacts_dir)
    state_dir = artifacts_dir / "state"
    evidence_file = state_dir / f"evidence_{finding_id}.json"

    if not evidence_file.exists():
        return None

    try:
        data = json.loads(evidence_file.read_text(encoding="utf-8"))
        return FindingEvidence(
            finding_id=data["finding_id"],
            file=data.get("file", ""),
            line=data.get("line", 0),
            description=data.get("description", ""),
            phases=[PhaseEvidence(**p) for p in data.get("phases", [])],
            rollback_commits=data.get("rollback_commits", []),
            overall_pass=data.get("overall_pass", False),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_finding_evidence(
    finding_id: str,
    file: str,
    line: int,
    description: str,
    artifacts_dir: str | Path,
) -> None:
    """Create or update finding metadata in the consolidated evidence file.

    Call this before collecting phase evidence to set the finding's metadata.
    """
    artifacts_dir = Path(artifacts_dir)
    state_dir = artifacts_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    consolidated_file = state_dir / f"evidence_{finding_id}.json"

    if consolidated_file.exists():
        try:
            data = json.loads(consolidated_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError, TypeError):
            data = {}
    else:
        data = {}

    data.update({
        "finding_id": finding_id,
        "file": file,
        "line": line,
        "description": description,
        "rollback_commits": data.get("rollback_commits", []),
        "overall_pass": data.get("overall_pass", False),
    })
    consolidated_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _store_phase_evidence(evidence: PhaseEvidence, artifacts_dir: Path) -> None:
    """Append phase evidence to the consolidated finding file."""
    state_dir = artifacts_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    consolidated_file = state_dir / f"evidence_{evidence.finding_id}.json"

    if consolidated_file.exists():
        try:
            data = json.loads(consolidated_file.read_text(encoding="utf-8"))
            phases = [PhaseEvidence(**p) for p in data.get("phases", [])]
        except (json.JSONDecodeError, KeyError, TypeError):
            phases = []
    else:
        phases = []

    phases.append(evidence)
    data["phases"] = [asdict(p) for p in phases]
    consolidated_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
