#!/usr/bin/env python3
"""Flaky test detection using pass rate analysis."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class FlakyTestDetector:
    """Detect flaky tests that fail intermittently."""

    def __init__(self, history_path: Path = Path(".test_history.json")):
        self.history_path = history_path
        self.history: dict[str, list[dict]] = self._load_history()

    def _load_history(self) -> dict[str, list[dict]]:
        """Load test run history."""
        if self.history_path.exists():
            try:
                return json.loads(self.history_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_history(self) -> None:
        """Save history to disk."""
        try:
            self.history_path.write_text(json.dumps(self.history, indent=2))
        except Exception:
            pass

    def record_run(
        self,
        test_name: str,
        passed: bool,
        error_message: str = "",
        runtime_seconds: float = 0,
    ) -> None:
        """Record a test run result."""
        if test_name not in self.history:
            self.history[test_name] = []

        self.history[test_name].append(
            {
                "timestamp": datetime.now().isoformat(),
                "passed": passed,
                "error_message": error_message,
                "runtime_seconds": runtime_seconds,
            }
        )

        # Keep only last 20 runs per test
        if len(self.history[test_name]) > 20:
            self.history[test_name] = self.history[test_name][-20:]

        self._save_history()

    def analyze_flakiness(
        self, test_name: str, min_runs: int = 5
    ) -> dict[str, Any]:
        """
        Analyze a test for flakiness.

        Returns:
            Dictionary with is_flaky, pass_rate, recent_runs, different_errors
        """
        if test_name not in self.history:
            return {"is_flaky": False, "pass_rate": 1.0, "recent_runs": 0, "different_errors": []}

        runs = self.history[test_name]

        if len(runs) < min_runs:
            return {
                "is_flaky": False,
                "pass_rate": 1.0,
                "recent_runs": len(runs),
                "different_errors": [],
            }

        # Calculate pass rate
        passed = sum(1 for r in runs if r["passed"])
        pass_rate = passed / len(runs)

        # Collect different error messages
        error_messages = set(r.get("error_message", "") for r in runs if not r["passed"])
        error_messages.discard("")

        # Flaky if: pass rate between 30-70% AND multiple different errors
        is_flaky = 0.3 < pass_rate < 0.7 and len(error_messages) >= 2

        return {
            "is_flaky": is_flaky,
            "pass_rate": pass_rate,
            "recent_runs": len(runs),
            "different_errors": sorted(list(error_messages)),
        }

    def get_all_flaky_tests(self) -> list[dict[str, Any]]:
        """Get all flaky tests across entire test suite."""
        flaky = []

        for test_name in self.history:
            analysis = self.analyze_flakiness(test_name)
            if analysis["is_flaky"]:
                flaky.append({"test_name": test_name, **analysis})

        # Sort by pass rate (most flaky first)
        flaky.sort(key=lambda x: x["pass_rate"])

        return flaky
