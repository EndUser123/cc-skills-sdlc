"""Mutation testing config reader.

Single source of truth: P:/.claude/quality_gates.json
Consumed by /t (mutation mode), /tdd (mutation phase), /go (verification-result).

Module tiers:
  - critical: production-critical, target = critical_path_mutation_score
  - standard: default target

Equivalent mutant policy: mutants that survive because the code has a semantically
equivalent alternative (no observable behavior change) are SKIPPED, not failed -
UP TO `skip_equivalent_threshold` percent of total mutants. Beyond that threshold,
all surviving mutants count as a real gap.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG_PATH = Path(os.environ.get("CLAUDE_QUALITY_GATES", "P:/.claude/quality_gates.json"))


@dataclass(frozen=True)
class ModuleGate:
    module: str
    tier: str
    target: int
    skip_equivalent_threshold: int
    rationale: str = ""


@dataclass(frozen=True)
class QualityGates:
    version: int
    default_mutation_score: int
    critical_path_mutation_score: int
    equivalent_mutant_threshold: int
    modules: dict
    tool_name: str
    tool_version: str
    coverage_guided: bool
    runner: str
    timeout_seconds: int
    block_pr_on_failure: bool
    waiver_required_below_target: bool
    treat_equivalent_mutants_under_threshold_as_pass: bool

    def get_target(self, module: str) -> int:
        if module in self.modules:
            return self.modules[module].target
        if module.startswith("skill_guard."):
            return self.critical_path_mutation_score
        return self.default_mutation_score

    def get_module_gate(self, module: str) -> Optional[ModuleGate]:
        return self.modules.get(module)

    def list_critical_modules(self) -> list:
        return [m for m, g in self.modules.items() if g.tier == "critical"]


class QualityGatesError(Exception):
    """Raised when quality_gates.json is missing, malformed, or version-mismatched."""


def load_quality_gates(path=None) -> QualityGates:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        raise QualityGatesError(f"quality_gates.json not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise QualityGatesError(f"quality_gates.json is not valid JSON: {e}") from e

    if raw.get("version") != 1:
        raise QualityGatesError(
            f"Unsupported quality_gates.json version: {raw.get('version')} (expected 1)"
        )

    for required in ("default_mutation_score", "critical_path_mutation_score", "tool"):
        if required not in raw:
            raise QualityGatesError(f"quality_gates.json missing required key: {required}")

    tool = raw["tool"]
    enforcement = raw.get("enforcement", {})
    modules_raw = raw.get("modules", {})
    modules = {
        name: ModuleGate(
            module=name,
            tier=spec.get("tier", "standard"),
            target=spec["target"],
            skip_equivalent_threshold=spec.get("skip_equivalent_threshold", 15),
            rationale=spec.get("rationale", ""),
        )
        for name, spec in modules_raw.items()
    }

    return QualityGates(
        version=raw["version"],
        default_mutation_score=int(raw["default_mutation_score"]),
        critical_path_mutation_score=int(raw["critical_path_mutation_score"]),
        equivalent_mutant_threshold=int(raw.get("equivalent_mutant_threshold", 15)),
        modules=modules,
        tool_name=tool.get("name", "mutmut"),
        tool_version=tool.get("version", ">=3.0,<4"),
        coverage_guided=bool(tool.get("coverage_guided", True)),
        runner=tool.get("runner", "pytest -x --no-header -q"),
        timeout_seconds=int(tool.get("timeout_seconds", 600)),
        block_pr_on_failure=bool(enforcement.get("block_pr_on_failure", True)),
        waiver_required_below_target=bool(enforcement.get("waiver_required_below_target", True)),
        treat_equivalent_mutants_under_threshold_as_pass=bool(
            enforcement.get("treat_equivalent_mutants_under_threshold_as_pass", True)
        ),
    )


def _apply_equivalent_threshold(skipped, total, threshold_pct):
    """Cap tolerated skipped mutants at threshold_pct of total."""
    cap = (total * threshold_pct) / 100.0
    return min(skipped, int(cap))


def evaluate_mutation_run(
    gates,
    module,
    *,
    killed,
    survived,
    skipped,
    timeout,
    no_tests,
):
    """Evaluate a mutation run against the configured gate for the module.

    Returns a dict suitable for the verification-result.schema.json `mutation` block.
    """
    target = gates.get_target(module)
    total = killed + survived + skipped + no_tests + timeout
    if total == 0:
        return {
            "status": "skipped",
            "module": module,
            "target": target,
            "score": None,
            "killed": 0,
            "survived": 0,
            "skipped": 0,
            "no_tests": 0,
            "timeout": 0,
            "reason": "no_mutants_generated",
        }

    tolerated_skipped = _apply_equivalent_threshold(
        skipped, total, gates.equivalent_mutant_threshold
    )
    effective_total = killed + survived + tolerated_skipped
    score = round(100.0 * killed / effective_total, 2) if effective_total > 0 else 0.0
    meets_target = score >= target
    over_skip_threshold = skipped > (total * gates.equivalent_mutant_threshold / 100.0)

    if meets_target and not over_skip_threshold:
        status = "passed"
    elif meets_target and over_skip_threshold and gates.treat_equivalent_mutants_under_threshold_as_pass:
        status = "passed"
    elif meets_target and over_skip_threshold:
        status = "waived"
    else:
        status = "failed"

    return {
        "status": status,
        "module": module,
        "target": target,
        "score": score,
        "killed": killed,
        "survived": survived,
        "skipped": skipped,
        "no_tests": no_tests,
        "timeout": timeout,
        "tool": gates.tool_name,
        "tool_version": gates.tool_version,
        "coverage_guided": gates.coverage_guided,
    }
