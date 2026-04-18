"""
Data collector for analyzing historical /uci runs.

This module provides infrastructure for:
1. Loading /uci run data from log files
2. Categorizing findings by bug type
3. Detecting missed bugs (bugs present but not found by /uci)
4. Validating finding data structure schemas
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BugCategory(Enum):
    """Categories of bugs that /uci may or may not detect."""

    STATE_TRANSITION = "state-transition"
    TOCTOU = "toctou"
    ID_COLLISION = "id-collision"
    PATH_VALIDATION = "path-validation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    LOGIC = "logic"
    TESTING = "testing"

    @classmethod
    def classify(cls, finding: dict[str, Any]) -> Optional["BugCategory"]:
        """
        Classify a finding into a bug category based on its content.

        Args:
            finding: Finding dictionary with problem, location, etc.

        Returns:
            BugCategory enum value or None if classification fails
        """
        problem = finding.get("problem", "").lower()
        location = finding.get("location", "")

        # State-transition patterns
        if any(
            keyword in problem
            for keyword in [
                "state transition",
                "state machine",
                "invalid state",
                "illegal state",
                "state not validated",
            ]
        ):
            return cls.STATE_TRANSITION

        # TOCTOU patterns
        if any(
            keyword in problem
            for keyword in [
                "toctou",
                "time-of-check time-of-use",
                "check-then-act",
                "race condition",
                "evidence freshness",
            ]
        ):
            return cls.TOCTOU

        # ID collision patterns
        if any(
            keyword in problem
            for keyword in [
                "id collision",
                "duplicate id",
                "id conflict",
                "concurrent request",
                "race condition",
            ]
        ):
            return cls.ID_COLLISION

        # Path validation patterns
        if any(
            keyword in problem
            for keyword in [
                "path existence",
                "file not found",
                "path validation",
                "missing path check",
                "transcript path",
            ]
        ):
            return cls.PATH_VALIDATION

        # Performance patterns
        if any(
            keyword in problem for keyword in ["n+1", "bottleneck", "slow query", "performance"]
        ):
            return cls.PERFORMANCE

        # Security patterns
        if any(
            keyword in problem
            for keyword in ["injection", "xss", "csrf", "data leak", "access control"]
        ):
            return cls.SECURITY

        return cls.LOGIC  # Default fallback


@dataclass
class UCIFinding:
    """A single bug finding from a /uci run."""

    id: str
    severity: str  # blocker, high, medium, low
    location: str  # file:line or section reference
    problem: str
    category: str | None = None
    adversarial_scenario: str | None = None
    impact: str | None = None
    recommendation: str | None = None


@dataclass
class UCIRun:
    """A single /uci execution with its findings."""

    timestamp: str
    mode: str  # triage, standard, deep, comprehensive
    agents: list[str]
    findings: list[UCIFinding]
    raw_data: dict[str, Any] = field(default_factory=dict)


class UCIRunCollector:
    """
    Collects and analyzes /uci run data from log files.

    Responsibilities:
    - Load /uci run data from JSON log files
    - Extract findings by category
    - Detect missed bugs (present but not found)
    - Validate finding schemas
    """

    def __init__(self, log_dir: str = ".claude/state/uci"):
        self.log_dir = Path(log_dir)
        self.runs: list[UCIRun] = []

    def load_from_logs(self) -> list[dict[str, Any]]:
        """
        Load all /uci runs from log directory.

        Returns:
            List of run dictionaries with timestamp, mode, agents, findings
        """
        runs = []

        if not self.log_dir.exists():
            logger.warning(f"Log directory does not exist: {self.log_dir}")
            return runs

        for log_file in self.log_dir.glob("uci_run_*.json"):
            try:
                with open(log_file) as f:
                    run_data = json.load(f)
                    runs.append(run_data)
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load {log_file}: {e}")

        self.runs = runs
        return runs

    def extract_findings_by_category(self, run: dict[str, Any]) -> dict[str, list[dict]]:
        """
        Extract findings from a run grouped by category.

        Args:
            run: Run dictionary with findings list

        Returns:
            Dictionary mapping category to list of findings
        """
        categories: dict[str, list[dict]] = {}

        for finding_data in run.get("findings", []):
            # Determine category
            category = None
            if "category" in finding_data:
                category = finding_data["category"]
            else:
                category_enum = BugCategory.classify(finding_data)
                category = category_enum.value if category_enum else "uncategorized"

            if category not in categories:
                categories[category] = []
            categories[category].append(finding_data)

        return categories

    def detect_missed_bugs(
        self, uci_run: dict[str, Any], code_analysis: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Detect bugs that were present but not found by /uci.

        Args:
            uci_run: The /uci run data with findings that WERE found
            code_analysis: Analysis of what bugs were actually present

        Returns:
            List of missed bug findings with metadata
        """
        missed = []

        # Get categories of bugs that /uci actually found
        found_categories = set()
        for finding in uci_run.get("findings", []):
            category = finding.get("category")
            if not category:
                category_enum = BugCategory.classify(finding)
                category = category_enum.value if category_enum else None
            if category:
                found_categories.add(category)

        # Check what bugs were present but not in found set
        for bug_data in code_analysis.get("state_bugs_present", []):
            # This is simplified - real implementation would need
            # more sophisticated analysis
            missed.append(
                {
                    "category": "state-transition",
                    "location": bug_data.get("location"),
                    "problem": bug_data.get("problem"),
                    "status": "missed",
                }
            )

        return missed


def validate_finding_schema(finding: dict[str, Any]) -> bool:
    """
    Validate that a finding has all required fields.

    Required fields: id, severity, location, problem

    Args:
        finding: Finding dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["id", "severity", "location", "problem"]

    for field in required_fields:
        if field not in finding:
            return False

    # Validate severity values
    valid_severities = ["blocker", "high", "medium", "low"]
    if finding.get("severity") not in valid_severities:
        return False

    return True


def calculate_missed_bug_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate metrics on missed bugs across all runs.

    Args:
        runs: List of /uci run dictionaries

    Returns:
        Dictionary with metrics:
        - total_runs: Total number of runs analyzed
        - runs_with_missed_bugs: Number of runs with missed bugs
        - missed_by_category: Count of missed bugs by category
        - missed_percentage: Percentage of runs with missed bugs
    """
    total_runs = len(runs)
    runs_with_missed = 0
    missed_by_category: dict[str, int] = {}

    for run in runs:
        # This is a placeholder - real implementation would
        # analyze actual missed bug data
        if run.get("missed_bugs"):
            runs_with_missed += 1

    return {
        "total_runs": total_runs,
        "runs_with_missed_bugs": runs_with_missed,
        "missed_by_category": missed_by_category,
        "missed_percentage": (runs_with_missed / total_runs * 100) if total_runs > 0 else 0,
    }
