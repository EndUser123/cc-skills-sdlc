"""Layer 4 — REQUIREMENTS: gto, spec-compliance, artifact status, contradiction check.

HARD DEPENDENCY: Layer 4 MUST NOT execute if Layer 2 (SEMANTIC) reported failures.
The orchestrator enforces this; this layer just runs its checks.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from findings.models import EvidenceTier, Finding, Layer, Severity

# Contradiction detection: simplified approach
# For will/won't, does/doesn't, can/cannot patterns: compare verb words
# to catch contradictions even when objects differ (e.g., "process all" vs "process batch")


def _check_contradictions(target: Path) -> list[Finding]:
    """Lightweight pre-mortem contradiction check on spec files.

    Scans PRD.md, ARD.md, CHANGELOG.md, README.md for contradictory statements.
    Uses simple pattern matching — not LLM-based — for fast one-shot detection.

    Contradiction pairs where the core VERB is the same but polarity differs:
    - will X vs won't X (same verb X = contradiction)
    - can X vs can't/cannot X (same verb X = contradiction)
    - does X vs doesn't X (same verb X = contradiction)
    - is X vs isn't/is not X (same noun X = contradiction)
    - enabled vs disabled (direct opposition)
    """
    findings: list[Finding] = []

    # Spec files to check (order of preference)
    spec_files = ["PRD.md", "ARD.md", "CHANGELOG.md", "README.md"]

    for filename in spec_files:
        file_path = target / filename
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(errors="ignore")
        except OSError:
            continue

        # Collect contradiction descriptors
        contradictions: list[str] = []

        # ---- will / won't ----
        _collect_verb_contradictions(content, r"\bwill\s+(\w+)", r"\bwon't\s+(\w+)", contradictions)
        _collect_verb_contradictions(content, r"\bwill\s+(\w+)", r"\bwill\s+not\s+(\w+)", contradictions)
        # ---- does / doesn't ----
        _collect_verb_contradictions(content, r"\bdoes\s+(\w+)", r"\bdoesn't\s+(\w+)", contradictions)
        _collect_verb_contradictions(content, r"\bdoes\s+(\w+)", r"\bdoes\s+not\s+(\w+)", contradictions)
        # ---- can / can't / cannot ----
        _collect_verb_contradictions(content, r"\bcan\s+(\w+)", r"\bcan't\s+(\w+)", contradictions)
        _collect_verb_contradictions(content, r"\bcan\s+(\w+)", r"\bcannot\s+(\w+)", contradictions)
        # ---- is / isn't / is not ----
        _collect_verb_contradictions(content, r"\bis\s+(\w+)", r"\bisn't\s+(\w+)", contradictions)
        _collect_verb_contradictions(content, r"\bis\s+(\w+)", r"\bis\s+not\s+(\w+)", contradictions)
        # ---- enabled / disabled ----
        if re.search(r"\benabled\b", content, re.IGNORECASE) and re.search(r"\bdisabled\b", content, re.IGNORECASE):
            contradictions.append("enabled vs disabled")
        # ---- supports / doesn't support ----
        _collect_verb_contradictions(content, r"\bsupports?\s+(\w+)", r"\bdoesn't\s+support\s+(\w+)", contradictions)
        _collect_verb_contradictions(content, r"\bsupports?\s+(\w+)", r"\bdoes\s+not\s+support\s+(\w+)", contradictions)
        # ---- uses / doesn't use ----
        _collect_verb_contradictions(content, r"\buses?\s+(\w+)", r"\bdoesn't\s+use\s+(\w+)", contradictions)
        _collect_verb_contradictions(content, r"\buses?\s+(\w+)", r"\bdoes\s+not\s+use\s+(\w+)", contradictions)

        if contradictions:
            finding_id = f"L4-CONTRADICTION-{filename.replace('.', '').upper()}"
            unique = list(dict.fromkeys(contradictions))  # preserve order, remove dupes
            findings.append(
                Finding(
                    finding_id=finding_id,
                    severity=Severity.MEDIUM,
                    layer=Layer.L4_REQUIREMENTS,
                    title=f"Contradiction detected in {filename}",
                    description=f"Found {len(unique)} contradictory statement(s): {'; '.join(unique[:5])}"
                    + ("..." if len(unique) > 5 else ""),
                    evidence_tier=EvidenceTier.T3,
                    category="requirements",
                )
            )

    return findings


def _collect_verb_contradictions(
    content: str, pos_pattern: str, neg_pattern: str, out: list[str]
) -> None:
    """Check for verb contradictions and append descriptions to out list."""
    pos_matches = re.findall(pos_pattern, content, re.IGNORECASE)
    neg_matches = re.findall(neg_pattern, content, re.IGNORECASE)
    if not pos_matches or not neg_matches:
        return
    # Normalize to set of verbs for overlap detection
    pos_verbs = {m.lower() for m in pos_matches}
    neg_verbs = {m.lower() for m in neg_matches}
    overlap = pos_verbs & neg_verbs
    for verb in overlap:
        out.append(f"'{verb}' — will/can/does vs won't/can't/doesn't")


def run(target: Path) -> list[Finding]:
    """Run Layer 4 REQUIREMENTS analysis."""
    findings: list[Finding] = []

    # Pre-mortem contradiction check (lightweight, runs first)
    contradiction_findings = _check_contradictions(target)
    findings.extend(contradiction_findings)

    # gto gap analysis
    gto_findings = _run_gto(target)
    findings.extend(gto_findings)

    # spec-compliance check
    spec_findings = _run_spec_compliance(target)
    findings.extend(spec_findings)

    # Artifact status (CHANGELOG, README sync)
    artifact_findings = _check_artifact_status(target)
    findings.extend(artifact_findings)

    # Check halt threshold before returning
    from orchestrator import check_halt
    check_halt("L4", findings)

    return findings


def _run_gto(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["gto", "analyze", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout:
            findings.append(
                Finding(
                    finding_id="L4-GTO-RESULTS",
                    severity=Severity.LOW,
                    layer=Layer.L4_REQUIREMENTS,
                    title="GTO gap analysis results",
                    description=result.stdout[:500],
                    evidence_tier=EvidenceTier.T3,
                    category="requirements",
                )
            )
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    return findings


def _run_spec_compliance(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["spec-compliance", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    findings.append(
                        Finding(
                            finding_id="L4-SPEC-NONCOMPLIANCE",
                            severity=Severity.MEDIUM,
                            layer=Layer.L4_REQUIREMENTS,
                            title="Spec compliance violation",
                            description=line.strip(),
                            evidence_tier=EvidenceTier.T3,
                            category="requirements",
                        )
                    )
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    return findings


def _check_artifact_status(target: Path) -> list[Finding]:
    """Check CHANGELOG is in sync with git tags (last 30 days)."""
    findings: list[Finding] = []

    # Check CHANGELOG exists
    changelog = target / "CHANGELOG.md"
    if not changelog.exists():
        findings.append(
            Finding(
                finding_id="L4-MISSING-CHANGELOG",
                severity=Severity.LOW,
                layer=Layer.L4_REQUIREMENTS,
                title="Missing CHANGELOG.md",
                description="No CHANGELOG.md found in target",
                evidence_tier=EvidenceTier.T3,
                category="requirements",
            )
        )
        return findings

    # Check for git tags in last 30 days without CHANGELOG entries
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        result = subprocess.run(
            ["git", "tag", f"--since={cutoff}"],
            capture_output=True,
            text=True,
            cwd=str(target),
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            recent_tags = result.stdout.strip().splitlines()
            changelog_text = changelog.read_text(errors="ignore")
            for tag in recent_tags:
                if tag not in changelog_text:
                    findings.append(
                        Finding(
                            finding_id="L4-CHANGELOG-OUT-OF-SYNC",
                            severity=Severity.MEDIUM,
                            layer=Layer.L4_REQUIREMENTS,
                            title="CHANGELOG missing recent entries",
                            description=f"Git tag '{tag}' created in last 30 days with no CHANGELOG entry",
                            evidence_tier=EvidenceTier.T3,
                            category="requirements",
                        )
                    )
                    break  # One finding per layer is enough
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass

    return findings
