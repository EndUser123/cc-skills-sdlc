"""Meta-Synthesis Layer: consensus detection, blind-spot detection, evidence quality."""

from __future__ import annotations

import dataclasses
from collections import defaultdict

from findings.models import EvidenceTier, Finding, Layer, Severity, _severity_order

# CHANGE-002: Evidence citation allowlist (case-insensitive)
ALLOWLIST: set[str] = {"architectural", "design", "process"}


def _enforce_evidence_citations(
    findings: list[Finding],
) -> tuple[list[Finding], int]:
    """Downgrade T1/T2/T3 findings missing location to T3 (not T4).

    Architectural/design/process findings are exempt regardless of location.
    Uses dataclasses.replace() for immutability (no in-place mutation).

    Returns (new_findings, downgrade_count).
    """
    new_findings: list[Finding] = []
    downgrade_count = 0
    allowlist_lower = {c.lower() for c in ALLOWLIST}

    for f in findings:
        if f.evidence_tier == EvidenceTier.T4:
            # Already lowest tier, no action needed
            new_findings.append(f)
            continue
        if f.location is None and f.category.lower() not in allowlist_lower:
            # Downgrade to T3
            new_f = dataclasses.replace(f, evidence_tier=EvidenceTier.T3)
            new_findings.append(new_f)
            downgrade_count += 1
        else:
            new_findings.append(f)

    return new_findings, downgrade_count


def run_meta(all_findings: list[Finding]) -> list[Finding]:
    """Run meta-synthesis on all findings from all layers.

    1. Evidence enforcement: downgrade T1/T2/T3 findings missing location to T3
    2. Consensus detection: 2+ layers agree on same file:line:category
    3. Blind-spot detection: layer was available but found nothing
    4. Evidence quality check per evidence-tiers
    """
    meta_findings: list[Finding] = []

    # Evidence enforcement (CHANGE-002): before consensus to affect severity
    enforced_findings, downgrade_count = _enforce_evidence_citations(all_findings)
    if downgrade_count > 0:
        meta_findings.append(
            Finding(
                finding_id=f"META-EVIDENCE-DOWNGRADE-{downgrade_count}",
                severity=Severity.LOW,
                layer=Layer.META,
                title=f"Evidence downgrade: {downgrade_count} finding(s) missing location",
                description=f"{downgrade_count} finding(s) were downgraded from T1/T2/T3 to T3 for missing location",
                evidence_tier=EvidenceTier.T4,
                category="evidence",
            )
        )

    # Consensus detection
    consensus_findings = _detect_consensus(enforced_findings)
    meta_findings.extend(consensus_findings)

    # Blind-spot detection
    blind_findings = _detect_blind_spots(enforced_findings)
    meta_findings.extend(blind_findings)

    # Evidence quality check
    quality_findings = _check_evidence_quality(enforced_findings)
    meta_findings.extend(quality_findings)

    # Check halt threshold before returning
    from orchestrator import check_halt
    check_halt("META", meta_findings)

    return meta_findings


def _detect_consensus(all_findings: list[Finding]) -> list[Finding]:
    """Find findings agreed on by 2+ layers at same file:line:category."""
    # Group by (file, line, category)
    groups: dict[tuple, list[Finding]] = defaultdict(list)
    for f in all_findings:
        if f.location:
            groups[(f.location, f.category)].append(f)

    consensus_findings: list[Finding] = []
    for (loc, cat), finds in groups.items():
        layers = {f.layer for f in finds}
        if len(layers) >= 2:
            max_severity = max(finds, key=lambda f: _severity_order(f.severity)).severity
            consensus_findings.append(
                Finding(
                    finding_id=f"META-CONSENSUS-{loc}-{cat}".replace(":", "-").replace("/", "-"),
                    severity=max_severity,  # Use highest severity from consensus
                    layer=Layer.META,
                    title=f"Consensus: {len(layers)} layers agree on same issue",
                    description=f"Issue at {loc} (category={cat}) found by {len(layers)} layers: {', '.join(lyr.value for lyr in layers)}",
                    location=loc,
                    evidence_tier=EvidenceTier.T3,
                    consensus=len(layers),
                    category=cat,
                )
            )
    return consensus_findings


def _detect_blind_spots(all_findings: list[Finding]) -> list[Finding]:
    """Detect quality categories where a layer WAS available but found nothing.

    A blind-spot finding is NOT generated when a layer was skipped via D5 graceful degradation.
    We only flag when a layer ran but produced zero findings for its expected categories.
    """
    meta_findings: list[Finding] = []

    # Categories each layer should cover
    layer_categories = {
        Layer.L0_PREDICTIVE: {
            "logic",
            "quality",
            "io",
            "security",
            "performance",
            "testing",
            "state",
        },
        Layer.L1_SYNTACTIC: {"syntax", "type", "structure"},
        Layer.L2_SEMANTIC: {"test", "diagnosis"},
        Layer.L3_STRUCTURAL: {"structure", "security", "safety"},
        Layer.L4_REQUIREMENTS: {"requirements"},
        Layer.L5_SECURITY: {"security", "safety"},
        Layer.L6_PERFORMANCE: {"performance"},
        Layer.L7_OPERATIONAL: {"operational"},
    }

    # What categories were actually found by each layer
    layer_found_categories: dict[Layer, set[str]] = defaultdict(set)
    for f in all_findings:
        if f.layer in layer_categories:
            layer_found_categories[f.layer].add(f.category)

    # Critical categories that warrant MEDIUM severity when absent
    _critical_categories = {"security", "safety", "logic", "correctness"}
    # Check for blind spots
    for layer, expected_cats in layer_categories.items():
        found_cats = layer_found_categories.get(layer, set())
        missing_cats = expected_cats - found_cats
        if missing_cats:
            # Layer ran but found nothing in these categories
            for cat in missing_cats:
                # SECURITY/CRITICAL categories → MEDIUM, others → LOW (Change C)
                severity = Severity.MEDIUM if cat in _critical_categories else Severity.LOW
                meta_findings.append(
                    Finding(
                        finding_id=f"META-BLIND-{layer.value}-{cat}",
                        severity=severity,
                        layer=Layer.META,
                        title=f"Blind-spot: {layer.value} available but found no {cat} issues",
                        description=f"Layer {layer.value} was available but produced no findings for category '{cat}'. Available categories: {expected_cats}, Found: {found_cats}",
                        evidence_tier=EvidenceTier.T4,
                        category=cat,
                    )
                )

    return meta_findings


def _check_evidence_quality(all_findings: list[Finding]) -> list[Finding]:
    """Cap confidence per evidence-tiers spec."""
    quality_findings: list[Finding] = []

    for f in all_findings:
        if f.evidence_tier == EvidenceTier.T4:
            # Heuristic finding — flag for review
            quality_findings.append(
                Finding(
                    finding_id=f"META-EVIDENCE-Q-{f.finding_id}",
                    severity=Severity.LOW,
                    layer=Layer.META,
                    title=f"Evidence quality cap: {f.finding_id} uses T4 heuristic",
                    description=f"Finding {f.finding_id} capped at T4 (heuristic) — verify with T1/T2 evidence",
                    evidence_tier=EvidenceTier.T4,
                    category="evidence",
                )
            )

    return quality_findings
