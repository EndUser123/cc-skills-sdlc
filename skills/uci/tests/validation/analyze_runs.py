#!/usr/bin/env python3
"""
Analyze /uci runs to detect missed bug patterns.

Phase 0 validation: Answer key questions about what bugs are being found
and whether new agents would add value.
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add validation directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data_collector import BugCategory, UCIRunCollector


def analyze_bug_categories(runs: list) -> dict:
    """Analyze bug categories across all runs."""
    category_counts = Counter()
    severity_by_category = defaultdict(Counter)

    for run in runs:
        for finding in run.get("findings", []):
            # Classify finding into bug category
            category = BugCategory.classify(finding)
            if category:
                category_counts[category.value] += 1
                severity = finding.get("severity", "medium")
                severity_by_category[category.value][severity] += 1

    return {
        "category_counts": dict(category_counts),
        "severity_by_category": {k: dict(v) for k, v in severity_by_category.items()},
        "total_findings": sum(category_counts.values()),
    }


def detect_gaps(category_counts: dict, runs: list) -> dict:
    """
    Detect potential gaps in bug detection.

    Returns analysis of whether new agents (state-machine, invariants, io-validation)
    would add value based on what's being found vs. what's missing.
    """
    findings_by_category = defaultdict(list)

    # Group findings by category
    for run in runs:
        for finding in run.get("findings", []):
            category = BugCategory.classify(finding)
            if category:
                findings_by_category[category.value].append(finding)

    # Analyze gaps
    gaps = {}

    # State-transition bugs
    state_findings = findings_by_category.get("state-transition", [])
    if len(state_findings) == 0:
        gaps["state-transition"] = {
            "status": "MISSING",
            "evidence": "No state-transition bugs found across any runs",
            "new_agent_value": "HIGH",
            "agents": ["state-machine", "invariants"],
        }
    else:
        gaps["state-transition"] = {
            "status": "FOUND",
            "count": len(state_findings),
            "new_agent_value": "LOW",
            "agents": [],
        }

    # TOCTOU bugs
    toctou_findings = findings_by_category.get("toctou", [])
    if len(toctou_findings) == 0:
        gaps["toctou"] = {
            "status": "MISSING",
            "evidence": "No TOCTOU race conditions found",
            "new_agent_value": "HIGH",
            "agents": ["state-machine", "io-validation"],
        }
    else:
        gaps["toctou"] = {
            "status": "FOUND",
            "count": len(toctou_findings),
            "new_agent_value": "LOW",
            "agents": [],
        }

    # ID collision bugs
    id_collision_findings = findings_by_category.get("id-collision", [])
    if len(id_collision_findings) == 0:
        gaps["id-collision"] = {
            "status": "MISSING",
            "evidence": "No ID collision issues found",
            "new_agent_value": "MEDIUM",
            "agents": ["state-machine", "invariants"],
        }
    else:
        gaps["id-collision"] = {
            "status": "FOUND",
            "count": len(id_collision_findings),
            "new_agent_value": "LOW",
            "agents": [],
        }

    # Path validation bugs
    path_findings = findings_by_category.get("path-validation", [])
    if len(path_findings) == 0:
        gaps["path-validation"] = {
            "status": "MISSING",
            "evidence": "No path validation issues found",
            "new_agent_value": "MEDIUM",
            "agents": ["io-validation"],
        }
    else:
        gaps["path-validation"] = {
            "status": "FOUND",
            "count": len(path_findings),
            "new_agent_value": "LOW",
            "agents": [],
        }

    return gaps


def summarize_modes(runs: list) -> dict:
    """Summarize findings by /uci mode."""
    mode_stats = defaultdict(
        lambda: {"runs": 0, "findings": 0, "agents_used": Counter(), "categories": Counter()}
    )

    for run in runs:
        mode = run.get("mode", "unknown")
        mode_stats[mode]["runs"] += 1
        mode_stats[mode]["findings"] += len(run.get("findings", []))

        for agent in run.get("agents", []):
            mode_stats[mode]["agents_used"][agent] += 1

        for finding in run.get("findings", []):
            category = BugCategory.classify(finding)
            if category:
                mode_stats[mode]["categories"][category.value] += 1

    # Convert Counters to dicts for JSON serialization
    return {
        mode: {
            "runs": stats["runs"],
            "total_findings": stats["findings"],
            "avg_findings_per_run": stats["findings"] / stats["runs"] if stats["runs"] > 0 else 0,
            "agents_used": dict(stats["agents_used"]),
            "categories_found": dict(stats["categories"]),
        }
        for mode, stats in mode_stats.items()
    }


def main():
    """Main analysis."""
    print("=" * 80)
    print("PHASE 0 VALIDATION: /UCI RUN ANALYSIS")
    print("=" * 80)
    print()

    # Load all /uci runs
    print("Loading /uci runs from P:\\\\\\.claude/state/uci/...")
    collector = UCIRunCollector(log_dir="P:\\\\\\.claude/state/uci")
    runs = collector.load_from_logs()

    if not runs:
        print("ERROR: No /uci runs found!")
        return

    print(f"Loaded {len(runs)} /uci runs")
    print()

    # Analyze bug categories
    print("ANALYSIS 1: Bug Categories Found")
    print("-" * 40)
    category_analysis = analyze_bug_categories(runs)
    print(f"Total findings classified: {category_analysis['total_findings']}")
    print()

    print("Findings by category:")
    for category, count in sorted(
        category_analysis["category_counts"].items(), key=lambda x: -x[1]
    ):
        severities = category_analysis["severity_by_category"].get(category, {})
        severity_str = ", ".join(
            [f"{s}:{c}" for s, c in sorted(severities.items(), key=lambda x: -x[1])]
        )
        print(f"  {category}: {count} findings ({severity_str})")

    print()

    # Detect gaps
    print("ANALYSIS 2: Potential Gaps (Would New Agents Add Value?)")
    print("-" * 40)
    gaps = detect_gaps(category_analysis["category_counts"], runs)

    for gap_type, gap_info in sorted(gaps.items()):
        if gap_info["status"] == "MISSING":
            print(f"❌ {gap_type.upper()}: NOT DETECTED")
            print(f"   Evidence: {gap_info['evidence']}")
            print(f"   New agent value: {gap_info['new_agent_value']}")
            print(f"   Relevant agents: {', '.join(gap_info['agents'])}")
        else:
            print(f"✅ {gap_type.upper()}: DETECTED ({gap_info['count']} findings)")
            print(f"   New agent value: {gap_info['new_agent_value']}")
        print()

    # Summarize by mode
    print("ANALYSIS 3: Findings by /UCI Mode")
    print("-" * 40)
    mode_summary = summarize_modes(runs)

    for mode, stats in sorted(mode_summary.items()):
        print(f"{mode.upper()} mode:")
        print(f"  Runs: {stats['runs']}")
        print(f"  Avg findings/run: {stats['avg_findings_per_run']:.1f}")
        print(
            f"  Categories found: {', '.join(stats['categories_found'].keys()) if stats['categories_found'] else 'None'}"
        )
        print()

    # Decision criteria
    print("=" * 80)
    print("PHASE 0 DECISION CRITERIA")
    print("=" * 80)
    print()

    missing_categories = sum(1 for g in gaps.values() if g["status"] == "MISSING")
    high_value_agents = sum(1 for g in gaps.values() if g["new_agent_value"] == "HIGH")

    print(f"Missing bug categories: {missing_categories}/4")
    print(f"High-value agent opportunities: {high_value_agents}")
    print()

    # Qualitative assessment (re-scoped from statistical <5% threshold)
    print("QUALITATIVE ASSESSMENT:")
    if missing_categories >= 3:
        print("→ SIGNIFICANT gaps detected - multi-lens adversarial approach LIKELY adds value")
        print("→ RECOMMENDATION: Proceed to Phase 0.5 (Prototype)")
    elif missing_categories >= 2:
        print("→ Moderate gaps detected - multi-lens adversarial approach MAY add value")
        print("→ RECOMMENDATION: Consider Phase 0.5 prototype before full commitment")
    else:
        print("→ Few gaps detected - current /uci agents may be sufficient")
        print("→ RECOMMENDATION: STOP implementation (reconsider approach)")
    print()

    print("=" * 80)
    print("LIMITATIONS (from validation_scope.md)")
    print("=" * 80)
    print("- Sample size: 9 runs (insufficient for statistical significance)")
    print("- Time span: 6 days (March 10-16, 2026)")
    print("- Qualitative insights only, not quantitative validation")
    print()


if __name__ == "__main__":
    main()
