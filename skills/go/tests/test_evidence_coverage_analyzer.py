"""Tests for the offline discovery telemetry analyzer.

Covers:
- Zero telemetry files → empty aggregate
- One file → correct aggregation
- Many files → multi-run aggregation
- Malformed entries → skipped gracefully
- Surface grouping by source field
- Pattern detection (missing evidence, writer errors)
- Deterministic output (same inputs → same output)
"""

from __future__ import annotations
import json, os
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_telemetry(
    root: Path,
    session_id: str,
    run_id: str,
    records: list[dict],
) -> Path:
    """Write a telemetry JSONL file under go-runs."""
    base = root / "go-runs" / session_id / run_id
    base.mkdir(parents=True, exist_ok=True)
    dest = base / f"telemetry-discovery-evidence_{run_id}.jsonl"
    with open(dest, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return dest


# ── zero telemetry ───────────────────────────────────────────────────────────


def test_analyzer_no_telemetry_files(tmp_path):
    """Zero telemetry files returns runs_analyzed=0."""
    import evidence_coverage_analyzer as ca
    records = ca.collect_telemetry(tmp_path)
    assert records == []
    agg = ca.compute_aggregates(records)
    assert agg["runs_analyzed"] == 0
    assert agg["evidence_reuse_rate"] == 0.0
    assert agg["common_surfaces"] == []


def test_analyzer_empty_root_no_crash(tmp_path):
    """Empty artifacts root doesn't crash."""
    import evidence_coverage_analyzer as ca
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    assert agg["generated_at"] != ""


# ── single file ──────────────────────────────────────────────────────────────


def test_analyzer_single_record(tmp_path):
    """Single telemetry record produces correct counts."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": True, "findings_count": 3, "structural_issue_count": 1,
         "source": "hook.py"},
    ])
    records = ca.collect_telemetry(tmp_path)
    assert len(records) == 1
    agg = ca.compute_aggregates(records)
    assert agg["runs_analyzed"] == 1
    assert agg["runs_with_findings"] == 1
    assert agg["runs_with_structural_issues"] == 1


def test_analyzer_no_findings(tmp_path):
    """Record with exists=False has 0 findings."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": False, "findings_count": 0, "source": "gate.py"},
    ])
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    assert agg["runs_analyzed"] == 1
    assert agg["runs_with_findings"] == 0


# ── many files ───────────────────────────────────────────────────────────────


def test_analyzer_multi_run_aggregation(tmp_path):
    """Multiple runs aggregate correctly."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": True, "findings_count": 3, "structural_issue_count": 0,
         "source": "hook_checker.py"},
    ])
    _write_telemetry(tmp_path, "s1", "r2", [
        {"exists": False, "findings_count": 0, "structural_issue_count": 0,
         "source": "router.py"},
    ])
    _write_telemetry(tmp_path, "s2", "r3", [
        {"exists": True, "findings_count": 5, "structural_issue_count": 2,
         "source": "gate_validator.py"},
    ])
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    assert agg["runs_analyzed"] == 3
    assert agg["runs_with_findings"] == 2
    assert agg["runs_with_structural_issues"] == 1
    assert agg["evidence_reuse_rate"] == pytest.approx(0.6667, abs=0.001)


# ── malformed entries ────────────────────────────────────────────────────────


def test_analyzer_malformed_jsonl_skipped(tmp_path):
    """Malformed JSONL lines are skipped."""
    import evidence_coverage_analyzer as ca
    base = tmp_path / "go-runs" / "s1" / "r1"
    base.mkdir(parents=True)
    dest = base / "telemetry-discovery-evidence_r1.jsonl"
    with open(dest, "w", encoding="utf-8") as f:
        f.write('{"exists": true, "source": "good"}\n')
        f.write("not json\n")
        f.write('{"exists": false}\n')
    records = ca.collect_telemetry(tmp_path)
    assert len(records) == 2  # malformed line skipped


def test_analyzer_non_dict_jsonl_skipped(tmp_path):
    """JSONL lines that parse as non-dict are skipped."""
    import evidence_coverage_analyzer as ca
    base = tmp_path / "go-runs" / "s1" / "r1"
    base.mkdir(parents=True)
    dest = base / "telemetry-discovery-evidence_r1.jsonl"
    with open(dest, "w", encoding="utf-8") as f:
        f.write("[1, 2, 3]\n");
        f.write('{"exists": true, "source": "ok"}\n')
    records = ca.collect_telemetry(tmp_path)
    assert len(records) == 1


def test_analyzer_empty_file_no_crash(tmp_path):
    """Empty telemetry file produces no records."""
    import evidence_coverage_analyzer as ca
    base = tmp_path / "go-runs" / "s1" / "r1"
    base.mkdir(parents=True)
    dest = base / "telemetry-discovery-evidence_r1.jsonl"
    dest.write_text("", encoding="utf-8")
    records = ca.collect_telemetry(tmp_path)
    assert records == []


# ── surface grouping ─────────────────────────────────────────────────────────


def test_analyzer_surface_grouping(tmp_path):
    """Surface types are grouped correctly by source keyword."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": True, "source": "hook_checker.py"},
    ])
    _write_telemetry(tmp_path, "s1", "r2", [
        {"exists": True, "source": "gate_runner.py"},
    ])
    _write_telemetry(tmp_path, "s1", "r3", [
        {"exists": True, "source": "worktree_manager.py"},
    ])
    _write_telemetry(tmp_path, "s1", "r4", [
        {"exists": True, "source": "something_random.py"},
    ])
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    surfaces = {s["surface"] for s in agg["common_surfaces"]}
    assert "hook" in surfaces
    assert "gate" in surfaces
    assert "worktree" in surfaces
    assert "general" in surfaces


# ── pattern detection ────────────────────────────────────────────────────────


def test_analyzer_pattern_writer_dropped(tmp_path):
    """Pattern detection for writer_dropped_all."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": True, "findings_count": 0,
         "writer_dropped_all": True, "source": "hook.py"},
    ])
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    pattern_names = [p["observation"] for p in agg["patterns"]]
    assert any("dropped-all" in n for n in pattern_names)


def test_analyzer_pattern_writer_error(tmp_path):
    """Pattern detection for writer_error."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": False, "writer_error": True, "source": "gate.py"},
    ])
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    pattern_names = [p["observation"] for p in agg["patterns"]]
    assert any("writer error" in n.lower() for n in pattern_names)


def test_analyzer_structural_issue_buckets(tmp_path):
    """Structural issue bucket pattern is detected."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": True, "findings_count": 3,
         "structural_issue_count": 4, "source": "hook.py"},
    ])
    agg = ca.compute_aggregates(ca.collect_telemetry(tmp_path))
    bucket_patterns = [p for p in agg["patterns"]
                       if "structural issues" in p.get("observation", "").lower()]
    assert len(bucket_patterns) >= 1
    if bucket_patterns:
        assert "buckets" in bucket_patterns[0]


# ── deterministic ────────────────────────────────────────────────────────────


def test_analyzer_deterministic_same_inputs(tmp_path):
    """Same inputs produce same output."""
    import evidence_coverage_analyzer as ca
    _write_telemetry(tmp_path, "s1", "r1", [
        {"exists": True, "findings_count": 3, "structural_issue_count": 1,
         "source": "hook.py"},
    ])
    _write_telemetry(tmp_path, "s1", "r2", [
        {"exists": False, "findings_count": 0, "source": "gate.py"},
    ])
    records = ca.collect_telemetry(tmp_path)
    a = ca.compute_aggregates(records)
    b = ca.compute_aggregates(records)
    # Structural fields should match (timestamp will differ)
    assert a["runs_analyzed"] == b["runs_analyzed"]
    assert a["runs_with_findings"] == b["runs_with_findings"]
    assert a["evidence_reuse_rate"] == b["evidence_reuse_rate"]
    assert a["common_surfaces"] == b["common_surfaces"]


# ── CLI smoke ────────────────────────────────────────────────────────────────


def test_analyzer_cli_no_crash(tmp_path):
    """CLI entrypoint (main) doesn't crash with empty root."""
    import evidence_coverage_analyzer as ca
    rc = ca.main(["--artifacts-root", str(tmp_path), "--output",
                   str(tmp_path / "out.json")])
    assert rc == 0
    out = tmp_path / "out.json"
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["runs_analyzed"] == 0
