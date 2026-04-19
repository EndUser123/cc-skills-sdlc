#!/usr/bin/env python3
"""Test execution profiling."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class TestProfiler:
    """Profile test execution times."""

    def __init__(self, profile_path: Path = Path(".test_profiles.json")):
        self.profile_path = profile_path
        self.profiles: dict[str, list[dict]] = self._load_profiles()

    def _load_profiles(self) -> dict[str, list[dict]]:
        """Load test profiles."""
        if self.profile_path.exists():
            try:
                return json.loads(self.profile_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_profiles(self) -> None:
        """Save profiles to disk."""
        try:
            self.profile_path.write_text(json.dumps(self.profiles, indent=2))
        except Exception:
            pass

    def record_test_time(self, test_name: str, runtime_seconds: float) -> None:
        """Record test execution time."""
        if test_name not in self.profiles:
            self.profiles[test_name] = []

        self.profiles[test_name].append(
            {"timestamp": datetime.now().isoformat(), "runtime_seconds": runtime_seconds}
        )

        # Keep only last 10 runs
        if len(self.profiles[test_name]) > 10:
            self.profiles[test_name] = self.profiles[test_name][-10:]

        self._save_profiles()

    def get_slow_tests(self, threshold_seconds: float = 5.0) -> list[dict[str, Any]]:
        """Get tests slower than threshold."""
        slow_tests = []

        for test_name, runs in self.profiles.items():
            if not runs:
                continue

            avg_time = sum(r["runtime_seconds"] for r in runs) / len(runs)

            if avg_time >= threshold_seconds:
                slow_tests.append(
                    {
                        "test_name": test_name,
                        "avg_runtime_seconds": avg_time,
                        "runs": len(runs),
                        "last_runtime": runs[-1]["runtime_seconds"],
                    }
                )

        # Sort by average runtime (slowest first)
        slow_tests.sort(key=lambda x: x["avg_runtime_seconds"], reverse=True)

        return slow_tests

    def get_recommendations(self) -> list[str]:
        """Get optimization recommendations for slow tests."""
        recommendations = []
        slow_tests = self.get_slow_tests(threshold_seconds=5.0)

        for test in slow_tests:
            test_name = test["test_name"]
            avg_time = test["avg_runtime_seconds"]

            if "integration" in test_name.lower() or "e2e" in test_name.lower():
                recommendations.append(
                    f"**{test_name}** ({avg_time:.1f}s) - Consider splitting into smaller tests"
                )
            elif "database" in test_name.lower() or "migration" in test_name.lower():
                recommendations.append(
                    f"**{test_name}** ({avg_time:.1f}s) - Could use database fixtures or mocks"
                )
            else:
                recommendations.append(
                    f"**{test_name}** ({avg_time:.1f}s) - Mark with @pytest.mark.slow"
                )

        return recommendations
