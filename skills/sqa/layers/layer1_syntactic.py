"""Layer 1 — SYNTACTIC: ruff, mypy, AI Distiller structure analysis."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from findings.models import EvidenceTier, Finding, Layer, Severity

logger = logging.getLogger(__name__)


def _calculate_adaptive_timeout(target: Path, base_timeout: int = 60, max_timeout: int = 300) -> int:
    """Calculate adaptive timeout based on target complexity.

    Args:
        target: Path to analyze
        base_timeout: Base timeout in seconds (default 60)
        max_timeout: Maximum timeout cap (default 300 = 5 minutes)

    Returns:
        Timeout in seconds, scaled by complexity
    """
    # Count Python files as complexity metric
    py_files = list(target.rglob("*.py"))
    file_count = len(py_files)

    # Base timeout + per-file scaling (10ms per Python file, 50ms per test)
    per_file_scaling = file_count * 0.01  # 10ms per file

    # Estimate test files by looking for test_*.py or */test_*.py patterns
    test_files = [f for f in py_files if "test_" in f.name or "tests" in f.parts]
    test_scaling = len(test_files) * 0.05  # 50ms per test file

    calculated_timeout = base_timeout + per_file_scaling + test_scaling
    return min(int(calculated_timeout), max_timeout)


def _run_ruff(target: Path) -> list[Finding]:
    """Run ruff check on Python files."""
    findings: list[Finding] = []
    py_files = list(target.rglob("*.py"))
    if not py_files:
        return findings

    timeout = _calculate_adaptive_timeout(target)

    try:
        result = subprocess.run(
            ["ruff", "check", str(target), "--output-format=json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # ruff returns 0 (no issues), 1 (issues found), >=2 (error)
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                for item in data:
                    loc = item.get("location", {})
                    findings.append(
                        Finding(
                            finding_id=f"L1-RUFF-{item.get('code', 'UNK')}",
                            severity=Severity.MEDIUM,  # ruff violations default MEDIUM
                            layer=Layer.L1_SYNTACTIC,
                            title=item.get("message", "Ruff violation"),
                            description=item.get("description", ""),
                            location=f"{item.get('filename')}:{loc.get('row', 0)}",
                            evidence_tier=EvidenceTier.T1,
                            category="syntax",
                        )
                    )
            except json.JSONDecodeError:
                pass
    except subprocess.TimeoutExpired:
        findings.append(
            Finding(
                finding_id="L1-RUFF-TIMEOUT",
                severity=Severity.MEDIUM,
                layer=Layer.L1_SYNTACTIC,
                title=f"Ruff check timed out after {timeout}s",
                description=f"Ruff subprocess exceeded {timeout}s timeout (adaptive based on {len(py_files)} files)",
                evidence_tier=EvidenceTier.T3,
                category="timeout",
            )
        )
    except FileNotFoundError:
        logger.warning("ruff not found in PATH — skipping syntactic analysis. Install ruff to enable.")
    return findings


def _run_mypy(target: Path) -> list[Finding]:
    """Run mypy type check on Python files."""
    findings: list[Finding] = []
    py_files = list(target.rglob("*.py"))
    if not py_files:
        return findings

    timeout = _calculate_adaptive_timeout(target)

    try:
        result = subprocess.run(
            ["mypy", str(target), "--output-format=json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                for item in data:
                    findings.append(
                        Finding(
                            finding_id=f"L1-MYPY-{item.get('code', 'UNK')}",
                            severity=Severity.HIGH,
                            layer=Layer.L1_SYNTACTIC,
                            title=item.get("message", "Type error"),
                            description=f"{item.get('file', '')}:{item.get('line', 0)}",
                            location=f"{item.get('file')}:{item.get('line', 0)}",
                            evidence_tier=EvidenceTier.T2,
                            category="type",
                        )
                    )
            except json.JSONDecodeError:
                pass
    except subprocess.TimeoutExpired:
        findings.append(
            Finding(
                finding_id="L1-MYPY-TIMEOUT",
                severity=Severity.MEDIUM,
                layer=Layer.L1_SYNTACTIC,
                title=f"Mypy timed out after {timeout}s",
                description=f"Mypy subprocess exceeded {timeout}s timeout (adaptive based on {len(py_files)} files)",
                evidence_tier=EvidenceTier.T3,
                category="timeout",
            )
        )
    except FileNotFoundError:
        logger.warning("mypy not found in PATH — skipping type checking. Install mypy to enable.")
    return findings


def _run_aid(target: Path) -> list[Finding]:
    """Run AI Distiller structure analysis."""
    findings: list[Finding] = []
    timeout = _calculate_adaptive_timeout(target)

    try:
        result = subprocess.run(
            ["aid", "distill", "--path", str(target), "--format=json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                for item in data.get("structures", []):
                    findings.append(
                        Finding(
                            finding_id=f"L1-AID-{item.get('id', 'UNK')}",
                            severity=Severity.LOW,
                            layer=Layer.L1_SYNTACTIC,
                            title=item.get("name", "Structure issue"),
                            description=item.get("description", ""),
                            evidence_tier=EvidenceTier.T3,
                            category="structure",
                        )
                    )
            except json.JSONDecodeError:
                pass
    except subprocess.TimeoutExpired:
        logger.warning("aid distill timed out — skipping structure analysis")
    except FileNotFoundError:
        logger.warning("aid command not found in PATH — skipping structure analysis")
    return findings


def run(target: Path) -> list[Finding]:
    """Run Layer 1 SYNTACTIC analysis."""
    findings: list[Finding] = []

    # ruff on Python files
    ruff_findings = _run_ruff(target)
    findings.extend(ruff_findings)

    # mypy on Python files
    mypy_findings = _run_mypy(target)
    findings.extend(mypy_findings)

    # AI Distiller structure analysis
    aid_findings = _run_aid(target)
    findings.extend(aid_findings)

    # Check halt threshold before returning
    from orchestrator import check_halt
    check_halt("L1", findings)

    return findings
