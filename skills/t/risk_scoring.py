#!/usr/bin/env python3
"""
Deterministic risk scoring for adaptive testing depth.

Implements formula: risk = (tier_weight × 0.5) + (size_weight × 0.3) + (kind_weight × 0.2)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum


def _ensure_import_paths() -> None:
    """Ensure CSF modules are in sys.path."""
    for candidate in ("P:\\\\\\__csf/src", "P:\\\\\\__csf", "P:\\\\\\"):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


class Tier(Enum):
    """Test tier classification."""
    T1_CRITICAL = "t1_critical"
    T2_IMPORTANT = "t2_important"
    T3_NICE_TO_HAVE = "t3_nice_to_have"


class Size(Enum):
    """Change size classification."""
    S_MODULE = "s_module"  # Full module or large change
    M_FUNCTION = "m_function"  # Function-level change
    L_LINE = "l_line"  # Single line or small change


class Kind(Enum):
    """Change kind classification."""
    CORE_LOGIC = "core_logic"
    ERROR_PATH = "error_path"
    EDGE_CASE = "edge_case"
    INTEGRATION = "integration"


@dataclass
class ChangeContext:
    """Context for risk calculation."""

    git_state: str  # "no_git", "unstaged", "staged", "last_commit", "full_scan"
    tier: Tier
    size: Size
    kind: Kind
    file_path: str


def calculate_risk_score(ctx: ChangeContext) -> float:
    """
    Calculate deterministic risk score from tier, size, and kind.

    Formula:
        risk = (tier_weight × 0.5) + (size_weight × 0.3) + (kind_weight × 0.2)
        risk = risk × git_state_multiplier

    Where:
        tier_weight:  t1=1.0, t2=0.6, t3=0.3
        size_weight:  s=1.0, m=0.5, l=0.2
        kind_weight:  core=1.0, error=0.9, edge=0.7, integration=0.5

        git_multiplier:  full_scan=1.3, staged=1.2, unstaged=1.1,
                       last_commit=1.0, no_git=0.8

    Args:
        ctx: Change context with tier, size, kind, and git state

    Returns:
        float in range [0.0, 1.0] rounded to 3 decimal places

    Examples:
        >>> ctx = ChangeContext("unstaged", Tier.T1_CRITICAL, Size.S_MODULE, Kind.CORE_LOGIC, "router.py")
        >>> score = calculate_risk_score(ctx)
        >>> 0.0 <= score <= 1.0
        True
    """
    # Tier weights
    tier_weights = {
        Tier.T1_CRITICAL: 1.0,
        Tier.T2_IMPORTANT: 0.6,
        Tier.T3_NICE_TO_HAVE: 0.3,
    }

    # Size weights
    size_weights = {
        Size.S_MODULE: 1.0,
        Size.M_FUNCTION: 0.5,
        Size.L_LINE: 0.2,
    }

    # Kind weights
    kind_weights = {
        Kind.CORE_LOGIC: 1.0,
        Kind.ERROR_PATH: 0.9,
        Kind.EDGE_CASE: 0.7,
        Kind.INTEGRATION: 0.5,
    }

    # Git state multipliers
    git_multipliers = {
        "full_scan": 1.3,
        "staged": 1.2,
        "unstaged": 1.1,
        "last_commit": 1.0,
        "no_git": 0.8,
    }

    # Calculate components
    tier_weight = tier_weights.get(ctx.tier, 0.5)
    size_weight = size_weights.get(ctx.size, 0.5)
    kind_weight = kind_weights.get(ctx.kind, 0.5)

    # Calculate base risk
    base_risk = (tier_weight * 0.5) + (size_weight * 0.3) + (kind_weight * 0.2)

    # Apply git state multiplier
    git_multiplier = git_multipliers.get(ctx.git_state, 1.0)
    final_risk = min(base_risk * git_multiplier, 1.0)

    return round(final_risk, 3)


def detect_change_context(
    file_path: str, git_state: str
) -> ChangeContext:
    """
    Auto-detect tier, size, kind from file path and git state.

    Heuristics:
        - Tier: "core" or "kernel" in path → t1_critical
                 "src" or "lib" in path → t2_important
                 else → t3_nice_to_have

        - Size: git_state == "full_scan" → s_module
                 git_state in ("staged", "unstaged") → m_function
                 else → l_line

        - Kind: "error" or "exception" in path → error_path
                "test" or "integration" in path → integration
                "edge" or "boundary" in path → edge_case
                else → core_logic

    Args:
        file_path: Path to file being changed
        git_state: Current git state

    Returns:
        ChangeContext with detected tier, size, kind

    Examples:
        >>> ctx = detect_change_context("router.py", "unstaged")
        >>> ctx.tier in [Tier.T1_CRITICAL, Tier.T2_IMPORTANT, Tier.T3_NICE_TO_HAVE]
        True
        >>> ctx.size in [Size.S_MODULE, Size.M_FUNCTION, Size.L_LINE]
        True
        >>> ctx.kind in [Kind.CORE_LOGIC, Kind.ERROR_PATH, Kind.EDGE_CASE, Kind.INTEGRATION]
        True
    """
    path_lower = file_path.lower()

    # Detect tier
    if any(keyword in path_lower for keyword in ("core", "kernel")):
        tier = Tier.T1_CRITICAL
    elif any(keyword in path_lower for keyword in ("src", "lib")):
        tier = Tier.T2_IMPORTANT
    else:
        tier = Tier.T3_NICE_TO_HAVE

    # Detect size
    if git_state == "full_scan":
        size = Size.S_MODULE
    elif git_state in ("staged", "unstaged"):
        size = Size.M_FUNCTION
    else:
        size = Size.L_LINE

    # Detect kind
    if any(keyword in path_lower for keyword in ("error", "exception")):
        kind = Kind.ERROR_PATH
    elif any(keyword in path_lower for keyword in ("test", "integration")):
        kind = Kind.INTEGRATION
    elif any(keyword in path_lower for keyword in ("edge", "boundary")):
        kind = Kind.EDGE_CASE
    else:
        kind = Kind.CORE_LOGIC

    return ChangeContext(
        git_state=git_state,
        tier=tier,
        size=size,
        kind=kind,
        file_path=file_path,
    )
