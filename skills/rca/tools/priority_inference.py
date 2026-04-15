#!/usr/bin/env python3
"""
Priority inference system for rca automatic triage.

Calculates priority scores (0-100) for files/contexts based on:
1. Error Frequency Clustering (40% weight)
2. Recent Change Detection (30% weight)
3. Static Complexity Metrics (20% weight)
4. Test Coverage Gaps (10% weight)

Uses existing hook state database as data source - no manual files required.
"""

import ast
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Priority weights (must sum to 1.0)
WEIGHT_ERROR_FREQUENCY = 0.40
WEIGHT_RECENT_CHANGE = 0.30
WEIGHT_COMPLEXITY = 0.20
WEIGHT_TEST_COVERAGE = 0.10

# Default priority when no signals available
DEFAULT_PRIORITY = 50

# Maximum file size for complexity analysis (lines)
MAX_COMPLEXITY_LINES = 5000


@dataclass
class PriorityFactors:
    """Breakdown of priority scores by factor."""

    error_frequency: float
    recent_change: float
    complexity: float
    test_coverage: float
    total: int


class PriorityInference:
    """
    Calculate priority scores for files/contexts based on execution patterns.

    Uses hook state database (rca_workflow.json, actions_*.json) as data source.
    """

    # Class-level weights for testing access
    WEIGHT_ERROR_FREQUENCY = WEIGHT_ERROR_FREQUENCY
    WEIGHT_RECENT_CHANGE = WEIGHT_RECENT_CHANGE
    WEIGHT_COMPLEXITY = WEIGHT_COMPLEXITY
    WEIGHT_TEST_COVERAGE = WEIGHT_TEST_COVERAGE

    def __init__(self, state_dir: str | None = None) -> None:
        """
        Initialize priority inference.

        Args:
            state_dir: Path to state directory (default: ~/.claude/state/rca)
        """
        self.state_dir = Path(state_dir or self._get_default_state_dir())
        self.state_file = self.state_dir / "rca_workflow.json"

    @staticmethod
    def _get_default_state_dir() -> Path:
        """Get default state directory path."""
        claude_home = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
        return claude_home / "state" / "rca"

    def calculate_priority_score(self, file_path: str) -> int:
        """
        Calculate overall priority score (0-100) for a file.

        Args:
            file_path: Path to file to score

        Returns:
            Priority score from 0 (low) to 100 (high)
        """
        try:
            # Get individual factor scores
            error_freq = self._get_error_frequency_score(file_path)
            recent_change = self._get_recent_change_score(file_path)
            complexity = self._get_complexity_score(file_path)
            test_coverage = self._get_test_coverage_score(file_path)

            # Calculate weighted total
            total = (
                error_freq * WEIGHT_ERROR_FREQUENCY
                + recent_change * WEIGHT_RECENT_CHANGE
                + complexity * WEIGHT_COMPLEXITY
                + test_coverage * WEIGHT_TEST_COVERAGE
            )

            # If all signals are zero, return default priority
            if total == 0:
                logger.debug(f"No signals found for {file_path}, returning default priority")
                return DEFAULT_PRIORITY

            # Clamp to 0-100 range
            total_clamped = max(0, min(100, int(total)))

            logger.info(
                f"Priority score for {file_path}: {total_clamped} "
                f"(error_freq={error_freq:.1f}, recent_change={recent_change:.1f}, "
                f"complexity={complexity:.1f}, test_coverage={test_coverage:.1f})"
            )

            return total_clamped

        except Exception as e:
            logger.warning(f"Error calculating priority for {file_path}: {e}, returning default")
            return DEFAULT_PRIORITY

    def get_priority_factors(self, file_path: str) -> PriorityFactors:
        """
        Get detailed breakdown of priority scores by factor.

        Args:
            file_path: Path to file to score

        Returns:
            PriorityFactors with individual scores and total
        """
        error_freq = self._get_error_frequency_score(file_path)
        recent_change = self._get_recent_change_score(file_path)
        complexity = self._get_complexity_score(file_path)
        test_coverage = self._get_test_coverage_score(file_path)

        total = (
            error_freq * WEIGHT_ERROR_FREQUENCY
            + recent_change * WEIGHT_RECENT_CHANGE
            + complexity * WEIGHT_COMPLEXITY
            + test_coverage * WEIGHT_TEST_COVERAGE
        )

        # If all signals are zero, return default priority
        if total == 0:
            total_clamped = DEFAULT_PRIORITY
        else:
            total_clamped = max(0, min(100, int(total)))

        return PriorityFactors(
            error_frequency=error_freq,
            recent_change=recent_change,
            complexity=complexity,
            test_coverage=test_coverage,
            total=total_clamped,
        )

    def _get_error_frequency_score(self, file_path: str) -> float:
        """
        Calculate error frequency score (0-100) from hook state database.

        Higher score = more errors in this file.
        Applies exponential decay for old errors.
        """
        try:
            if not self.state_file.exists():
                logger.debug(f"State file not found: {self.state_file}")
                return 0.0

            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            actions = data.get("actions", [])

            if not actions:
                return 0.0

            # Count errors for this file with exponential decay
            now = datetime.now()
            weighted_error_count = 0.0

            for action in actions:
                # Check if action involves this file
                action_file = action.get("file", "")
                if file_path not in action_file and action_file not in file_path:
                    continue

                # Check if action had error
                if not action.get("error", False):
                    continue

                # Calculate decay factor based on age
                timestamp_str = action.get("timestamp", "")
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    age_hours = (now - timestamp).total_seconds() / 3600

                    # Exponential decay: 1.0 at 0 hours, 0.5 at 24 hours, 0.25 at 48 hours
                    decay_factor = 2.0 ** (-age_hours / 24)
                    weighted_error_count += decay_factor

                except (ValueError, TypeError):
                    # Invalid timestamp, skip
                    continue

            # Normalize to 0-100 scale (1 recent error = 60 points)
            score = min(100, weighted_error_count * 60)
            return score

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Error reading state file {self.state_file}: {e}")
            return 0.0

    def _get_recent_change_score(self, file_path: str) -> float:
        """
        Calculate recent change score (0-100) from git history.

        Higher score = more recently changed.
        """
        try:
            # Get last modification time from git
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ci", "--", file_path],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode != 0 or not result.stdout.strip():
                logger.debug(f"No git history for {file_path}")
                return 0.0

            # Parse git timestamp
            timestamp_str = result.stdout.strip().split()[
                0
            ]  # "2026-03-14" from "2026-03-14 10:30:00 +0000"
            try:
                last_change = datetime.fromisoformat(timestamp_str)
            except ValueError:
                logger.debug(f"Invalid git timestamp: {timestamp_str}")
                return 0.0

            # Calculate age in days
            age_days = (datetime.now() - last_change).days

            # Score: 100 for today, decays to 0 at 30+ days
            # Formula: max(0, 100 - (age_days * 100 / 30))
            score = max(0, 100 - (age_days * 100 / 30))
            return score

        except subprocess.TimeoutExpired:
            logger.warning(f"Git log timeout for {file_path}")
            return 0.0
        except FileNotFoundError:
            logger.debug(f"Git not found or file not in repository: {file_path}")
            return 0.0
        except Exception as e:
            logger.warning(f"Error getting git history for {file_path}: {e}")
            return 0.0

    def _get_complexity_score(self, str_path: str) -> float:
        """
        Calculate static complexity score (0-100) via AST analysis.

        Higher score = more complex code.
        Skips files > MAX_COMPLEXITY_LINES.
        Returns 0 for non-Python files.
        """
        try:
            path = Path(str_path)

            # Skip non-Python files
            if not str(path).endswith(".py"):
                return 0.0

            # Skip if file too large
            if not path.exists():
                return 0.0

            line_count = 0
            with open(path, encoding="utf-8") as f:
                for _line in f:
                    line_count += 1
                    if line_count > MAX_COMPLEXITY_LINES:
                        logger.debug(f"Skipping complexity analysis for large file: {path}")
                        return 0.0

            # Parse AST
            with open(path, encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=str(path))
                except SyntaxError:
                    logger.debug(f"Syntax error in {path}, skipping complexity analysis")
                    return 0.0

            # Calculate complexity metrics
            complexity_analyzer: ComplexityAnalyzer = ComplexityAnalyzer()
            complexity_analyzer.visit(tree)

            # Normalize to 0-100 scale
            # High cyclomatic complexity (>10) + high nesting (>4) = high score
            cyclomatic_score = min(100, complexity_analyzer.max_cyclomatic * 10)
            nesting_score = min(100, complexity_analyzer.max_nesting * 20)
            length_score = min(100, complexity_analyzer.max_function_length / 5)

            score = (cyclomatic_score + nesting_score + length_score) / 3
            return score

        except OSError as e:
            logger.warning(f"Error reading file {str_path} for complexity analysis: {e}")
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating complexity for {str_path}: {e}")
            return 0.0

    def _get_test_coverage_score(self, file_path: str) -> float:
        """
        Calculate test coverage gap score (0-100).

        Higher score = lower test coverage (higher priority).
        Returns 0 if coverage file not found (graceful degradation).
        """
        try:
            # Look for .coverage file in project root
            coverage_file = Path(".coverage")
            if not coverage_file.exists():
                logger.debug("Coverage file not found")
                return 0.0

            # Parse coverage file (simplified - would use coverage API in production)
            # For now, return 0 (advisory only, not blocking)
            return 0.0

        except Exception as e:
            logger.warning(f"Error checking test coverage: {e}")
            return 0.0


class ComplexityAnalyzer(ast.NodeVisitor):
    """AST visitor to calculate code complexity metrics."""

    def __init__(self) -> None:
        self.max_cyclomatic = 1  # Base complexity
        self.max_nesting = 0
        self.max_function_length = 0
        self._current_nesting = 0
        self._function_start_line = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_start_line = node.lineno
        self._current_nesting = 0

        # Calculate cyclomatic complexity (decision points + 1)
        cyclomatic = 1  # Base complexity
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.Try)):
                cyclomatic += 1

        self.max_cyclomatic = max(self.max_cyclomatic, cyclomatic)

        # Visit function body
        self.generic_visit(node)

        # Calculate function length
        function_length = node.end_lineno - node.lineno if node.end_lineno else 0
        self.max_function_length = max(self.max_function_length, function_length)

    def visit_If(self, node: ast.If) -> None:
        self._current_nesting += 1
        self.max_nesting = max(self.max_nesting, self._current_nesting)
        self.generic_visit(node)
        self._current_nesting -= 1

    def visit_For(self, node: ast.For) -> None:
        self._current_nesting += 1
        self.max_nesting = max(self.max_nesting, self._current_nesting)
        self.generic_visit(node)
        self._current_nesting -= 1

    def visit_While(self, node: ast.While) -> None:
        self._current_nesting += 1
        self.max_nesting = max(self.max_nesting, self._current_nesting)
        self.generic_visit(node)
        self._current_nesting -= 1

    def visit_Try(self, node: ast.Try) -> None:
        self._current_nesting += 1
        self.max_nesting = max(self.max_nesting, self._current_nesting)
        self.generic_visit(node)
        self._current_nesting -= 1


def calculate_priority_score(file_path: str, state_dir: str | None = None) -> int:
    """
    Convenience function to calculate priority score for a single file.

    Args:
        file_path: Path to file to score
        state_dir: Optional state directory path

    Returns:
        Priority score from 0 (low) to 100 (high)
    """
    inference = PriorityInference(state_dir=state_dir)
    return inference.calculate_priority_score(file_path)


def rank_contexts(contexts: list[str], state_dir: str | None = None) -> list[tuple[str, int]]:
    """
    Rank multiple contexts by priority score.

    Args:
        contexts: List of file paths to rank
        state_dir: Optional state directory path

    Returns:
        List of (context, score) tuples sorted by score descending
    """
    inference = PriorityInference(state_dir=state_dir)

    scored_contexts = [(ctx, inference.calculate_priority_score(ctx)) for ctx in contexts]

    # Sort by score descending
    scored_contexts.sort(key=lambda x: x[1], reverse=True)
    return scored_contexts


def main() -> None:
    """CLI entry point for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python priority_inference.py <file_path> [file_path...]")
        sys.exit(1)

    inference = PriorityInference()

    for file_path in sys.argv[1:]:
        factors = inference.get_priority_factors(file_path)

        print(f"\n{file_path}:")
        print(f"  Priority Score: {factors.total}/100")
        print(f"  Error Frequency: {factors.error_frequency:.1f}/100")
        print(f"  Recent Change: {factors.recent_change:.1f}/100")
        print(f"  Complexity: {factors.complexity:.1f}/100")
        print(f"  Test Coverage: {factors.test_coverage:.1f}/100")


if __name__ == "__main__":
    main()
