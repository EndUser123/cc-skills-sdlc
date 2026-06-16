#!/usr/bin/env python3
"""Mutation mode for /t skill - Fault-detection strength via mutmut 3.x."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class MutationResult:
    target: str
    module: str
    killed: int = 0
    survived: int = 0
    skipped: int = 0
    timeout: int = 0
    no_tests: int = 0
    mutation_score: float = 0.0
    target_score: int | None = None
    status: str = "skipped"
    equivalent_treated_as_pass: bool = False
    raw_output: str = ""


@dataclass
class MutationRunReport:
    target: str
    results: list = field(default_factory=list)
    passed: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    waived: list = field(default_factory=list)
    blocked: list = field(default_factory=list)


def _read_quality_gates(project_root):
    candidates = [
        Path("P:/.claude/quality_gates.json"),
        project_root / ".claude" / "quality_gates.json",
    ]
    for path in candidates:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return None


def _resolve_runner(gates):
    if gates and "tool" in gates and "runner" in gates["tool"]:
        return gates["tool"]["runner"]
    return "pytest -x --no-header -q"


def _parse_mutmut_summary(output):
    counts = {"killed": 0, "survived": 0, "skipped": 0, "timeout": 0, "no_tests": 0}
    pattern = re.compile(
        r"(\d+)\s+mutants?:\s*(\d+)\s+killed,\s*(\d+)\s+survived,\s*(\d+)\s+skipped,\s*(\d+)\s+timeout",
        re.IGNORECASE,
    )
    match = pattern.search(output)
    if match:
        counts["killed"] = int(match.group(2))
        counts["survived"] = int(match.group(3))
        counts["skipped"] = int(match.group(4))
        counts["timeout"] = int(match.group(5))
    return counts


def _module_key_for(target):
    p = Path(target)
    if "/" in target or "\\" in target:
        parts = p.with_suffix("").as_posix().split("/")
        while parts and parts[0] in {"src", "."}:
            parts.pop(0)
        return ".".join(parts) if parts else p.stem
    return target.removesuffix(".py") if target.endswith(".py") else target


def _get_target_for_module(gates, module_key):
    if not gates:
        return None, 15
    default_target = int(gates.get("default_mutation_score", 60))
    default_equiv = int(gates.get("equivalent_mutant_threshold", 15))
    modules = gates.get("modules", {}) or {}
    if module_key in modules:
        m = modules[module_key]
        return int(m.get("target", default_target)), int(
            m.get("skip_equivalent_threshold", default_equiv)
        )
    for prefix, m in modules.items():
        if module_key.startswith(prefix + ".") or module_key == prefix:
            return int(m.get("target", default_target)), int(
                m.get("skip_equivalent_threshold", default_equiv)
            )
    return default_target, default_equiv


def _effective_killed(killed, skipped, total, equiv_threshold_pct, treat_equiv_as_pass):
    if not treat_equiv_as_pass or total <= 0:
        return killed
    equiv_budget = max(0, (total * equiv_threshold_pct) // 100)
    if skipped <= equiv_budget:
        return killed + skipped
    return killed + equiv_budget


def run_mutation_for_module(target, project_root=None):
    project_root = project_root or Path.cwd()
    gates = _read_quality_gates(project_root)
    runner = _resolve_runner(gates)
    module_key = _module_key_for(target)
    target_score, equiv_threshold = _get_target_for_module(gates, module_key)
    treat_equiv_as_pass = bool((gates or {}).get("enforcement", {}).get(
        "treat_equivalent_mutants_under_threshold_as_pass", True
    ))
    cmd = ["mutmut", "run", "--use-coverage", "--runner", runner, "--target", target]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except FileNotFoundError:
        return MutationResult(
            target=target, module=module_key, status="skipped",
            raw_output='mutmut not installed; run: pip install "mutmut>=3.0,<4"',
        )
    except subprocess.TimeoutExpired:
        return MutationResult(
            target=target, module=module_key, status="timeout",
            raw_output="mutmut timed out after 600s",
        )
    counts = _parse_mutmut_summary(output)
    total = counts["killed"] + counts["survived"] + counts["skipped"] + counts["timeout"] + counts["no_tests"]
    if total == 0:
        return MutationResult(target=target, module=module_key, status="skipped", raw_output=output)
    effective = _effective_killed(counts["killed"], counts["skipped"], total, equiv_threshold, treat_equiv_as_pass)
    mutation_score = round((effective / total) * 100, 2) if total else 0.0
    if target_score is None or mutation_score >= target_score:
        status = "passed"
    else:
        status = "failed"
    return MutationResult(
        target=target, module=module_key,
        killed=counts["killed"], survived=counts["survived"], skipped=counts["skipped"],
        timeout=counts["timeout"], no_tests=counts["no_tests"],
        mutation_score=mutation_score, target_score=target_score, status=status,
        equivalent_treated_as_pass=treat_equiv_as_pass and counts["skipped"] > 0,
        raw_output=output[-4000:],
    )


def run_mutation(targets=None, project_root=None):
    project_root = project_root or Path.cwd()
    if not targets:
        gates = _read_quality_gates(project_root)
        targets = list(gates["modules"].keys()) if gates and gates.get("modules") else []
    report = MutationRunReport(target=",".join(targets) if targets else "(none)")
    bucket_keys = {"passed", "failed", "waived", "blocked"}
    for target in targets:
        result = run_mutation_for_module(target, project_root)
        report.results.append(result)
        key = result.status if result.status in bucket_keys else "blocked"
        getattr(report, key).append(result.module)
    return report


def format_mutation_report(report):
    lines = ["# Mutation Testing Report", "", "**Target:** " + report.target, ""]
    if not report.results:
        lines.append("*No mutation targets found.*")
        lines.append("")
        lines.append("Provide a target (file path) or define modules in P:/.claude/quality_gates.json.")
        return "\n".join(lines)
    lines.append("| Module | Killed | Survived | Skipped | Timeout | Score | Target | Status |")
    lines.append("|--------|-------:|---------:|--------:|--------:|------:|-------:|--------|")
    for r in report.results:
        ts = r.target_score if r.target_score is not None else "-"
        lines.append(
            "| `" + r.module + "` | " + str(r.killed) + " | " + str(r.survived) + " | "
            + str(r.skipped) + " | " + str(r.timeout) + " | "
            + format(r.mutation_score, ".1f") + "% | " + str(ts) + " | " + r.status + " |"
        )
    lines.extend([
        "", "## Summary", "",
        "- **Passed:** " + str(len(report.passed)),
        "- **Failed:** " + str(len(report.failed)),
        "- **Waived:** " + str(len(report.waived)),
        "- **Blocked:** " + str(len(report.blocked)),
        "",
    ])
    if report.failed:
        lines.append("### Failed modules")
        for m in report.failed:
            lines.append("- `" + m + "`")
        lines.append("")
        lines.append("> Sub-target mutation scores on critical-path modules require a waiver.")
    return "\n".join(lines)


def save_mutation_report(report, project_root, terminal_id):
    from datetime import UTC, datetime
    state_dir = project_root / ".claude" / "state" / "mutation_runs"
    state_dir.mkdir(parents=True, exist_ok=True)
    out_path = state_dir / (terminal_id + "_mutation.json")
    payload = {
        "target": report.target,
        "passed": report.passed, "failed": report.failed,
        "waived": report.waived, "blocked": report.blocked,
        "results": [asdict(r) for r in report.results],
        "timestamp": datetime.now(UTC).isoformat(),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    target_arg = sys.argv[1] if len(sys.argv) > 1 else None
    targets = [target_arg] if target_arg else None
    report = run_mutation(targets)
    print(format_mutation_report(report))
