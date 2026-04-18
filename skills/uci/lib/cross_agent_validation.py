"""
Cross-Agent Validation for Unified Code Inspection

Identifies consensus when multiple agents agree on findings at the same location.
Uses line-number evidence to validate findings and increase confidence.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of cross-agent validation."""
    validated_findings: List[Dict[str, Any]]
    unvalidated_findings: List[Dict[str, Any]]
    consensus_map: Dict[str, List[str]]  # location -> list of agent names
    validation_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class LocationKey:
    """Key for identifying finding locations."""
    file_path: str
    line_number: int
    category: str

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line_number}:{self.category}"

    @classmethod
    def from_finding(cls, finding: Dict[str, Any]) -> "LocationKey":
        """Extract location key from a finding."""
        file_path = finding.get("location", "").split(":")[0]
        line_number = finding.get("line_number", 0)

        # Try to extract line number from location string
        location = finding.get("location", "")
        if ":" in location:
            parts = location.split(":")
            try:
                line_number = int(parts[-1]) if len(parts) > 1 else 0
            except ValueError:
                line_number = 0

        category = finding.get("category", "general")

        return cls(
            file_path=file_path,
            line_number=line_number,
            category=category
        )


class CrossAgentValidator:
    """
    Validates findings across multiple agents using location-based consensus.

    Validation rules:
    1. Findings at the same location (file:line:category) from multiple agents are validated
    2. Findings from a single agent are unvalidated (require manual review)
    3. Confidence increases with number of agreeing agents
    4. Pre-existing issues are tracked separately
    """

    def __init__(
        self,
        min_consensus: int = 2,
        confidence_boost: float = 0.15
    ):
        """
        Initialize cross-agent validator.

        Args:
            min_consensus: Minimum number of agents required for validation
            confidence_boost: Confidence increase per additional agreeing agent
        """
        self.min_consensus = min_consensus
        self.confidence_boost = confidence_boost

    def validate_findings(
        self,
        agent_results: Dict[str, List[Dict[str, Any]]]
    ) -> ValidationResult:
        """
        Validate findings across multiple agents using location-based consensus.

        Args:
            agent_results: Dictionary mapping agent name to their findings

        Returns:
            ValidationResult with validated findings, consensus map, and stats
        """
        # Group findings by location
        location_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        location_agents: Dict[str, Set[str]] = defaultdict(set)

        for agent_name, findings in agent_results.items():
            for finding in findings:
                key = LocationKey.from_finding(finding)

                # Store finding with agent metadata
                finding_with_agent = {**finding, "_agent": agent_name}
                location_groups[str(key)].append(finding_with_agent)
                location_agents[str(key)].add(agent_name)

        # Separate validated (consensus) from unvalidated findings
        validated = []
        unvalidated = []
        consensus_map: Dict[str, List[str]] = {}

        for location_key, findings_list in location_groups.items():
            agents = location_agents[location_key]
            consensus_map[location_key] = list(agents)

            # Select the finding with highest confidence as representative
            primary_finding = max(
                findings_list,
                key=lambda f: f.get("confidence", 0)
            )

            # Add validation metadata
            primary_finding["_validated_by"] = list(agents)
            primary_finding["_consensus_count"] = len(agents)

            # Calculate confidence boost
            if len(agents) >= self.min_consensus:
                # Boost confidence based on number of agreeing agents
                boost = min(
                    (len(agents) - 1) * self.confidence_boost,
                    0.30  # Max boost of 30%
                )
                primary_finding["confidence"] = min(
                    primary_finding.get("confidence", 0.5) + boost,
                    1.0
                )
                primary_finding["_validated"] = True
                validated.append(primary_finding)
            else:
                primary_finding["_validated"] = False
                unvalidated.append(primary_finding)

        # Calculate statistics
        total_findings = sum(len(f) for f in agent_results.values())
        unique_locations = len(location_groups)

        stats = {
            "total_findings": total_findings,
            "unique_locations": unique_locations,
            "validated_findings": len(validated),
            "unvalidated_findings": len(unvalidated),
            "validation_rate": len(validated) / unique_locations if unique_locations > 0 else 0
        }

        return ValidationResult(
            validated_findings=validated,
            unvalidated_findings=unvalidated,
            consensus_map=consensus_map,
            validation_stats=stats
        )

    def detect_pre_existing_issues(
        self,
        findings: List[Dict[str, Any]],
        base_diff: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Distinguish between issues in user's diff vs pre-existing issues.

        Args:
            findings: List of findings with location information
            base_diff: Git diff output for scope detection

        Returns:
            Tuple of (new_issues, pre_existing_issues)
        """
        # Parse diff to get changed files and line ranges
        changed_files = self._parse_diff(base_diff)

        new_issues = []
        pre_existing = []

        for finding in findings:
            location = finding.get("location", "")
            if not location:
                continue

            file_path = location.split(":")[0]

            # Check if finding is in changed files
            if file_path in changed_files:
                finding["_pre_existing"] = False
                new_issues.append(finding)
            else:
                finding["_pre_existing"] = True
                pre_existing.append(finding)

        return new_issues, pre_existing

    def _parse_diff(self, diff_output: str) -> Set[str]:
        """
        Parse git diff to extract changed files.

        Args:
            diff_output: Git diff output

        Returns:
            Set of changed file paths
        """
        changed_files = set()

        for line in diff_output.split("\n"):
            if line.startswith("+++ ") or line.startswith("--- "):
                # Extract file path from diff header
                parts = line.split()
                if len(parts) >= 2:
                    file_path = parts[1].lstrip("b/")
                    changed_files.add(file_path)

        return changed_files


def validate_agent_registry_compliance(
    agent_registry: Dict[str, Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Validate that all agents in registry are constitutionally compliant.

    Args:
        agent_registry: Dictionary of agent configurations

    Returns:
        Tuple of (is_compliant, list of non_compliant_agents)
    """
    from .constitutional_filter import validate_agent_registry_compliance as validate_constitutional

    return validate_constitutional(agent_registry)


# Convenience functions for common use cases
def validate_findings(
    agent_results: Dict[str, List[Dict[str, Any]]],
    min_consensus: int = 2
) -> ValidationResult:
    """
    Validate findings across multiple agents.

    Convenience function that creates validator and applies it.

    Args:
        agent_results: Dictionary mapping agent name to their findings
        min_consensus: Minimum number of agents required for validation

    Returns:
        ValidationResult with validated findings and consensus map
    """
    validator = CrossAgentValidator(min_consensus=min_consensus)
    return validator.validate_findings(agent_results)


def merge_validated_results(
    validated: List[Dict[str, Any]],
    unvalidated: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge validated and unvalidated findings into single list.

    Args:
        validated: List of validated findings
        unvalidated: List of unvalidated findings

    Returns:
        Combined list with validated findings first
    """
    merged = []

    # Add validated findings first (higher priority)
    for finding in validated:
        finding.setdefault("_validation_status", "validated")
        merged.append(finding)

    # Add unvalidated findings after
    for finding in unvalidated:
        finding.setdefault("_validation_status", "unvalidated")
        merged.append(finding)

    return merged
