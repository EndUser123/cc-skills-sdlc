#!/usr/bin/env python3
"""Test for TASK-026 parallelization rationale documentation.

This test verifies that the plan document includes proper explanation
of why certain tasks can run in parallel.
"""

import re
from pathlib import Path


def test_parallelization_section_exists():
    """Verify parallelization rationale section exists in plan."""
    plan_path = (
        Path(__file__).parent.parent.parent.parent
        / "hooks/plans/plan-20260315-skill-enhancements-core-plan.md"
    )

    content = plan_path.read_text()

    # Should have a parallelization rationale section
    assert (
        "## Parallelization Rationale" in content or "## Task Parallelization" in content
    ), "Plan should include a parallelization rationale section"


def test_independence_documentation():
    """Verify that test independence is documented."""
    plan_path = (
        Path(__file__).parent.parent.parent.parent
        / "hooks/plans/plan-20260315-skill-enhancements-core-plan.md"
    )

    content = plan_path.read_text()

    # Should mention test file independence
    assert re.search(
        r"independent.*test", content, re.IGNORECASE
    ), "Should document that test files are independent"


def test_shared_state_documentation():
    """Verify that lack of shared mutable state is documented."""
    plan_path = (
        Path(__file__).parent.parent.parent.parent
        / "hooks/plans/plan-20260315-skill-enhancements-core-plan.md"
    )

    content = plan_path.read_text()

    # Should mention no shared mutable state
    assert re.search(
        r"shared.*state|shared.*mutable", content, re.IGNORECASE
    ), "Should document absence of shared mutable state"


def test_fixture_isolation_documentation():
    """Verify that fixture isolation is documented."""
    plan_path = (
        Path(__file__).parent.parent.parent.parent
        / "hooks/plans/plan-20260315-skill-enhancements-core-plan.md"
    )

    content = plan_path.read_text()

    # Should mention fixtures providing isolation
    assert re.search(
        r"fixture.*isolation|isolation.*fixture", content, re.IGNORECASE
    ), "Should document that fixtures provide isolation"


def test_merge_conflict_warning():
    """Verify that merge conflict risk is noted."""
    plan_path = (
        Path(__file__).parent.parent.parent.parent
        / "hooks/plans/plan-20260315-skill-enhancements-core-plan.md"
    )

    content = plan_path.read_text()

    # Should mention merge conflict risk
    assert re.search(
        r"merge.*conflict|conflict.*merge", content, re.IGNORECASE
    ), "Should note merge conflict risk for parallel development"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
