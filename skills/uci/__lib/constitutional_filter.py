"""
Constitutional Filter for Unified Code Inspection

Filters findings according to solo-dev constitutional principles:
- Singular Decision Authority: Technical choices unrestricted
- Subagent Optimization: Specialist delegation encouraged
- Enterprise Patterns: Organizational overhead rejected
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of constitutional filtering."""
    filtered_findings: List[Dict[str, Any]]
    rejected_findings: List[Dict[str, Any]]
    rejected_count: int = 0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)


class ConstitutionalFilter:
    """
    Filters adversarial review findings against constitutional principles.

    Solo-dev constitutional principles:
    1. Singular Decision Authority (97% confidence)
       - Architectural choices unrestricted
       - Only process patterns requiring others' consent prohibited

    2. Subagent Optimization Mandate (95% confidence)
       - Specialist delegation encouraged
       - Autonomous specialist execution allowed

    3. Enterprise Patterns Rejection (89% rejection rate)
       - Team coordination prohibited
       - Stakeholder approval prohibited
       - Architectural review boards prohibited
    """

    # Prohibited patterns that violate solo-dev constraints
    PROHIBITED_PATTERNS = [
        "team coordination",
        "team approval",
        "stakeholder consensus",
        "stakeholder approval",
        "cross-team coordination",
        "multi-person sign-off",
        "management approval",
        "architectural review board",
        "team review required",
        "requires team discussion",
        "coordinate with team",
        "get team consensus",
    ]

    # Allowed categories that are constitutionally compliant
    ALLOWED_CATEGORIES = [
        "logic", "testing", "security", "performance", "conventions",
        "quality", "compliance", "qa", "simplification", "rca",
        "failure-modes", "deployment", "modernization", "test-quality",
        "spec", "schema", "validation", "error", "async", "race",
        "resource", "maintainability", "coverage", "type", "syntax",
        "stdlib", "anti-pattern"
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Initialize constitutional filter.

        Args:
            strict_mode: If True, reject all findings with prohibited patterns.
                        If False, mark findings but allow them through with warning.
        """
        self.strict_mode = strict_mode

    def filter_findings(
        self,
        findings: List[Dict[str, Any]]
    ) -> FilterResult:
        """
        Filter findings against constitutional principles.

        Args:
            findings: List of agent findings to filter

        Returns:
            FilterResult with filtered_findings, rejected_findings, and stats
        """
        filtered = []
        rejected = []
        reasons = {}

        for finding in findings:
            violation = self._check_constitutional_violation(finding)

            if violation:
                rejected.append(finding)
                reason = violation["reason"]
                reasons[reason] = reasons.get(reason, 0) + 1

                if not self.strict_mode:
                    # In non-strict mode, mark but keep with warning
                    finding["constitutional_warning"] = (
                        f"[SOLO-DEV VIOLATION] {reason}"
                    )
                    filtered.append(finding)
            else:
                filtered.append(finding)

        return FilterResult(
            filtered_findings=filtered,
            rejected_findings=rejected,
            rejected_count=len(rejected),
            rejection_reasons=reasons
        )

    def _check_constitutional_violation(
        self,
        finding: Dict[str, Any]
    ) -> Dict[str, str] | None:
        """
        Check if a finding violates constitutional principles.

        Args:
            finding: Single finding to check

        Returns:
            None if compliant, or dict with 'reason' key if violation
        """
        # Check problem description for prohibited patterns
        problem = finding.get("problem", "").lower()
        recommendation = finding.get("recommendation", "").lower()
        category = finding.get("category", "").lower()

        # Check for prohibited patterns in problem and recommendation
        for prohibited in self.PROHIBITED_PATTERNS:
            if prohibited in problem or prohibited in recommendation:
                return {
                    "reason": f"Prohibited pattern: '{prohibited}' (violates Singular Decision Authority)",
                    "pattern": prohibited
                }

        # Check if category itself is problematic
        if category in ["enterprise", "team", "stakeholder"]:
            return {
                "reason": f"Prohibited category: '{category}' (violates Solo-Dev constraints)",
                "category": category
            }

        # Finding is constitutionally compliant
        return None

    def validate_agent_config(self, agent_config: Dict[str, Any]) -> bool:
        """
        Validate that an agent configuration is constitutionally compliant.

        Args:
            agent_config: Agent configuration dictionary

        Returns:
            True if compliant, False otherwise
        """
        # Check agent focus for prohibited patterns
        focus = agent_config.get("focus", "").lower()

        for prohibited in self.PROHIBITED_PATTERNS:
            if prohibited in focus:
                logger.warning(
                    f"Agent {agent_config.get('name')} has prohibited focus pattern: {prohibited}"
                )
                return False

        return True

    def get_allowed_categories(self) -> Set[str]:
        """Get set of constitutionally compliant finding categories."""
        return set(self.ALLOWED_CATEGORIES)

    def get_prohibited_patterns(self) -> List[str]:
        """Get list of prohibited patterns."""
        return list(self.PROHIBITED_PATTERNS)

    def is_strict_mode(self) -> bool:
        """Check if filter is in strict mode."""
        return self.strict_mode

    def set_strict_mode(self, strict: bool) -> None:
        """Set strict mode for filtering."""
        self.strict_mode = strict


def create_constitutional_filter(strict_mode: bool = False) -> ConstitutionalFilter:
    """
    Factory function to create a constitutional filter.

    Args:
        strict_mode: If True, reject all findings with prohibited patterns

    Returns:
        ConstitutionalFilter instance
    """
    return ConstitutionalFilter(strict_mode=strict_mode)


# Convenience functions for common use cases
def filter_constitutional_violations(
    findings: List[Dict[str, Any]],
    strict_mode: bool = False
) -> FilterResult:
    """
    Filter findings against constitutional principles.

    Convenience function that creates filter and applies it.

    Args:
        findings: List of agent findings to filter
        strict_mode: If True, reject all findings with prohibited patterns

    Returns:
        FilterResult with filtered findings and rejection stats
    """
    filter_obj = create_constitutional_filter(strict_mode=strict_mode)
    return filter_obj.filter_findings(findings)


def validate_agent_registry_compliance(
    agent_registry: Dict[str, Dict[str, Any]]
) -> tuple[bool, List[str]]:
    """
    Validate that all agents in registry are constitutionally compliant.

    Args:
        agent_registry: Dictionary of agent configurations

    Returns:
        Tuple of (is_compliant, list of non_compliant_agents)
    """
    filter_obj = create_constitutional_filter()
    non_compliant = []

    for agent_name, agent_config in agent_registry.items():
        if not filter_obj.validate_agent_config(agent_config):
            non_compliant.append(agent_name)

    return (len(non_compliant) == 0, non_compliant)
