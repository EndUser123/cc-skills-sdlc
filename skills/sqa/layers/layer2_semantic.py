"""Layer 2 — SEMANTIC: pytest + diagnose on failures."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from findings.models import EvidenceTier, Finding, Layer, Severity

logger = logging.getLogger(__name__)


def run(target: Path) -> list[Finding]:
    """Run Layer 2 SEMANTIC analysis.

    Runs verify (pytest) and diagnose on failures.
    """
    findings: list[Finding] = []

    # Run pytest via verify skill
    try:
        result = subprocess.run(
            ["verify", "--tier=1", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # If pytest fails (exit code != 0), check for failures
        has_failures = result.returncode != 0

        if has_failures:
            findings.append(
                Finding(
                    finding_id="L2-VERITY-PYTEST-FAILURES",
                    severity=Severity.HIGH,
                    layer=Layer.L2_SEMANTIC,
                    title="Pytest tests failed",
                    description=result.stdout[:500] if result.stdout else "pytest exited non-zero",
                    evidence_tier=EvidenceTier.T2,
                    category="test",
                )
            )
            # Run diagnose on failures
            diag_findings = _run_diagnose(target)
            findings.extend(diag_findings)
    except subprocess.TimeoutExpired:
        findings.append(
            Finding(
                finding_id="L2-VERITY-TIMEOUT",
                severity=Severity.MEDIUM,
                layer=Layer.L2_SEMANTIC,
                title="Verify (pytest) timed out after 60s",
                description="pytest subprocess exceeded 60s timeout",
                evidence_tier=EvidenceTier.T3,
                category="timeout",
            )
        )
    except FileNotFoundError:
        logger.warning("verify skill not found in PATH — skipping semantic analysis")

    # Check for test files
    test_files = list(target.rglob("test_*.py")) + list(target.rglob("*_test.py"))
    if not test_files:
        findings.append(
            Finding(
                finding_id="L2-NO-TEST-FILES",
                severity=Severity.MEDIUM,
                layer=Layer.L2_SEMANTIC,
                title="No test files found",
                description="Target has no test_*.py or *_test.py files",
                evidence_tier=EvidenceTier.T3,
                category="requirements",
            )
        )

    # Check halt threshold before returning
    from orchestrator import check_halt
    check_halt("L2", findings)

    return findings


def _run_diagnose(target: Path) -> list[Finding]:
    """Run diagnose if pytest failures detected."""
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["diagnose", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout:
            findings.append(
                Finding(
                    finding_id="L2-DIAGNOSE-RESULTS",
                    severity=Severity.MEDIUM,
                    layer=Layer.L2_SEMANTIC,
                    title="Diagnose hypothesis results",
                    description=result.stdout[:500],
                    evidence_tier=EvidenceTier.T3,
                    category="diagnosis",
                )
            )
    except subprocess.TimeoutExpired:
        logger.warning("diagnose timed out after 60s — returning findings so far")
        return findings  # Return findings collected so far
    except FileNotFoundError:
        logger.warning("diagnose skill not found in PATH — skipping root cause analysis")
    return findings
