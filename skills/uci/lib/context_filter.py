"""
Context-Aware Filtering for Unified Code Inspection

Filters findings against solo-dev context constraints to remove
enterprise-style patterns that don't apply to solo development.

Inspired by /r (Remember/Refine) context-aware filtering patterns.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of filtering a list of findings."""
    original_count: int
    filtered_count: int
    removed_count: int
    removed_categories: Dict[str, int] = field(default_factory=dict)
    filter_reasons: List[str] = field(default_factory=list)


class SoloDevContextFilter:
    """
    Filters code review findings against solo-dev context constraints.

    Removes enterprise-style findings such as:
    - Team coordination requirements
    - Multi-person code review patterns
    - Enterprise deployment patterns
    - Organizational policy violations
    """

    # Default solo-dev forbidden patterns
    DEFAULT_FORBIDDEN = [
        "team coordination",
        "team approval",
        "stakeholder consensus",
        "multi-person sign-off",
        "architectural review board",
        "management approval",
        "code review meeting",
        "pair programming",
        "mob programming",
        "group consensus",
    ]

    # Solo-dev appropriate patterns (should NOT be filtered)
    SOLO_DEV_SAFE = [
        "test coverage",
        "documentation",
        "type safety",
        "error handling",
        "security",
        "performance",
        "accessibility",
        "code quality",
        "refactoring",
        "modularity",
    ]

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the context filter.

        Args:
            config_path: Path to solo-dev-context.yaml config file
        """
        self.config_path = config_path or Path(".claude/config/solo-dev-context.yaml")
        self.forbidden_patterns = self.DEFAULT_FORBIDDEN.copy()
        self.safe_patterns = self.SOLO_DEV_SAFE.copy()

        # Load custom config if exists
        if self.config_path.exists():
            self._load_config()

    def _load_config(self) -> None:
        """Load solo-dev context configuration from YAML file."""
        try:
            import yaml

            with open(self.config_path) as f:
                config = yaml.safe_load(f)

            # Load custom forbidden patterns
            custom_forbidden = config.get("constraints", {}).get("forbidden", [])
            if custom_forbidden:
                self.forbidden_patterns.extend(custom_forbidden)

            # Load custom safe patterns
            custom_safe = config.get("safe_patterns", [])
            if custom_safe:
                self.safe_patterns.extend(custom_safe)

            logger.info(f"Loaded context filter from {self.config_path}")

        except Exception as e:
            logger.warning(f"Failed to load context config: {e}. Using defaults.")

    def filter_findings(
        self,
        findings: List[Dict[str, Any]]
    ) -> FilterResult:
        """
        Filter findings against solo-dev context constraints.

        Args:
            findings: List of finding dicts to filter

        Returns:
            FilterResult with filtered findings and statistics
        """
        original_count = len(findings)
        filtered = []
        removed = 0
        removed_categories = {}
        filter_reasons = []

        for finding in findings:
            # Get text to check
            text_to_check = self._get_finding_text(finding)

            # Check if finding matches any forbidden pattern
            is_forbidden = False
            reason = None

            for pattern in self.forbidden_patterns:
                if pattern.lower() in text_to_check:
                    # But check if it's a safe pattern override
                    is_safe_override = any(
                        safe in text_to_check
                        for safe in self.safe_patterns
                    )

                    if not is_safe_override:
                        is_forbidden = True
                        reason = f"Contains forbidden pattern: '{pattern}'"

                        # Track category
                        category = finding.get("category", "unknown")
                        removed_categories[category] = removed_categories.get(category, 0) + 1
                        break

            if is_forbidden:
                removed += 1
                if reason:
                    filter_reasons.append(f"{finding.get('id', 'unknown')}: {reason}")
            else:
                filtered.append(finding)

        return FilterResult(
            original_count=original_count,
            filtered_count=len(filtered),
            removed_count=removed,
            removed_categories=removed_categories,
            filter_reasons=filter_reasons,
        )

    def _get_finding_text(self, finding: Dict[str, Any]) -> str:
        """Get searchable text from a finding."""
        fields = [
            finding.get("problem", ""),
            finding.get("description", ""),
            finding.get("recommendation", ""),
            finding.get("impact", ""),
        ]

        combined = " ".join(str(f).lower() for f in fields if f)
        return combined

    def is_solo_dev_safe(self, finding: Dict[str, Any]) -> bool:
        """
        Check if a finding is safe for solo-dev context.

        Args:
            finding: Finding dict to check

        Returns:
            True if finding doesn't contain forbidden patterns
        """
        text = self._get_finding_text(finding)

        for pattern in self.forbidden_patterns:
            if pattern.lower() in text:
                # Check for safe override
                is_safe = any(safe in text for safe in self.safe_patterns)
                if not is_safe:
                    return False

        return True


class PathScopeFilter:
    """
    Filters file paths to exclude virtual environment and dependency directories.

    Inspired by /cco path scoping patterns.
    """

    # Default paths to exclude from search/analysis
    DEFAULT_EXCLUDE_PATTERNS = [
        r"venv/.*",
        r"env/.*",
        r"\.venv/.*",
        r"virtualenv/.+",
        r"node_modules/.*",
        r"\.npm/.*",
        r"__pycache__/.*",
        r"\.pytest_cache/.*",
        r"\.mypy_cache/.*",
        r"\.tox/.*",
        r"\.eggs/.*",
        r"build/.*",
        r"dist/.*",
        r"\.git/.*",
        r"\.svn/.*",
        r"\.hg/.*",
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize the path scope filter.

        Args:
            custom_patterns: Additional regex patterns to exclude
        """
        self.exclude_patterns = self.DEFAULT_EXCLUDE_PATTERNS.copy()

        if custom_patterns:
            self.exclude_patterns.extend(custom_patterns)

        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern) for pattern in self.exclude_patterns
        ]

    def should_exclude_path(self, file_path: str) -> bool:
        """
        Check if a file path should be excluded from analysis.

        Args:
            file_path: File path to check

        Returns:
            True if path should be excluded
        """
        normalized_path = file_path.replace("\\", "/")

        for pattern in self.compiled_patterns:
            if pattern.search(normalized_path):
                return True

        return False

    def filter_paths(
        self,
        file_list: List[str],
        max_files: int = 100
    ) -> List[str]:
        """
        Filter file list to exclude unwanted paths.

        Args:
            file_list: List of file paths to filter
            max_files: Maximum number of files to return (prevent bloat)

        Returns:
            Filtered list of file paths
        """
        filtered = [
            f for f in file_list
            if not self.should_exclude_path(f)
        ]

        # Limit file count
        if len(filtered) > max_files:
            logger.warning(
                f"File list truncated from {len(filtered)} to {max_files} "
                f"to prevent excessive processing"
            )
            filtered = filtered[:max_files]

        return filtered

    def get_excluded_count(self, file_list: List[str]) -> Dict[str, int]:
        """
        Get statistics about excluded paths by category.

        Args:
            file_list: List of file paths to analyze

        Returns:
            Dict with excluded counts by category
        """
        excluded = {
            "venv": 0,
            "node_modules": 0,
            "cache": 0,
            "build": 0,
            "vcs": 0,
            "other": 0,
        }

        for file_path in file_list:
            normalized_path = file_path.replace("\\", "/")

            if any(p in normalized_path for p in ["venv", "env", ".venv", "virtualenv"]):
                excluded["venv"] += 1
            elif "node_modules" in normalized_path:
                excluded["node_modules"] += 1
            elif any(p in normalized_path for p in ["__pycache__", "pytest_cache", "mypy_cache", ".tox"]):
                excluded["cache"] += 1
            elif any(p in normalized_path for p in ["build", "dist", ".eggs"]):
                excluded["build"] += 1
            elif any(p in normalized_path for p in [".git", ".svn", ".hg"]):
                excluded["vcs"] += 1
            else:
                # Check if excluded by custom pattern
                if self.should_exclude_path(file_path):
                    excluded["other"] += 1

        return excluded


def apply_context_filters(
    findings: List[Dict[str, Any]],
    file_list: Optional[List[str]] = None,
    config_path: Optional[Path] = None,
) -> tuple[List[Dict[str, Any]], FilterResult, Optional[Dict[str, int]]]:
    """
    Apply all context filters to findings and file list.

    Args:
        findings: List of finding dicts to filter
        file_list: Optional list of file paths to filter
        config_path: Optional path to solo-dev context config

    Returns:
        Tuple of (filtered findings, filter result, excluded path stats)
    """
    # Apply solo-dev context filter
    context_filter = SoloDevContextFilter(config_path)
    filter_result = context_filter.filter_findings(findings)

    # Apply path scoping if file list provided
    excluded_stats = None
    if file_list:
        path_filter = PathScopeFilter()
        file_list = path_filter.filter_paths(file_list)
        excluded_stats = path_filter.get_excluded_count(file_list)

    return findings, filter_result, excluded_stats


def generate_filter_prompt_directive() -> str:
    """
    Generate prompt text to instruct agents about path scoping.

    Returns:
        Prompt text for agent instructions
    """
    return """
PATH SCOPING (CRITICAL):
When searching or analyzing code, ALWAYS exclude these directories:
- Virtual environments: venv/, env/, .venv/, virtualenv/
- Dependencies: node_modules/, .npm/, .eggs/
- Build artifacts: build/, dist/
- Cache directories: __pycache__/, .pytest_cache/, .mypy_cache/, .tox/
- Version control: .git/, .svn/, .hg/

DO NOT search or analyze files in these locations.
Focus analysis on application code only.
"""
