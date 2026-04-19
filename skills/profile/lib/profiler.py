"""Performance profiling for baseline and comparison measurements."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Profiler:
    """Measure and compare performance metrics."""

    def __init__(self, baseline_path: Path = Path.home() / ".claude" / "state" / "profile_baselines.json"):
        self.baseline_path = baseline_path
        self.baselines = self._load_baselines()

    def _load_baselines(self) -> dict:
        """Load existing baselines from JSON file."""
        if self.baseline_path.exists():
            try:
                return json.loads(self.baseline_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_baselines(self) -> None:
        """Save baselines to JSON file."""
        try:
            self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
            self.baseline_path.write_text(json.dumps(self.baselines, indent=2))
        except OSError:
            pass

    def measure(self, target: str | Path) -> dict:
        """Measure performance metrics for target file or directory.

        Args:
            target: File or directory path to profile

        Returns:
            Dictionary with performance metrics
        """
        target_path = Path(target)
        if not target_path.exists():
            raise FileNotFoundError(f"Target not found: {target}")

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": str(target_path),
        }

        # Measure import time for Python files
        if target_path.is_file() and target_path.suffix == ".py":
            metrics["import_time_ms"] = self._measure_import_time(target_path)
            metrics["complexity"] = self._measure_complexity(target_path)
            metrics["lines_of_code"] = self._count_lines(target_path)

        # For directories, measure all Python files
        elif target_path.is_dir():
            py_files = list(target_path.rglob("*.py"))
            if py_files:
                total_cc = 0
                total_loc = 0
                for py_file in py_files:
                    try:
                        cc = self._measure_complexity(py_file)
                        loc = self._count_lines(py_file)
                        total_cc += cc.get("average_cc", 0) * cc.get("num_functions", 0)
                        total_loc += loc
                    except Exception:
                        pass

                metrics["complexity"] = {"average_cc": total_cc / len(py_files) if py_files else 0, "num_functions": len(py_files)}
                metrics["lines_of_code"] = total_loc

        return metrics

    def _measure_import_time(self, target: Path) -> float:
        """Measure time to import Python module.

        Args:
            target: Path to Python file

        Returns:
            Import time in milliseconds
        """
        start = time.perf_counter()
        try:
            # Clear module cache to force fresh import
            module_name = target.stem
            if module_name in sys.modules:
                del sys.modules[module_name]

            # Import and measure
            __import__(str(target.parent / module_name))
        except Exception:
            pass
        end = time.perf_counter()

        return (end - start) * 1000  # Convert to milliseconds

    def _measure_complexity(self, target: Path) -> dict:
        """Measure cyclomatic complexity using radon.

        Args:
            target: Path to Python file

        Returns:
            Dictionary with complexity metrics
        """
        try:
            result = subprocess.run(
                ["radon", "cc", str(target), "-a", "-s"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Parse radon output to extract average CC
                lines = result.stdout.strip().split("\n")
                cc_values = []

                for line in lines:
                    if "CC " in line:
                        try:
                            cc = int(line.split("CC ")[1].split()[0])
                            cc_values.append(cc)
                        except (ValueError, IndexError):
                            pass

                if cc_values:
                    return {
                        "average_cc": sum(cc_values) / len(cc_values),
                        "max_cc": max(cc_values),
                        "num_functions": len(cc_values),
                    }
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        return {"average_cc": 0, "max_cc": 0, "num_functions": 0}

    def _count_lines(self, target: Path) -> int:
        """Count lines of code (excluding blanks and comments).

        Args:
            target: Path to Python file

        Returns:
            Number of lines of code
        """
        try:
            content = target.read_text()
            lines = content.split("\n")
            loc = 0

            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    loc += 1

            return loc
        except Exception:
            return 0

    def save_baseline(self, target: str | Path, metrics: dict) -> None:
        """Save performance metrics as baseline.

        Args:
            target: Target that was profiled
            metrics: Performance metrics to save
        """
        key = str(target)
        self.baselines[key] = metrics
        self._save_baselines()

    def get_baseline(self, target: str | Path) -> dict | None:
        """Get saved baseline for target.

        Args:
            target: Target to get baseline for

        Returns:
            Baseline metrics or None if not found
        """
        return self.baselines.get(str(target))

    def compare(self, target: str | Path, current_metrics: dict) -> dict:
        """Compare current metrics against baseline.

        Args:
            target: Target being profiled
            current_metrics: Current performance metrics

        Returns:
            Comparison results with deltas
        """
        baseline = self.get_baseline(target)
        if not baseline:
            return {"error": "No baseline found for target", "fallback": "Run --baseline first"}

        comparison = {
            "target": str(target),
            "baseline_timestamp": baseline.get("timestamp"),
            "current_timestamp": current_metrics.get("timestamp"),
        }

        # Compare import time
        if "import_time_ms" in baseline and "import_time_ms" in current_metrics:
            baseline_time = baseline["import_time_ms"]
            current_time = current_metrics["import_time_ms"]
            delta = current_time - baseline_time
            pct_change = (delta / baseline_time) * 100 if baseline_time > 0 else 0

            comparison["import_time_ms"] = {
                "baseline": baseline_time,
                "current": current_time,
                "delta_ms": delta,
                "pct_change": pct_change,
                "improved": delta < 0,
            }

        # Compare complexity
        if "complexity" in baseline and "complexity" in current_metrics:
            baseline_cc = baseline["complexity"].get("average_cc", 0)
            current_cc = current_metrics["complexity"].get("average_cc", 0)
            delta = current_cc - baseline_cc
            pct_change = (delta / baseline_cc) * 100 if baseline_cc > 0 else 0

            comparison["complexity"] = {
                "baseline": baseline_cc,
                "current": current_cc,
                "delta": delta,
                "pct_change": pct_change,
                "improved": delta < 0,
            }

        # Compare LOC
        if "lines_of_code" in baseline and "lines_of_code" in current_metrics:
            baseline_loc = baseline["lines_of_code"]
            current_loc = current_metrics["lines_of_code"]
            delta = current_loc - baseline_loc
            pct_change = (delta / baseline_loc) * 100 if baseline_loc > 0 else 0

            comparison["lines_of_code"] = {
                "baseline": baseline_loc,
                "current": current_loc,
                "delta": delta,
                "pct_change": pct_change,
                "improved": delta < 0,  # LOC reduction is improvement
            }

        return comparison
