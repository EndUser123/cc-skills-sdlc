"""Layer 7 — OPERATIONAL: hook chain, hook-audit, hook-inventory, recursive failure detector."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from findings.models import EvidenceTier, Finding, Layer, Severity

RECURSIVE_FAILURE_DETECTOR = (
    Path(__file__).parent.parent.parent / ".claude" / "hooks" / "recursive_failure_detector.py"
)


def run(target: Path) -> list[Finding]:
    """Run Layer 7 OPERATIONAL analysis."""
    findings: list[Finding] = []

    # verify Tier 2 (hook chain + router)
    verify_findings = _run_verify_tier2(target)
    findings.extend(verify_findings)

    # hook-audit
    audit_findings = _run_hook_audit(target)
    findings.extend(audit_findings)

    # hook-inventory
    inv_findings = _run_hook_inventory(target)
    findings.extend(inv_findings)

    # recursive_failure_detector
    rfd_findings = _run_recursive_failure_detector(target)
    findings.extend(rfd_findings)

    # Check halt threshold before returning
    from orchestrator import check_halt
    check_halt("L7", findings)

    return findings


def _run_verify_tier2(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["verify", "--tier=2", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    findings.append(
                        Finding(
                            finding_id="L7-VERIFY-TIER2",
                            severity=Severity.MEDIUM,
                            layer=Layer.L7_OPERATIONAL,
                            title="Verify Tier 2 hook chain issue",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T3,
                            category="operational",
                        )
                    )
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    return findings


def _run_hook_audit(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["hook-audit", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    findings.append(
                        Finding(
                            finding_id="L7-HOOK-AUDIT",
                            severity=Severity.MEDIUM,
                            layer=Layer.L7_OPERATIONAL,
                            title="Hook audit finding",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T3,
                            category="operational",
                        )
                    )
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    return findings


def _run_hook_inventory(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    # Check for dead hooks (not invoked in 30 days)
    hook_dir = target / ".claude" / "hooks"
    if not hook_dir.exists():
        return findings

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for hook_file in hook_dir.rglob("*.py"):
        if hook_file.stem.startswith("_") or hook_file.stem == "__init__":
            continue
        try:
            mtime = datetime.fromtimestamp(hook_file.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                findings.append(
                    Finding(
                        finding_id=f"L7-DEAD-HOOK-{hook_file.stem}",
                        severity=Severity.LOW,
                        layer=Layer.L7_OPERATIONAL,
                        title="Dead hook file",
                        description=f"{hook_file.name} not modified in 30 days",
                        location=str(hook_file),
                        evidence_tier=EvidenceTier.T3,
                        category="operational",
                    )
                )
        except OSError:
            pass
    return findings


def _run_recursive_failure_detector(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not RECURSIVE_FAILURE_DETECTOR.exists():
        return findings

    try:
        result = subprocess.run(
            ["python", str(RECURSIVE_FAILURE_DETECTOR), str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    findings.append(
                        Finding(
                            finding_id="L7-RECURSIVE-DEP",
                            severity=Severity.CRITICAL,
                            layer=Layer.L7_OPERATIONAL,
                            title="Recursive dependency between hooks detected",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T2,
                            category="operational",
                        )
                    )
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    return findings
