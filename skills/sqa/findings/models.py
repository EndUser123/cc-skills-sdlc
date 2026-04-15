"""Findings data models for SQA Orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Layer(Enum):
    """SQA quality layers."""

    L0_PREDICTIVE = "L0_PREDICTIVE"
    L1_SYNTACTIC = "L1_SYNTACTIC"
    L2_SEMANTIC = "L2_SEMANTIC"
    L3_STRUCTURAL = "L3_STRUCTURAL"
    L4_REQUIREMENTS = "L4_REQUIREMENTS"
    L5_SECURITY = "L5_SECURITY"
    L6_PERFORMANCE = "L6_PERFORMANCE"
    L7_OPERATIONAL = "L7_OPERATIONAL"
    META = "META"


class Severity(Enum):
    """Finding severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceTier(Enum):
    """Evidence quality tiers."""

    T1 = "T1"  # Direct execution/observation
    T2 = "T2"  # Instrumented test
    T3 = "T3"  # Logical inference
    T4 = "T4"  # Heuristic/assumption


@dataclass
class Evidence:
    """Evidence supporting a finding."""

    tier: EvidenceTier
    description: str
    location: str | None = None  # file:line when applicable


@dataclass
class Finding:
    """A quality finding from one layer."""

    finding_id: str  # e.g. "L1-001"
    severity: Severity
    layer: Layer
    title: str
    description: str
    location: str | None = None  # file:line when applicable
    evidence_tier: EvidenceTier = EvidenceTier.T3
    consensus: int = 1  # Number of layers that found this issue
    category: str = "general"
    evidence: list[Evidence] = field(default_factory=list)
    # Weighted scoring fields (CHANGE-001)
    reproducibility: float = 0.5  # [0.0, 1.0]
    recency: float = 0.5  # [0.0, 1.0]
    impact: float = 0.5  # [0.0, 1.0]

    def __post_init__(self) -> None:
        """Clamp weighted scoring fields to valid range [0.0, 1.0]."""
        self.reproducibility = max(0.0, min(1.0, self.reproducibility))
        self.recency = max(0.0, min(1.0, self.recency))
        self.impact = max(0.0, min(1.0, self.impact))

    def key(self) -> tuple[str, str, str, str]:
        """Deduplication key: (file, line, category, issue_type)."""
        loc = self.location or ""
        parts = loc.rsplit(":", 1)
        file = parts[0] if parts else ""
        line = parts[1] if len(parts) > 1 else ""
        return (file, line, self.category, self.title)


@dataclass
class AuditEntry:
    """Record of a skill/tool invocation."""

    timestamp: str  # ISO format
    skill: str
    exit_code: int | None
    finding_count: int
    notes: str | None = None


@dataclass
class SQAReport:
    """Complete SQA analysis report."""

    findings: list[Finding] = field(default_factory=list)
    health_score: int = 100
    layers_completed: list[str] = field(default_factory=list)
    audit_trail: list[AuditEntry] = field(default_factory=list)
    target: str = ""
    timestamp: str = ""

    def add_finding(self, finding: Finding) -> None:
        """Add a finding (append-only)."""
        self.findings.append(finding)

    def add_audit(self, entry: AuditEntry) -> None:
        """Add an audit entry (append-only)."""
        self.audit_trail.append(entry)

    def compute_health_score(self) -> int:
        """Compute health score from deduplicated severity counts.

        Uses deduplicated severity counts (D4 deduplication removes
        consensus duplicates before scoring). Negative scores preserved.
        Each finding's severity weight is multiplied by its evidence tier factor:
        T1=1.0x, T2=0.75x, T3=0.5x, T4=0.25x — reducing noise from
        heuristic findings while preserving signal from execution-verified ones.
        """
        # Deduplicate findings by key, keeping highest severity per key
        seen: dict[tuple[str, str, str, str], Finding] = {}
        for f in self.findings:
            k = f.key()
            if k not in seen or _severity_order(seen[k].severity) < _severity_order(f.severity):
                seen[k] = f

        unique = list(seen.values())

        # Evidence tier weight factors
        tier_weights = {
            EvidenceTier.T1: 1.0,
            EvidenceTier.T2: 0.75,
            EvidenceTier.T3: 0.5,
            EvidenceTier.T4: 0.25,
        }

        # Severity base weights
        severity_weights = {
            Severity.CRITICAL: 20,
            Severity.HIGH: 10,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
        }

        deductions = 0.0
        for f in unique:
            tier_factor = tier_weights.get(f.evidence_tier, 0.5)
            severity_weight = severity_weights.get(f.severity, 0)
            deductions += severity_weight * tier_factor

        score = 100 - deductions
        return max(-100, int(score))

    def deduplicated_findings(self) -> list[Finding]:
        """Return findings deduplicated by (file, line, category, title).

        For duplicate keys, keeps the finding with highest severity.
        """
        seen: dict[tuple[str, str, str, str], Finding] = {}
        for f in self.findings:
            k = f.key()
            if k not in seen or _severity_order(seen[k].severity) < _severity_order(f.severity):
                seen[k] = f
        return list(seen.values())

    @property
    def health_band(self) -> str:
        """Return health band label based on computed health_score.

        Band assignment: 95-100 NOMINAL, 80-94 MINOR, 50-79 MIDDLE, <50 CRITICAL.
        """
        score = self.health_score
        if score >= 95:
            return "NOMINAL"
        elif score >= 80:
            return "MINOR"
        elif score >= 50:
            return "MIDDLE"
        else:
            return "CRITICAL"


def _compute_per_finding_score(f: Finding) -> float:
    """Compute per-finding score scaled to [0, 100] range.

    Formula: (reproducibility * 0.3 + recency * 0.2 + impact * 0.5) * 100
    All inputs are clamped to [0.0, 1.0] by Finding.__post_init__.
    """
    return (f.reproducibility * 0.3 + f.recency * 0.2 + f.impact * 0.5) * 100


def _compute_layer_weights(findings: list[Finding]) -> dict[Layer, float]:
    """Compute normalized layer weights from findings list.

    Base weights: L2 0.30, L3 0.25, L5 0.20, L4 0.00, residual 0.25
    split across L1/L6/L7 (~8.3% each). If a layer has no findings,
    its weight is redistributed proportionally to active layers.
    Weights are normalized to sum to 1.0.
    """
    # Base weights per CHANGE-001 spec
    base: dict[Layer, float] = {
        Layer.L2_SEMANTIC: 0.30,
        Layer.L3_STRUCTURAL: 0.25,
        Layer.L5_SECURITY: 0.20,
        Layer.L4_REQUIREMENTS: 0.00,
        Layer.L1_SYNTACTIC: 0.083,
        Layer.L6_PERFORMANCE: 0.083,
        Layer.L7_OPERATIONAL: 0.083,
    }

    # Determine which layers have findings
    active_layers = {f.layer for f in findings if f.layer in base}
    if not active_layers:
        return dict.fromkeys(base, 0.0)

    # Redistribute inactive layer weights proportionally to active layers
    inactive_weight = sum(base[layer] for layer in base if layer not in active_layers)
    active_count = len(active_layers)
    if active_count == 0:
        return base

    extra_per_active = inactive_weight / active_count
    weights = {}
    total = 0.0
    for layer, w in base.items():
        if layer in active_layers:
            new_w = w + extra_per_active
            weights[layer] = new_w
            total += new_w
        else:
            weights[layer] = 0.0

    # Normalize to sum to 1.0
    if total > 0:
        weights = {layer: w / total for layer, w in weights.items()}
    return weights


def _severity_order(sev: Severity) -> int:
    """Return sort order for severity (higher = more severe)."""
    return {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}[sev]
