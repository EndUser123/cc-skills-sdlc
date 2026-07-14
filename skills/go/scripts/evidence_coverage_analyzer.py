"""Offline discovery telemetry analyzer -- aggregate stats from run telemetry.

Not on the /go hot path. Never blocks execution. Rebuildable.
Reads telemetry-discovery-evidence_*.jsonl from the artifacts root and
produces aggregate statistics about discovery coverage, surfaces encountered,
finding counts, and structural issue categories.

Usage:
    python evidence_coverage_analyzer.py [--artifacts-root PATH]
                                         [--output PATH]
                                         [--min-runs N]

Designed for offline use (not per-run). Output is advisory only.
"""

from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from typing import Any

ARTIFACTS_ROOT_ENV = "GO_ARTIFACTS_ROOT"
ARTIFACTS_ROOT_DEFAULT = Path("P:/.claude/.artifacts")
TELEMETRY_GLOB = "go-runs/*/*/telemetry-discovery-evidence_*.jsonl"
OUTPUT_FILENAME = "evidence-coverage-trends.json"
MIN_RUNS_DEFAULT = 1


def _artifacts_root(ar=None):
    if ar is not None:
        return Path(ar)
    return Path(os.environ.get(ARTIFACTS_ROOT_ENV, str(ARTIFACTS_ROOT_DEFAULT)))


def _read_jsonl(path):
    """Read JSONL file, return list of parsed entries."""
    results = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return results
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict):
                results.append(entry)
        except json.JSONDecodeError:
            pass
    return results


def collect_telemetry(artifacts_root):
    """Walk go-runs artifacts root and collect all telemetry records."""
    records = []
    for tel_path in sorted(artifacts_root.glob(TELEMETRY_GLOB)):
        records.extend(_read_jsonl(tel_path))
    return records


def compute_aggregates(records, min_runs=MIN_RUNS_DEFAULT):
    """Compute aggregate statistics from telemetry records."""
    if not records:
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runs_analyzed": 0,
            "evidence_reuse_rate": 0.0,
            "common_surfaces": [],
            "patterns": [],
        }

    total = len(records)
    runs_with_findings = sum(1 for r in records if r.get("exists"))
    runs_with_structural = sum(
        1 for r in records if r.get("structural_issue_count", 0) > 0
    )

    surface_map = {}
    for r in records:
        source = str(r.get("source", "unknown"))
        if "hook" in source.lower():
            surfaces = ["hook"]
        elif "gate" in source.lower():
            surfaces = ["gate"]
        elif "worktree" in source.lower():
            surfaces = ["worktree"]
        else:
            surfaces = ["general"]
        for s in surfaces:
            entry = surface_map.setdefault(s, {"runs": 0, "with_findings": 0})
            entry["runs"] += 1
            if r.get("exists"):
                entry["with_findings"] += 1

    common_surfaces = []
    for surface, counts in sorted(surface_map.items(), key=lambda x: -x[1]["runs"]):
        common_surfaces.append({
            "surface": surface,
            "runs": counts["runs"],
            "runs_with_findings": counts["with_findings"],
        })

    evidence_reuse_rate = runs_with_findings / total if total > 0 else 0.0

    patterns = []
    missing_count = sum(
        1 for r in records
        if r.get("writer_dropped_all")
        or (r.get("exists") and r.get("findings_count", 0) == 0)
    )
    writer_error_count = sum(1 for r in records if r.get("writer_error"))
    if missing_count > 0:
        patterns.append({
            "observation": "worker wrote empty or dropped-all-discovery evidence",
            "count": missing_count,
        })
    if writer_error_count > 0:
        patterns.append({
            "observation": "writer error detected during discovery evidence recording",
            "count": writer_error_count,
        })

    si_buckets = {}
    for r in records:
        si_count = r.get("structural_issue_count", 0)
        if si_count > 0:
            bucket = "1-2" if si_count <= 2 else "3-5" if si_count <= 5 else "6+"
            si_buckets[bucket] = si_buckets.get(bucket, 0) + 1

    if si_buckets:
        patterns.append({
            "observation": "structural issues by bucket count",
            "count": sum(si_buckets.values()),
            "buckets": si_buckets,
        })

    source_counts = {}
    for r in records:
        src = r.get("source", "absent")
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs_analyzed": total,
        "runs_with_findings": runs_with_findings,
        "runs_with_structural_issues": runs_with_structural,
        "evidence_writer_error_count": writer_error_count,
        "evidence_reuse_rate": round(evidence_reuse_rate, 4),
        "common_surfaces": common_surfaces,
        "patterns": patterns,
        "source_distribution": source_counts,
    }


def write_report(aggregates, output_path=None):
    """Write aggregate report to JSON file."""
    if output_path is None:
        output_path = _artifacts_root() / OUTPUT_FILENAME
    else:
        output_path = Path(output_path) if not isinstance(output_path, Path) else output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(aggregates, indent=2, default=str), encoding="utf-8")
    tmp.replace(output_path)
    return output_path


def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Offline discovery telemetry analyzer.")
    p.add_argument("--artifacts-root", default=None,
                    help=f"Artifacts root (default: ${ARTIFACTS_ROOT_ENV})")
    p.add_argument("--output", default=None,
                    help=f"Output path (default: <root>/{OUTPUT_FILENAME})")
    p.add_argument("--min-runs", type=int, default=MIN_RUNS_DEFAULT,
                    help="Minimum runs for surface in patterns")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    root = _artifacts_root(args.artifacts_root)
    records = collect_telemetry(root)
    aggregates = compute_aggregates(records, min_runs=args.min_runs)
    path = write_report(aggregates, args.output)
    print(f"Analyzed {len(records)} records from {root}")
    print(f"Written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
