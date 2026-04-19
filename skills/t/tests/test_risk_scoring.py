#!/usr/bin/env python3
"""Test deterministic risk scoring."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from director_output import determine_strictness
from risk_scoring import ChangeContext, Kind, Size, Tier, calculate_risk_score


def test_risk_score_determinism() -> None:
    """Same inputs produce same risk score."""
    ctx = ChangeContext(
        git_state="unstaged",
        tier=Tier.T1_CRITICAL,
        size=Size.M_FUNCTION,
        kind=Kind.CORE_LOGIC,
        file_path="router.py",
    )

    score1 = calculate_risk_score(ctx)
    score2 = calculate_risk_score(ctx)
    score3 = calculate_risk_score(ctx)

    # All three scores must be identical
    assert score1 == score2 == score3
    assert 0.0 <= score1 <= 1.0


def test_high_risk_thresholds() -> None:
    """Test that HIGH risk triggers T1+T2 required."""
    # Create maximum risk context
    ctx = ChangeContext(
        git_state="full_scan",  # 1.3x multiplier
        tier=Tier.T1_CRITICAL,  # 1.0 weight
        size=Size.S_MODULE,  # 1.0 weight
        kind=Kind.CORE_LOGIC,  # 1.0 weight
        file_path="router.py",
    )

    risk = calculate_risk_score(ctx)
    strictness = determine_strictness(risk)

    # Should be high risk with strict enforcement
    assert risk >= 0.7
    assert strictness.t1_required is True
    assert strictness.t2_required is True


def test_low_risk_thresholds() -> None:
    """Test that LOW risk skips T2."""
    # Create minimum risk context
    ctx = ChangeContext(
        git_state="no_git",  # 0.8x multiplier
        tier=Tier.T3_NICE_TO_HAVE,  # 0.3 weight
        size=Size.L_LINE,  # 0.2 weight
        kind=Kind.INTEGRATION,  # 0.5 weight
        file_path="utils.py",
    )

    risk = calculate_risk_score(ctx)
    strictness = determine_strictness(risk)

    # Should be low risk with relaxed enforcement
    assert risk < 0.4
    assert strictness.t2_required is False


if __name__ == "__main__":
    test_risk_score_determinism()
    print("✅ test_risk_score_determinism passed")

    test_high_risk_thresholds()
    print("✅ test_high_risk_thresholds passed")

    test_low_risk_thresholds()
    print("✅ test_low_risk_thresholds passed")

    print("\nAll risk scoring tests passed!")
