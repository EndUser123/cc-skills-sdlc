"""
Blind Spot Detector for Unified Code Inspection

Detects categories (security, performance, etc.) that haven't been
checked in recent reviews for this codebase, but should have been
based on code risk patterns.

Only speaks up when confident - requires actual risk signal in code.
"""

from __future__ import annotations

import json
import os
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


# Categories agents check
CATEGORIES = [
    "security",
    "performance",
    "logic",
    "tests",
    "compliance",
    "quality",
    "conventions",
    "state_machine",
    "io_validation",
    "invariants",
]


# Risk patterns per category - what in code suggests this category should be checked
CATEGORY_RISK_PATTERNS: dict[str, list[str]] = {
    "security": [
        r"auth",
        r"password",
        r"token",
        r"secret",
        r"credential",
        r"permission",
        r"access.control",
        r"sql",
        r"query",
        r"input.*valid",
        r"sanitiz",
        r"escape",
        r"xss",
        r"csrf",
        r"inject",
        r"session",
        r"cookie",
        r"jwt",
        r"oauth",
        r"encrypt",
        r"decrypt",
        r"hash",
    ],
    "performance": [
        r"loop",
        r"async",
        r"await",
        r"cache",
        r"query",
        r"database",
        r"fetch",
        r"request",
        r"response.*time",
        r"latency",
        r"bottleneck",
        r"optimiz",
        r"memory.*leak",
        r"n\+1",
    ],
    "logic": [
        r"if.*else",
        r"condition",
        r"branch",
        r"switch",
        r"match",
        r"state.*transition",
        r"edge.*case",
        r"boundary",
        r"null.*check",
        r"undefined",
    ],
    "compliance": [
        r"schema",
        r"validation",
        r"contract",
        r"api",
        r"interface",
        r"type.*hint",
        r"annotation",
    ],
    "io_validation": [
        r"file.*path",
        r"path.*join",
        r"open\(",
        r"read.*file",
        r"write.*file",
        r"exists",
        r"mkdir",
        r"remove",
        r"delete",
        r"unlink",
    ],
    "invariants": [
        r"unique",
        r"constraint",
        r"id.*collision",
        r"duplicate",
        r"consistency",
        r"atomic",
        r"transaction",
    ],
}


@dataclass
class CategorySignal:
    """A category with detected risk signals in the code."""

    category: str
    signal_count: int
    matched_patterns: list[str]
    confidence: float  # 0-1, how confident we are this category should be checked


@dataclass
class BlindSpotFinding:
    """A finding about a category that should have been checked but wasn't."""

    category: str
    severity: str  # HIGH/MEDIUM/LOW
    title: str
    description: str
    confidence: float
    risk_signals: list[str]
    recommendation: str


@dataclass
class BlindSpotReport:
    """Report of blind spots detected."""

    findings: list[BlindSpotFinding]
    coverage_summary: dict[str, int]  # category -> count of recent checks
    last_checked: dict[str, str]  # category -> ISO timestamp
    is_meaningful: bool  # False if findings are just noise


class BlindSpotDetector:
    """

    Detects categories that haven't been checked but should be.

    Works in two directions:
    1. RECOMMEND: Before review - based on code risk patterns, suggest categories to check
    2. DETECT: After review - check if categories with risk signals weren't covered
    """

    def __init__(
        self,
        state_dir: Path | None = None,
        lookback_days: int = 14,
    ):
        """
        Args:
            state_dir: Directory with review state files
            lookback_days: How far back to look for prior reviews
        """
        self.state_dir = state_dir or Path.cwd().resolve() / ".claude" / ".artifacts" / os.environ.get("CLAUDE_TERMINAL_ID", "default") / "uci"
        self.lookback_days = lookback_days

    def scan_code_for_risk_signals(
        self, file_paths: list[str], scope: str = ""
    ) -> list[CategorySignal]:
        """
        Scan code files for risk patterns that suggest categories to check.

        Returns list of CategorySignals sorted by confidence.
        """
        signals: list[CategorySignal] = []

        for category, patterns in CATEGORY_RISK_PATTERNS.items():
            all_matches: list[str] = []
            for file_path in file_paths:
                try:
                    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                    for pattern in patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            all_matches.append(pattern)
                except (OSError, UnicodeDecodeError):
                    continue

            if all_matches:
                # Confidence based on how many patterns matched and how specific
                confidence = min(1.0, len(set(all_matches)) / 3.0)
                signals.append(
                    CategorySignal(
                        category=category,
                        signal_count=len(all_matches),
                        matched_patterns=list(set(all_matches))[:5],
                        confidence=confidence,
                    )
                )

        # Sort by confidence descending
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def get_recent_coverage(
        self,
        project_root: Path | None = None,
    ) -> tuple[dict[str, int], dict[str, str]]:
        """
        Get category coverage from recent review state files.

        Returns:
            coverage: category -> count of times checked in lookback period
            last_checked: category -> ISO timestamp of last check
        """
        coverage: dict[str, int] = defaultdict(int)
        last_checked: dict[str, str] = {}

        if project_root is None:
            project_root = Path.cwd()

        state_dir = project_root / ".claude" / ".state"
        if not state_dir.exists():
            return dict(coverage), dict(last_checked)

        cutoff = datetime.now() - timedelta(days=self.lookback_days)

        # Look for review state files
        patterns = ["adversarial-*.json", "uci-*.json", "review-*.json"]
        for pattern in patterns:
            for state_file in state_dir.glob(pattern):
                try:
                    mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
                    if mtime < cutoff:
                        continue

                    content = state_file.read_text(encoding="utf-8", errors="ignore")
                    data = json.loads(content)

                    # Extract categories from findings
                    findings = data.get("findings", [])
                    if isinstance(findings, list):
                        for finding in findings:
                            cat = finding.get("category", "unknown")
                            if cat in CATEGORIES:
                                coverage[cat] += 1
                                ts = data.get("timestamp", "")
                                if ts and (cat not in last_checked or ts > last_checked[cat]):
                                    last_checked[cat] = ts

                    # Also check for coverage array
                    cats = data.get("categories_covered", [])
                    for cat in cats:
                        if cat in CATEGORIES:
                            coverage[cat] += 1

                except (json.JSONDecodeError, OSError, KeyError):
                    continue

        return dict(coverage), dict(last_checked)

    def detect_blind_spots(
        self,
        file_paths: list[str],
        covered_categories: set[str],
        project_root: Path | None = None,
    ) -> BlindSpotReport:
        """
        Detect blind spots - categories with risk signals but no recent coverage.

        Args:
            file_paths: Code files that were reviewed
            covered_categories: Categories that were checked this session
            project_root: Project root for state files

        Returns:
            BlindSpotReport with findings (if any)
        """
        # Step 1: Get risk signals from code
        risk_signals = self.scan_code_for_risk_signals(file_paths)

        # Step 2: Get recent coverage
        recent_coverage, last_checked = self.get_recent_coverage(project_root)

        # Step 3: Build coverage summary
        all_categories = set(CATEGORIES)
        coverage_summary: dict[str, int] = {}
        for cat in all_categories:
            coverage_summary[cat] = recent_coverage.get(cat, 0)

        # Step 4: Find blind spots
        findings: list[BlindSpotFinding] = []

        for signal in risk_signals:
            cat = signal.category

            # Skip if already covered this session
            if cat in covered_categories:
                continue

            # Skip if covered recently (within lookback)
            if recent_coverage.get(cat, 0) > 0:
                continue

            # Skip low confidence
            if signal.confidence < 0.4:
                continue

            # Skip categories with no risk signals
            if signal.signal_count < 2:
                continue

            # Determine severity based on category and confidence
            if cat == "security" and signal.confidence >= 0.7:
                severity = "HIGH"
            elif signal.confidence >= 0.8:
                severity = "HIGH"
            elif signal.confidence >= 0.6:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            findings.append(
                BlindSpotFinding(
                    category=cat,
                    severity=severity,
                    title=f"{cat.title()} concerns not reviewed",
                    description=(
                        f"Code shows {signal.signal_count} risk signal(s) for {cat}, "
                        f"but {cat} wasn't checked in this review. "
                        f"Matched: {', '.join(signal.matched_patterns[:3])}"
                    ),
                    confidence=signal.confidence,
                    risk_signals=signal.matched_patterns[:5],
                    recommendation=f"Consider adding {cat} review or running /uci --include={cat}",
                )
            )

        # Sort by severity then confidence
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        findings.sort(key=lambda f: (severity_order.get(f.severity, 3), -f.confidence))

        # Only meaningful if we have HIGH/MEDIUM findings
        is_meaningful = any(f.severity in ("HIGH", "MEDIUM") for f in findings)

        return BlindSpotReport(
            findings=findings,
            coverage_summary=coverage_summary,
            last_checked=last_checked,
            is_meaningful=is_meaningful,
        )

    def render_report(self, report: BlindSpotReport) -> str:
        """
        Render a blind spot report as markdown.

        Returns empty string if not meaningful.
        """
        if not report.is_meaningful or not report.findings:
            return ""

        lines = [
            "",
            "### Blind Spot Detection",
            "",
        ]

        high = [f for f in report.findings if f.severity == "HIGH"]
        med = [f for f in report.findings if f.severity == "MEDIUM"]

        if high:
            lines.append(f"**{len(high)} high-priority categories may have been missed:**")
            for f in high:
                lines.append(f"- **{f.title}** ({f.confidence:.0%} confidence)")
                lines.append(f"  {f.description}")
                lines.append(f"  Recommendation: {f.recommendation}")
            lines.append("")

        if med:
            lines.append(f"**{len(med)} medium-priority categories may have been missed:**")
            for f in med:
                lines.append(f"- {f.title} ({f.confidence:.0%} confidence)")
            lines.append("")

        return "\n".join(lines)
