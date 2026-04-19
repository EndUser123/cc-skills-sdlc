#!/usr/bin/env python3
"""Coverage trend analysis with rolling window."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class CoverageTrendTracker:
    """Track coverage changes over time."""

    def __init__(self, trends_path: Path = Path(".coverage_trends.json")):
        self.trends_path = trends_path
        self.trends: dict[str, list[dict]] = self._load_trends()

    def _load_trends(self) -> dict[str, list[dict]]:
        """Load coverage trends."""
        if self.trends_path.exists():
            try:
                return json.loads(self.trends_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_trends(self) -> None:
        """Save trends to disk."""
        try:
            self.trends_path.write_text(json.dumps(self.trends, indent=2))
        except Exception:
            pass

    def record_coverage(
        self, module: str, coverage_percent: float, lines_covered: int, lines_total: int
    ) -> None:
        """Record coverage measurement for a module."""
        if module not in self.trends:
            self.trends[module] = []

        self.trends[module].append(
            {
                "timestamp": datetime.now().isoformat(),
                "coverage_percent": coverage_percent,
                "lines_covered": lines_covered,
                "lines_total": lines_total,
            }
        )

        # Keep only last 30 days
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        self.trends[module] = [e for e in self.trends[module] if e["timestamp"] > cutoff]

        self._save_trends()

    def analyze_trend(self, module: str, days: int = 7) -> dict[str, Any]:
        """
        Analyze coverage trend for a module.

        Returns:
            Dictionary with current_percent, change_percent, trend, measurements
        """
        if module not in self.trends:
            return {"current_percent": 0, "change_percent": 0, "trend": "unknown", "measurements": 0}

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [e for e in self.trends[module] if e["timestamp"] > cutoff]

        if len(recent) < 2:
            return {
                "current_percent": 0,
                "change_percent": 0,
                "trend": "insufficient_data",
                "measurements": len(recent),
            }

        current = recent[-1]["coverage_percent"]
        oldest = recent[0]["coverage_percent"]
        change = current - oldest

        # Determine trend
        if change > 2:
            trend = "improving"
        elif change < -2:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "current_percent": current,
            "change_percent": change,
            "trend": trend,
            "measurements": len(recent),
        }

    def get_degrading_modules(self, threshold: float = -2.0) -> list[dict[str, Any]]:
        """Get modules with degrading coverage."""
        degrading = []

        for module in self.trends:
            analysis = self.analyze_trend(module)
            if analysis["trend"] == "degrading" and analysis["change_percent"] <= threshold:
                degrading.append({"module": module, **analysis})

        # Sort by change percent (worst first)
        degrading.sort(key=lambda x: x["change_percent"])

        return degrading
