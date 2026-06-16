#!/usr/bin/env python3
"""Unit tests for /t skill mutation_mode helpers.

Covers: scoring, equivalent-mutant budget, target lookup, mutmut summary
parser, and report formatting. Does NOT shell out to mutmut (that path is
exercised in the integration pilot, not in unit tests).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modes.mutation_mode import (  # noqa: E402
    MutationResult,
    MutationRunReport,
    _effective_killed,
    _get_target_for_module,
    _module_key_for,
    _parse_mutmut_summary,
    format_mutation_report,
)


def test_module_key_for_src_path() -> None:
    """Leading 'src/' is stripped from module key."""
    assert _module_key_for("src/skill_guard/breadcrumb/inference.py") == "skill_guard.breadcrumb.inference"


def test_module_key_for_dotted_path() -> None:
    """A dotted (already-module) path passes through unchanged."""
    assert _module_key_for("skill_guard.breadcrumb.inference") == "skill_guard.breadcrumb.inference"


def test_module_key_for_bare_filename() -> None:
    """A bare filename becomes its stem."""
    assert _module_key_for("inference.py") == "inference"


def test_parse_mutmut_summary_extracts_counts() -> None:
    """The mutmut summary regex extracts the four counts."""
    output = "12 mutants: 7 killed, 3 survived, 1 skipped, 1 timeout"
    counts = _parse_mutmut_summary(output)
    assert counts == {"killed": 7, "survived": 3, "skipped": 1, "timeout": 1, "no_tests": 0}


def test_parse_mutmut_summary_empty_when_no_match() -> None:
    """No summary line -> zero counts, not an exception."""
    counts = _parse_mutmut_summary("nothing useful here")
    assert counts == {"killed": 0, "survived": 0, "skipped": 0, "timeout": 0, "no_tests": 0}


def test_effective_killed_under_budget_adds_skipped() -> None:
    """When skipped <= budget, effective_killed = killed + skipped."""
    # 20 total, 15% budget = 3, skipped=2 -> effective = 12 + 2
    assert _effective_killed(12, 2, 20, 15, True) == 14


def test_effective_killed_over_budget_caps_at_budget() -> None:
    """When skipped > budget, only the budget amount is added."""
    # 20 total, 15% budget = 3, skipped=10 -> effective = 12 + 3
    assert _effective_killed(12, 10, 20, 15, True) == 15


def test_effective_killed_treat_equiv_disabled() -> None:
    """If treat_equiv_as_pass is False, skipped mutants are NOT added."""
    assert _effective_killed(12, 2, 20, 15, False) == 12


def test_effective_killed_zero_total_safe() -> None:
    """Zero total does not divide by zero."""
    assert _effective_killed(0, 0, 0, 15, True) == 0


def test_get_target_for_module_uses_modules_map() -> None:
    """Exact module key match returns its target and equiv threshold."""
    gates = {
        "default_mutation_score": 60,
        "equivalent_mutant_threshold": 15,
        "modules": {
            "skill_guard.breadcrumb.inference": {
                "target": 80,
                "skip_equivalent_threshold": 10,
            }
        },
    }
    target, equiv = _get_target_for_module(gates, "skill_guard.breadcrumb.inference")
    assert target == 80
    assert equiv == 10


def test_get_target_for_module_prefix_match() -> None:
    """A child module inherits a parent prefix's target when no exact key."""
    gates = {
        "default_mutation_score": 60,
        "equivalent_mutant_threshold": 15,
        "modules": {"skill_guard": {"target": 90}},
    }
    target, equiv = _get_target_for_module(gates, "skill_guard.breadcrumb.inference")
    assert target == 90
    assert equiv == 15


def test_get_target_for_module_falls_back_to_defaults() -> None:
    """Unknown module gets the JSON defaults."""
    gates = {"default_mutation_score": 60, "equivalent_mutant_threshold": 15, "modules": {}}
    target, equiv = _get_target_for_module(gates, "unrelated.module")
    assert target == 60
    assert equiv == 15


def test_get_target_for_module_no_gates() -> None:
    """With no gates file, return (None, 15) so the caller can short-circuit.

    The 'no targets' signal (None) is preserved instead of silently inventing
    a 60% default — callers must read P:/.claude/quality_gates.json explicitly.
    """
    target, equiv = _get_target_for_module(None, "any.module")
    assert target is None
    assert equiv == 15


def test_format_mutation_report_includes_summary_counts() -> None:
    """The report header counts passed/failed/waived/blocked correctly."""
    report = MutationRunReport(
        target="src/skill_guard/breadcrumb/inference.py",
        results=[
            MutationResult(target="src/skill_guard/breadcrumb/inference.py",
                           module="skill_guard.breadcrumb.inference",
                           killed=12, survived=2, skipped=1, timeout=0,
                           mutation_score=86.7, target_score=80, status="passed"),
            MutationResult(target="src/skill_guard/execution_runtime.py",
                           module="skill_guard.execution_runtime",
                           killed=8, survived=5, skipped=0, timeout=0,
                           mutation_score=61.5, target_score=80, status="failed"),
        ],
        passed=["skill_guard.breadcrumb.inference"],
        failed=["skill_guard.execution_runtime"],
        waived=[],
        blocked=[],
    )
    md = format_mutation_report(report)
    assert "# Mutation Testing Report" in md
    assert "skill_guard.breadcrumb.inference" in md
    assert "skill_guard.execution_runtime" in md
    assert "**Passed:** 1" in md
    assert "**Failed:** 1" in md
    assert "Failed modules" in md
    assert "skill_guard.execution_runtime" in md.split("## Summary")[1]


def test_format_mutation_report_handles_no_results() -> None:
    """Empty results list yields a helpful pointer to quality_gates.json."""
    report = MutationRunReport(target="(none)")
    md = format_mutation_report(report)
    assert "No mutation targets found" in md
    assert "quality_gates.json" in md
