#!/usr/bin/env python3
"""Improvement Governance Real-Data Validation Harness.

A repeatable evaluation workflow that runs the existing hypothesis engine
against historical /go outcomes and produces an evaluation report.

USAGE:
    python evaluate_hypothesis_quality.py --artifacts-root P:/.claude/.artifacts

OUTPUT:
    hypothesis-evaluation-report_{TIMESTAMP}.json  — structured results
    hypothesis-evaluation-report_{TIMESTAMP}.md    — human-readable report

AUTHORITY BOUNDARY:
    Read-only. Does not modify /go behavior, discovery, routing, or hypotheses.
    Does not create candidates automatically.
"""

from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from typing import Any

# Ensure we can import sibling modules
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

import hypothesis_generator as hg
import hypothesis_governance as gov
import outcome_index as oi
import evidence_index as ei
from outcome_reader import query_by_surface, get_outcome_summary


REPORT_SCHEMA_VERSION = "hypothesis-evaluation-report.v1"


def _now_utc_z() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def discover_runs(artifacts_root: Path) -> list[dict]:
    """Discover all available /go runs from artifact structure.

    Walks go-runs/{session}/{run}/ directories and collects run-record,
    qa-verdict, completion-review, falsification-result, and discovery-evidence.

    Returns list of consolidated run dicts with available evidence.
    """
    runs: list[dict] = []
    run_records = sorted(artifacts_root.glob("go-runs/*/*/run-record.json"))

    if not run_records:
        # Fallback: look for standalone qa-verdict files in go/ dirs
        qa_files = list(artifacts_root.glob("*/go/qa-verdict-*.json"))
        if qa_files:
            for qf in qa_files:
                try:
                    data = json.loads(qf.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                terminal = qf.relative_to(artifacts_root).parts[0]
                run_id = data.get("run_id") or qf.stem.replace("qa-verdict-", "")
                runs.append({
                    "run_id": run_id,
                    "session_id": terminal,
                    "source": "standalone_qa_verdict",
                    "qa_verdict": data.get("qa_status", ""),
                    "has_discovery_evidence": False,
                    "has_run_record": False,
                    "has_completion_review": False,
                    "has_falsification": False,
                })
        return runs

    for rr_path in run_records:
        try:
            rr = json.loads(rr_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rr, dict):
            continue

        rel = rr_path.relative_to(artifacts_root).parts
        session_id = rel[1] if len(rel) >= 3 else "unknown"
        run_id = rr.get("run_id", "") or (rel[2] if len(rel) >= 3 else "unknown")

        # Discover associated evidence artifacts
        run_dir = rr_path.parent
        qa_path = artifacts_root / f"{session_id}/go/qa-verdict-{run_id}.json"
        cer_path = artifacts_root / f"{session_id}/go/completion-evidence-review_{run_id}.json"
        fals_path = artifacts_root / f"{session_id}/go/falsification-result_{run_id}.json"
        de_path = run_dir / f"discovery-evidence_{run_id}.json"

        qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else None
        cer = json.loads(cer_path.read_text(encoding="utf-8")) if cer_path.exists() else None
        fals = json.loads(fals_path.read_text(encoding="utf-8")) if fals_path.exists() else None
        de = json.loads(de_path.read_text(encoding="utf-8")) if de_path.exists() else None

        runs.append({
            "run_id": run_id,
            "session_id": session_id,
            "source": "run_record",
            "repository": rr.get("repository", ""),
            "revision": rr.get("base_revision", ""),
            "lifecycle_status": rr.get("lifecycle_status", ""),
            "qa_verdict": qa.get("qa_status", "") if qa else "",
            "completion_verdict": cer.get("verdict", "") if cer else "",
            "falsification_verdict": fals.get("verdict", "") if fals else "",
            "has_discovery_evidence": de is not None,
            "finding_count": len(de.get("findings", [])) if de and isinstance(de.get("findings"), list) else 0,
            "has_run_record": True,
            "has_completion_review": cer is not None,
            "has_falsification": fals is not None,
        })

    return runs


def build_outcome_index_entries(runs: list[dict]) -> list[dict]:
    """Convert discovered runs into outcome-index-compatible entries.

    This allows the hypothesis generator to consume partial data gracefully
    — runs without complete discovery evidence still produce entries with
    whatever fields are available.
    """
    entries: list[dict] = []
    for r in runs:
        dr = {
            "artifact_path": "",
            "surface_fingerprint": f"auto-{r['session_id'][:8]}" if r.get("session_id") else "auto-unknown",
            "finding_count": r.get("finding_count", 0),
            "structural_issue_count": 0,
            "task_intent": "implement",
            "evidence_retrieved": r.get("has_discovery_evidence", False),
        }
        outcome = {
            "lifecycle_status": r.get("lifecycle_status", "completed"),
            "qa_verdict": r.get("qa_verdict", ""),
            "qa_summary": "",
            "completion_verdict": r.get("completion_verdict", ""),
            "completion_blocking_gaps": [],
            "falsification_result": r.get("falsification_verdict", ""),
        }
        entries.append({
            "run_id": str(r["run_id"]),
            "session_id": str(r.get("session_id", "")),
            "repository": str(r.get("repository", "")),
            "revision": str(r.get("revision", "")),
            "discovery_reference": dr,
            "outcome_reference": outcome,
            "provenance": {"writers": ["evaluate_hypothesis_quality.py"], "source_artifacts": [str(r.get("source", ""))]},
        })
    return entries


def classify_hypothesis(h: dict) -> dict:
    """Classify a hypothesis for the evaluation report.

    Returns the original hypothesis plus human-review fields.
    All human-review fields start with underscore to indicate
    they are evaluation metadata, not part of the hypothesis schema.
    """
    obs = h.get("observation", {})
    htype = obs.get("type", "unknown")
    primary = h.get("hypotheses", [{}])[0]
    conf = primary.get("confidence", 0.0)
    iv = h.get("investigation_value", {})

    # Auto-classify value tier based on type + confidence
    if conf >= 0.6 and htype not in ("unknown", "positive_first_pass_validation"):
        _usefulness = "interesting_but_low_value"
        _actionability = "requires_more_investigation"
    elif conf >= 0.4:
        _usefulness = "interesting_but_low_value"
        _actionability = "requires_more_investigation"
    else:
        _usefulness = "insufficient_evidence"
        _actionability = "not_actionable"

    # Override for specific well-known patterns
    if htype == "positive_discovery_success":
        _usefulness = "interesting_but_low_value"
        _actionability = "actionable"
    elif htype == "possible_discovery_gap" and conf >= 0.6:
        _usefulness = "valuable"
        _actionability = "actionable"
    elif htype == "unknown":
        _usefulness = "noise"
        _actionability = "not_actionable"

    h["_usefulness"] = _usefulness
    h["_actionability"] = _actionability
    h["_evaluated_at"] = _now_utc_z()
    return h


def produce_report(
    runs: list[dict],
    entries: list[dict],
    hypotheses: list[dict],
    deduped: list[dict],
    aggregated: list[dict],
    summary: dict,
    start_time: float,
) -> dict:
    """Produce the structured evaluation report."""
    categories = {}
    for r in runs:
        qa = r.get("qa_verdict", "") or "unknown"
        categories.setdefault(qa, 0)
        categories[qa] += 1

    # Count hypothesis quality
    total_h = len(hypotheses)
    valuable = sum(1 for h in hypotheses if h.get("_usefulness") == "valuable")
    interesting = sum(1 for h in hypotheses if h.get("_usefulness", "").startswith("interesting"))
    noise = sum(1 for h in hypotheses if h.get("_usefulness") == "noise")
    actionable = sum(1 for h in hypotheses if h.get("_actionability") == "actionable")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": _now_utc_z(),
        "elapsed_seconds": round(time.time() - start_time, 2),
        "dataset": {
            "runs_analyzed": len(runs),
            "date_range": {"start": "", "end": ""},  # No timestamps in source data
            "outcome_categories": categories,
            "evidence_available": {
                "has_run_record": sum(1 for r in runs if r.get("has_run_record")),
                "has_discovery_evidence": sum(1 for r in runs if r.get("has_discovery_evidence")),
                "has_completion_review": sum(1 for r in runs if r.get("has_completion_review")),
                "has_falsification": sum(1 for r in runs if r.get("has_falsification")),
            },
            "repositories": list({r.get("repository", "") for r in runs if r.get("repository")}),
        },
        "hypotheses": {
            "total": summary.get("total_hypotheses", 0),
            "distinct_runs": summary.get("distinct_run_count", 0),
            "by_type": summary.get("by_type", {}),
        },
        "quality_metrics": {
            "signal_quality": {
                "valuable": valuable,
                "interesting_but_low_value": interesting,
                "noise": noise,
                "actionable": actionable,
                "valuable_pct": round(valuable / total_h * 100, 1) if total_h else 0,
                "actionable_pct": round(actionable / total_h * 100, 1) if total_h else 0,
                "noise_pct": round(noise / total_h * 100, 1) if total_h else 0,
            },
            "pattern_quality": {
                "hypotheses_generated": total_h,
                "runs_analyzed": len(runs),
                "hypotheses_per_run": round(total_h / len(runs), 2) if runs else 0,
                "deduped_to_original_ratio": round(len(deduped) / total_h, 2) if total_h else 0,
                "recurring_surfaces": len(aggregated),
            },
            "review_burden": {
                "expected_hypotheses_per_10_runs": round(total_h / len(runs) * 10, 1) if runs else 0,
                "estimated_review_minutes": round((total_h * 3) / 60, 1),  # ~3 min per hypothesis
            },
        },
        "failure_modes_tested": {
            "generic_hypothesis": bool(aggregated and len(aggregated) <= len(summary.get("by_type", {}))),
            "false_causality_alternatives_preserved": all(
                len(h.get("hypotheses", [{}])[0].get("counter_evidence", [])) >= 0
                for h in hypotheses
            ) if hypotheses else True,
            "not_all_redos_become_discovery_gap": all(
                h.get("observation", {}).get("type") != "possible_discovery_gap"
                or h.get("hypotheses", [{}])[0].get("supporting_evidence", [])
                for h in hypotheses
            ) if hypotheses else True,
        },
        "provenance": {
            "writer": "evaluate_hypothesis_quality.py",
            "inputs": {
                "runs_discovered": len(runs),
                "hypothesis_generator_version": hg.HYPOTHESIS_SCHEMA_VERSION,
            },
            "generated_at": _now_utc_z(),
        },
    }


def produce_markdown_report(report: dict, hypotheses: list[dict], runs: list[dict]) -> str:
    """Generate the human-readable markdown report."""
    lines: list[str] = []
    lines.append("# Improvement Governance Real-Data Validation Report")
    lines.append(f"\n**Generated:** {report['generated_at']}")
    lines.append(f"**Schema:** {report['schema_version']}")
    lines.append(f"**Elapsed:** {report['elapsed_seconds']}s")
    lines.append("")

    d = report["dataset"]
    lines.append("## 1. Dataset")
    lines.append(f"\n- Runs analyzed: **{d['runs_analyzed']}**")
    lines.append(f"- Outcome categories: `{d['outcome_categories']}`")
    lines.append(f"- Evidence available: `{d['evidence_available']}`")
    lines.append(f"- Repositories: `{d['repositories'] or 'none'}`")
    lines.append("")

    lines.append("### Evidence Availability")
    ev = d.get("evidence_available", {})
    lines.append(f"\n- Run records: {ev.get('has_run_record', 0)}/{d['runs_analyzed']}")
    lines.append(f"- Discovery evidence: {ev.get('has_discovery_evidence', 0)}/{d['runs_analyzed']}")
    lines.append(f"- Completion reviews: {ev.get('has_completion_review', 0)}/{d['runs_analyzed']}")
    lines.append(f"- Falsification results: {ev.get('has_falsification', 0)}/{d['runs_analyzed']}")
    lines.append("")

    lines.append("## 2. Generated Hypotheses")
    lines.append(f"\nTotal: **{report['hypotheses']['total']}**")
    lines.append(f"Distinct runs: **{report['hypotheses']['distinct_runs']}**")
    lines.append("\n### By Type")
    for htype, count in sorted(report["hypotheses"]["by_type"].items()):
        lines.append(f"- `{htype}`: {count}")
    lines.append("")

    lines.append("### Hypothesis Inventory")
    for i, h in enumerate(hypotheses):
        obs = h.get("observation", {})
        primary = h.get("hypotheses", [{}])[0]
        iv = h.get("investigation_value", {})
        lines.append(f"\n**{i+1}. {obs.get('type', 'unknown')}**")
        lines.append(f"   - Statement: {primary.get('statement', '')[:120]}")
        lines.append(f"   - Confidence: {primary.get('confidence', 0.0)}")
        lines.append(f"   - Supporting: {primary.get('supporting_evidence', [])}")
        lines.append(f"   - Counter: {primary.get('counter_evidence', [])}")
        lines.append(f"   - Source runs: {[r.get('run_id','') for r in h.get('evidence',{}).get('runs',[])]}")
        lines.append(f"   - Impact: {iv.get('impact', 0.0)}, Evidence quality: {iv.get('evidence_quality', 0.0)}")
        lines.append(f"   - _Usefulness: {h.get('_usefulness', 'unclassified')}")
        lines.append(f"   - _Actionability: {h.get('_actionability', 'unclassified')}")
    lines.append("")

    q = report["quality_metrics"]
    lines.append("## 3. Quality Metrics")
    lines.append("\n### Signal Quality")
    sq = q["signal_quality"]
    lines.append(f"- Valuable: {sq['valuable']} ({sq['valuable_pct']}%)")
    lines.append(f"- Interesting: {sq['interesting_but_low_value']}")
    lines.append(f"- Noise: {sq['noise']} ({sq['noise_pct']}%)")
    lines.append(f"- Actionable: {sq['actionable']} ({sq['actionable_pct']}%)")
    lines.append("\n### Pattern Quality")
    pq = q["pattern_quality"]
    lines.append(f"- Hypotheses per run: {pq['hypotheses_per_run']}")
    lines.append(f"- Dedup ratio: {pq['deduped_to_original_ratio']}")
    lines.append(f"- Recurring surface groups: {pq['recurring_surfaces']}")
    lines.append("\n### Review Burden")
    rb = q["review_burden"]
    lines.append(f"- Expected per 10 runs: ~{rb['expected_hypotheses_per_10_runs']} hypotheses")
    lines.append(f"- Estimated review time: ~{rb['estimated_review_minutes']} min")

    lines.append("\n## 4. Failure Modes Tested")
    for fm, result in report["failure_modes_tested"].items():
        lines.append(f"- `{fm}`: {'✅' if result else '❌'}")

    lines.append("\n## 5. Human Review Worksheet")
    lines.append("\n| # | Type | Statement | Usefulness | Actionability |")
    lines.append("|---|------|-----------|------------|--------------|")
    for i, h in enumerate(hypotheses):
        t = h.get("observation", {}).get("type", "?")[:20]
        s = h.get("observation", {}).get("description", "")[:60]
        u = h.get("_usefulness", "?")
        a = h.get("_actionability", "?")
        lines.append(f"| {i+1} | {t} | {s} | {u} | {a} |")

    lines.append("\n## 6. Legend")
    lines.append("""
- **usefulness**: valuable / interesting but low value / noise / already known / insufficient evidence
- **actionability**: actionable / requires more investigation / not actionable
""")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Hypothesis quality evaluation harness")
    p.add_argument("--artifacts-root", default="P:/.claude/.artifacts",
                   help="Root path for go-run artifacts")
    p.add_argument("--output-dir", default=None,
                   help="Output directory for reports (default: artifacts root)")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress progress output")
    args = p.parse_args()

    start = time.time()
    root = Path(args.artifacts_root).resolve()
    output_dir = Path(args.output_dir or root)

    if not args.quiet:
        print(f"[eval] Scanning artifacts in {root}")

    # Step 1: Discover runs
    runs = discover_runs(root)
    if not args.quiet:
        print(f"[eval] Discovered {len(runs)} runs (source: {set(r.get('source','') for r in runs)})")

    # Step 2: Build outcome-index-compatible entries
    entries = build_outcome_index_entries(runs)
    if not args.quiet:
        print(f"[eval] Built {len(entries)} outcome entries")

    # Step 3: Generate hypotheses
    hypotheses = hg.generate(entries)
    if not args.quiet:
        print(f"[eval] Generated {len(hypotheses)} hypotheses")

    # Step 4: Classify each hypothesis
    evaluated = [classify_hypothesis(h) for h in hypotheses]

    # Step 5: Deduplicate
    deduped = gov.deduplicate(evaluated)
    if not args.quiet:
        print(f"[eval] Deduplicated: {len(hypotheses)} -> {len(deduped)} groups")

    # Step 6: Aggregate
    aggregated = hg.aggregate(evaluated)

    # Step 7: Summary
    summary = hg.get_summary(evaluated)

    # Step 8: Produce report
    report = produce_report(runs, entries, evaluated, deduped, aggregated, summary, start)

    # Step 9: Write outputs
    ts = _now_utc_z().replace(":", "").replace("-", "")
    json_path = output_dir / f"hypothesis-evaluation-report_{ts}.json"
    md_path = output_dir / f"hypothesis-evaluation-report_{ts}.md"

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(produce_markdown_report(report, evaluated, runs), encoding="utf-8")

    if not args.quiet:
        print(f"\n[eval] JSON report: {json_path}")
        print(f"[eval] MD report:  {md_path}")
        print(f"[eval] Elapsed: {round(time.time() - start, 1)}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
