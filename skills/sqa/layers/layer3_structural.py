"""Layer 3 — STRUCTURAL: circular deps, assertion guards, safety patterns."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from findings.models import EvidenceTier, Finding, Layer, Severity

logger = logging.getLogger(__name__)


def run(target: Path) -> list[Finding]:
    """Run Layer 3 STRUCTURAL analysis.

    Reuses:
    - meta-review ImportGraphAnalyzer for circular deps
    - harden for assertion guard + parameter validation
    - apply_safety_patterns for safety patterns
    """
    findings: list[Finding] = []

    # Circular dependency check via meta-review
    circ_findings = _check_circular_deps(target)
    findings.extend(circ_findings)

    # Assertion guards via harden
    guard_findings = _check_assertion_guards(target)
    findings.extend(guard_findings)

    # Safety patterns via apply_safety_patterns
    safety_findings = _check_safety_patterns(target)
    findings.extend(safety_findings)

    # Check halt threshold before returning
    from orchestrator import check_halt
    check_halt("L3", findings)

    return findings


def _check_circular_deps(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["meta-review", "--analyze=imports", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout:
            # Parse circular deps from output
            for line in result.stdout.splitlines():
                if "circular" in line.lower() or "cycle" in line.lower():
                    findings.append(
                        Finding(
                            finding_id="L3-CIRCULAR-DEP",
                            severity=Severity.MEDIUM,
                            layer=Layer.L3_STRUCTURAL,
                            title="Circular dependency detected",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T3,
                            category="structure",
                        )
                    )
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out after 60s")
    except FileNotFoundError:
        logger.warning("Command not found in PATH — skipping check")
    return findings


def _check_assertion_guards(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["harden", "--check=guards", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    findings.append(
                        Finding(
                            finding_id="L3-MISSING-GUARD",
                            severity=Severity.HIGH,
                            layer=Layer.L3_STRUCTURAL,
                            title="Missing defensive guard on external input",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T3,
                            category="security",
                        )
                    )
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out after 60s")
    except FileNotFoundError:
        logger.warning("Command not found in PATH — skipping check")
    return findings


def _check_safety_patterns(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["apply_safety_patterns", "--verify", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    findings.append(
                        Finding(
                            finding_id="L3-SAFETY-PATTERN-MISSING",
                            severity=Severity.MEDIUM,
                            layer=Layer.L3_STRUCTURAL,
                            title="Safety pattern violation",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T3,
                            category="safety",
                        )
                    )
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out after 60s")
    except FileNotFoundError:
        logger.warning("Command not found in PATH — skipping check")
    return findings
