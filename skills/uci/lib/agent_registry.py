"""
Agent Registry and Mode-Based Selector for Unified Code Inspection

Defines AGENT_REGISTRY and MODE_AGENTS mappings for mode-based agent selection.
- Triage mode selects 3 core agents
- Standard mode selects 4 agents
- Deep mode selects 8 agents
- Comprehensive mode selects all 11+ agents
"""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Agent Registry with metadata
AGENT_REGISTRY: Dict[str, Dict[str, any]] = {
    # Core agents (triage mode)
    "adversarial-logic": {
        "tier": "core",
        "focus": "logical errors, edge cases, incorrect reasoning",
        "token_limit": 10,
        "subagent_type": "adversarial-logic"
    },
    "adversarial-testing": {
        "tier": "core",
        "focus": "missing test scenarios, coverage gaps",
        "token_limit": 10,
        "subagent_type": "adversarial-testing"
    },
    "adversarial-security": {
        "tier": "core",
        "focus": "data leaks, access control, injection vectors",
        "token_limit": 10,
        "subagent_type": "adversarial-security"
    },

    # Extended agents (standard/deep modes)
    "adversarial-performance": {
        "tier": "extended",
        "focus": "N+1 patterns, bottlenecks, async issues",
        "token_limit": 8,
        "subagent_type": "adversarial-performance"
    },
    "adversarial-quality": {
        "tier": "extended",
        "focus": "maintainability risks, technical debt",
        "token_limit": 8,
        "subagent_type": "adversarial-quality"
    },
    "adversarial-compliance": {
        "tier": "extended",
        "focus": "spec/schema validation",
        "token_limit": 8,
        "subagent_type": "adversarial-compliance"
    },
    "adversarial-qa": {
        "tier": "extended",
        "focus": "test coverage gaps, missing scenarios",
        "token_limit": 8,
        "subagent_type": "adversarial-qa"
    },

    # Extended agents (standard/deep modes) - NEW: state-transition agents (Alternative A/B: parallel-only)
    "adversarial-state-machine": {
        "tier": "extended",
        "focus": "state-transition bugs, invalid states, missing validation, race conditions",
        "token_limit": 8,
        "subagent_type": "adversarial-state-machine"
    },
    "adversarial-invariants": {
        "tier": "extended",
        "focus": "ID collision, referential integrity, uniqueness constraints",
        "token_limit": 8,
        "subagent_type": "adversarial-invariants"
    },
    "adversarial-io-validation": {
        "tier": "extended",
        "focus": "I/O assumption auditing, path validation, external service assumptions",
        "token_limit": 8,
        "subagent_type": "adversarial-io-validation"
    },

    # Comprehensive agents (comprehensive mode only)
    "simplification": {
        "tier": "comprehensive",
        "focus": "cognitive load, premature abstractions, change atomicity, clarity, consistency, maintainability",
        "token_limit": 10,
        "subagent_type": "code-simplifier:code-simplifier"
    },
    "adversarial-rca": {
        "tier": "comprehensive",
        "focus": "root cause analysis with multi-agent reasoning",
        "token_limit": 8,
        "subagent_type": "adversarial-rca"
    },
    "adversarial-failure-modes": {
        "tier": "comprehensive",
        "focus": "domain-aware anti-patterns with web research",
        "token_limit": 8,
        "subagent_type": "adversarial-failure-modes"
    },
    "deployment-safety": {
        "tier": "comprehensive",
        "focus": "migration concerns, observability, rollback safety, infrastructure, runtime concerns",
        "token_limit": 10,
        "subagent_type": "general-purpose"
    },
    "python-modernization": {
        "tier": "comprehensive",
        "focus": "Python 3.12+ idioms, type hints, modern patterns",
        "token_limit": 10,
        "triggers": [".py files"],
        "subagent_type": "python-simplifier"
    },
    "test-quality-roi": {
        "tier": "comprehensive",
        "focus": "ROI-focused coverage, critical paths vs low-risk code, test quality assessment",
        "token_limit": 10,
        "subagent_type": "qa-engineer"
    },
}

# Mode-based agent selection (Alternative A/B: Parallel-only with cognitive load mitigations)
#
# Tier-based activation (Phase 0.5 mitigation):
# - triage (3 agents): Core agents only - minimal cognitive load
# - standard (4 agents): Core + performance - baseline cognitive load
# - deep (8 agents): Extended tier - adds state-machine only (tier-based activation)
# - comprehensive (11+ agents): All agents including new state-transition agents
#
MODE_AGENTS: Dict[str, List[str] | str] = {
    "triage": ["adversarial-logic", "adversarial-testing", "adversarial-security"],
    "standard": ["adversarial-logic", "adversarial-testing", "adversarial-security", "adversarial-performance"],
    "deep": [
        "adversarial-logic",
        "adversarial-testing",
        "adversarial-security",
        "adversarial-performance",
        "adversarial-quality",
        "adversarial-compliance",
        "adversarial-qa",
        "adversarial-state-machine"  # NEW: Tier-based activation
    ],
    "comprehensive": "all",  # All agents (including new state-transition agents)
}

# Change-type-based agent selection (overrides default mode selection)
CHANGE_TYPE_AGENTS: Dict[str, List[str]] = {
    "bug_fix": ["adversarial-logic", "adversarial-testing", "adversarial-security"],
    "new_feature": [
        "adversarial-logic",
        "adversarial-testing",
        "adversarial-security",
        "adversarial-performance",
        "adversarial-quality"
    ],
    "refactor": [
        "adversarial-logic",
        "adversarial-performance",
        "adversarial-quality",
        "simplification"
    ],
    "config_infra": ["adversarial-security", "adversarial-compliance", "adversarial-quality"],
    "tests_only": ["adversarial-testing", "adversarial-qa", "adversarial-quality"],
}


def select_agents(
    mode: str = "standard",
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    change_type: Optional[str] = None,
    file_extensions: Optional[Set[str]] = None
) -> List[str]:
    """
    Select agents based on mode, include/exclude lists, and change type.

    Args:
        mode: Review mode (triage|standard|deep|comprehensive)
        include: Set of agents to include (overrides mode)
        exclude: Set of agents to exclude
        change_type: Change type for custom selection
        file_extensions: File extensions to trigger specialized agents

    Returns:
        List of agent names to run

    Examples:
        >>> select_agents(mode="triage")
        ['adversarial-logic', 'adversarial-testing', 'adversarial-security']

        >>> select_agents(mode="deep", exclude={"adversarial-qa"})
        ['adversarial-logic', 'adversarial-testing', 'adversarial-security', ...]
    """
    # Priority 1: Explicit include overrides mode
    if include:
        agents = list(include)
    elif change_type and change_type in CHANGE_TYPE_AGENTS:
        agents = CHANGE_TYPE_AGENTS[change_type]
    else:
        # Use mode-based selection
        mode_agents = MODE_AGENTS.get(mode, MODE_AGENTS["standard"])
        if mode_agents == "all":
            agents = _get_all_agents()
        else:
            agents = list(mode_agents)

    # Apply exclude filter
    if exclude:
        agents = [a for a in agents if a not in exclude]

    # Add triggered agents (e.g., python-modernization for .py files)
    if file_extensions:
        for agent_name, agent_config in AGENT_REGISTRY.items():
            triggers = agent_config.get("triggers", [])
            if any(trigger in ".".join(file_extensions) for trigger in triggers):
                if agent_name not in agents:
                    agents.append(agent_name)

    return agents


def _get_all_agents() -> List[str]:
    """Get all available agent names."""
    return list(AGENT_REGISTRY.keys())


def get_agent_config(agent_name: str) -> Dict[str, any]:
    """Get configuration for a specific agent."""
    return AGENT_REGISTRY.get(agent_name, {})


def get_token_limit(agent_name: str) -> int:
    """Get token limit for a specific agent."""
    config = get_agent_config(agent_name)
    return config.get("token_limit", 10)


def validate_agent_names(agent_names: List[str]) -> tuple[bool, List[str]]:
    """
    Validate that all agent names exist in registry.

    Returns:
        Tuple of (is_valid, list of invalid names)
    """
    invalid = [name for name in agent_names if name not in AGENT_REGISTRY]
    return (len(invalid) == 0, invalid)
