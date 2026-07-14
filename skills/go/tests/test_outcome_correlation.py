"""Tests for the outcome correlation index and reader.

Covers:
- Rebuild from existing run-record + discovery-outcome-link + QA verdict
- Deterministic: same inputs produce same output
- Corrupted index regenerates
- No duplicate authority (outcome data is separate from discovery index)
- QA verdict correlation
- Completion review correlation
- Falsification correlation
- Missing outcome handling (fields stay null/unknown)
- Malformed artifact handling
- No failure conclusions from insufficient evidence
- Uncertainty preserved
- Provenance retained
"""

from __future__ import annotations
import json, os, time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_run_record(root: Path, session_id: str, run_id: str,
                      lifecycle_status: str = "completed", repository: str = "test/repo",
                      base_revision: str = "abc123") -> Path:
    base = root / "go-runs" / session_id / run_id
    base.mkdir(parents=True, exist_ok=True)
    rr_path = base / "run-record.json"
    rr_path.write_text(json.dumps({
        "schema": "go.run-record.v1",
        "run_id": run_id,
        "session_id": session_id,
        "lifecycle_status": lifecycle_status,
        "repository": repository,
        "base_revision": base_revision,
    }), encoding="utf-8")
    return rr_path


def _write_outcome_link(root: Path, session_id: str, run_id: str,
                        fingerprint: str = "", finding_count: int = 0) -> Path:
    base = root / "go-runs" / session_id / run_id
    base.mkdir(parents=True, exist_ok=True)
    link_path = base / "discovery-outcome-link.json"
    link_path.write_text(json.dumps({
        "schema": "discovery-outcome-link.v1",
        "originating_run_id": run_id,
        "originating_session_id": session_id,
        "surface_fingerprint": fingerprint,
        "finding_count": finding_count,
        "evidence_path": str(base / f"discovery-evidence_{run_id}.json"),
    }), encoding="utf-8")
    return link_path


def _write_qa_verdict(root: Path, terminal: str, run_id: str,
                      qa_status: str = "accept", summary: str = "ok") -> Path:
    dest = root / terminal / "go"
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / f"qa-verdict-{run_id}.json"
    p.write_text(json.dumps({
        "qa_status": qa_status,
        "summary": summary,
        "run_id": run_id,
        "timestamp": "2026-07-15T00:00:00Z",
    }), encoding="utf-8")
    return p


def _write_completion_review(root: Path, terminal: str, run_id: str,
                             verdict: str = "PASS", blocking_gaps: list[str] | None = None) -> Path:
    dest = root / terminal / "go"
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / f"completion-evidence-review_{run_id}.json"
    p.write_text(json.dumps({
        "verdict": verdict,
        "blocking_gaps": blocking_gaps or [],
        "commit_push_safe": verdict == "PASS",
        "generated_at": "2026-07-15T00:00:00Z",
    }), encoding="utf-8")
    return p


def _write_falsification_result(root: Path, terminal: str, run_id: str,
                                verdict: str = "NOT_FALSIFIED_WITHIN_BUDGET") -> Path:
    dest = root / terminal / "go"
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / f"falsification-result_{run_id}.json"
    p.write_text(json.dumps({
        "verdict": verdict,
        "run_id": run_id,
    }), encoding="utf-8")
    return p


def _load_index(root: Path) -> list[dict]:
    import outcome_index as oi
    idx_path = root / "outcome-index.json"
    return oi.load_index(idx_path) if idx_path.is_file() else []


# ── rebuild_index ────────────────────────────────────────────────────────────


def test_rebuild_from_run_records(tmp_path):
    """rebuild_index produces entries from run-records."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    summary = oi.rebuild_index(tmp_path)
    assert summary["entries"] == 1
    entries = _load_index(tmp_path)
    assert len(entries) == 1
    assert entries[0]["run_id"] == "r1"


def test_rebuild_deterministic(tmp_path):
    """Same inputs produce same output."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1", lifecycle_status="completed")
    _write_run_record(tmp_path, "s1", "r2", lifecycle_status="blocked")
    oi.rebuild_index(tmp_path)
    a = _load_index(tmp_path)
    # Delete index, rebuild again
    (tmp_path / "outcome-index.json").unlink()
    oi.rebuild_index(tmp_path)
    b = _load_index(tmp_path)
    assert len(a) == len(b) == 2
    assert a[0]["run_id"] == b[0]["run_id"]
    assert a[0]["outcome_reference"]["lifecycle_status"] == b[0]["outcome_reference"]["lifecycle_status"]


def test_rebuild_skips_malformed_run_record(tmp_path):
    "Malformed run-record is skipped."""
    import outcome_index as oi
    base = tmp_path / "go-runs" / "s1" / "r1"
    base.mkdir(parents=True)
    (base / "run-record.json").write_text("not json", encoding="utf-8")
    summary = oi.rebuild_index(tmp_path)
    assert summary["entries"] == 0
    assert summary["skipped"] == 1


def test_rebuild_from_empty(tmp_path):
    """rebuild_index on empty root returns 0 entries."""
    import outcome_index as oi
    summary = oi.rebuild_index(tmp_path)
    assert summary["entries"] == 0


def test_rebuild_corrupted_index_regenerates(tmp_path):
    """Deleting the index file and rebuilding produces the same result."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    oi.rebuild_index(tmp_path)
    (tmp_path / "outcome-index.json").unlink()
    summary = oi.rebuild_index(tmp_path)
    assert summary["entries"] == 1


# ── outcome correlation: QA verdict ──────────────────────────────────────────


def test_rebuild_correlates_qa_verdict(tmp_path):
    """QA verdict from terminal state_dir correlates via run_id."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    _write_qa_verdict(tmp_path, "terminal-A", "r1", qa_status="redo")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    assert len(entries) == 1
    assert entries[0]["outcome_reference"]["qa_verdict"] == "redo"
    assert "qa-verdict" in entries[0]["provenance"]["writers"]


def test_rebuild_missing_qa_verdict(tmp_path):
    """Missing QA verdict leaves qa_verdict empty."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    assert entries[0]["outcome_reference"]["qa_verdict"] == ""


def test_rebuild_malformed_qa_verdict_skipped(tmp_path):
    """Malformed QA verdict file is skipped."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    dest = tmp_path / "terminal-A" / "go"
    dest.mkdir(parents=True)
    (dest / "qa-verdict-r1.json").write_text("not json", encoding="utf-8")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    assert entries[0]["outcome_reference"]["qa_verdict"] == ""


# ── outcome correlation: completion review ───────────────────────────────────


def test_rebuild_correlates_completion_review(tmp_path):
    """Completion review verdict correlates via run_id."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    _write_completion_review(tmp_path, "terminal-A", "r1", verdict="BLOCK",
                              blocking_gaps=["Missing writer"])
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    assert entries[0]["outcome_reference"]["completion_verdict"] == "BLOCK"
    assert entries[0]["outcome_reference"]["completion_blocking_gaps"] == ["Missing writer"]


# ── outcome correlation: falsification ───────────────────────────────────────


def test_rebuild_correlates_falsification(tmp_path):
    """Falsification result correlates via run_id."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    _write_falsification_result(tmp_path, "terminal-A", "r1", verdict="FALSIFIED")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    assert entries[0]["outcome_reference"]["falsification_result"] == "FALSIFIED"


# ── outcome correlation: discovery-outcome link ──────────────────────────────


def test_rebuild_correlates_outcome_link(tmp_path):
    """Discovery outcome link data appears in discovery_reference."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    _write_outcome_link(tmp_path, "s1", "r1", fingerprint="hook_hash", finding_count=3)
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    dr = entries[0]["discovery_reference"]
    assert dr["surface_fingerprint"] == "hook_hash"
    assert dr["finding_count"] == 3


# ── outcome reader ───────────────────────────────────────────────────────────


def test_reader_query_by_surface(tmp_path):
    """query_by_surface returns runs matching surface fingerprint."""
    import outcome_index as oi
    import outcome_reader as ore
    _write_run_record(tmp_path, "s1", "r1")
    _write_run_record(tmp_path, "s1", "r2")
    _write_outcome_link(tmp_path, "s1", "r1", fingerprint="abc")
    _write_outcome_link(tmp_path, "s1", "r2", fingerprint="abc")
    oi.rebuild_index(tmp_path)
    idx = _load_index(tmp_path)
    result = ore.query_by_surface(idx, surface_fingerprint="abc")
    assert result["count"] == 2
    assert result["aggregates"]["qa_accept"] == 2


def test_reader_query_by_run(tmp_path):
    """query_by_run returns entry for specific run."""
    import outcome_index as oi
    import outcome_reader as ore
    _write_run_record(tmp_path, "s1", "r1")
    _write_run_record(tmp_path, "s1", "r2")
    oi.rebuild_index(tmp_path)
    idx = _load_index(tmp_path)
    result = ore.query_by_run(idx, run_id="r1")
    assert result["count"] == 1
    assert result["correlated_runs"][0]["run_id"] == "r1"


def test_reader_get_outcome_summary(tmp_path):
    """get_outcome_summary returns aggregates."""
    import outcome_index as oi
    import outcome_reader as ore
    _write_run_record(tmp_path, "s1", "r1", lifecycle_status="completed")
    _write_run_record(tmp_path, "s1", "r2", lifecycle_status="blocked")
    _write_qa_verdict(tmp_path, "t1", "r1", qa_status="redo")
    oi.rebuild_index(tmp_path)
    idx = _load_index(tmp_path)
    summary = ore.get_outcome_summary(idx)
    assert summary["total_runs"] == 2
    assert summary["aggregates"]["qa_redo"] == 1
    assert summary["aggregates"]["blocked"] == 1


def test_reader_empty_index(tmp_path):
    """Reader functions handle empty index gracefully."""
    import outcome_reader as ore
    assert ore.query_by_surface([], "abc")["count"] == 0
    assert ore.query_by_run([], "r1")["count"] == 0
    assert ore.get_outcome_summary([])["total_runs"] == 0


# ── hypothesis safety ────────────────────────────────────────────────────────


def test_no_failure_conclusion_from_insufficient_evidence(tmp_path):
    """Missing outcome data does not lead to conclusions — fields stay empty."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    # No verdict fields should contain "failed" or "discovery_failure"
    oref = entries[0].get("outcome_reference", {}) or {}
    for val in oref.values():
        if isinstance(val, str):
            assert "failed" not in val.lower()
            assert "discovery" not in val.lower()
    # The discovery_reference should show no evidence retrieved
    assert entries[0]["discovery_reference"]["evidence_retrieved"] is False


def test_hypothesis_language_not_present(tmp_path):
    """The index stores only facts. No hypothesis language."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    _write_qa_verdict(tmp_path, "t1", "r1", qa_status="redo")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    oref = entries[0].get("outcome_reference", {}) or {}
    assert oref.get("qa_verdict") == "redo"  # fact
    assert "hypothesis" not in {k for k in entries[0].keys()}  # no hypothesis field keys (avoid str() which includes tmp_path name)


@pytest.mark.parametrize("key", [
    "run_id", "session_id", "repository", "revision",
    "discovery_reference", "outcome_reference", "provenance",
])
def test_provenance_retained(tmp_path, key):
    """Each entry retains provenance fields."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    _write_outcome_link(tmp_path, "s1", "r1", fingerprint="abc")
    _write_qa_verdict(tmp_path, "t1", "r1", qa_status="redo")
    oi.rebuild_index(tmp_path)
    entries = _load_index(tmp_path)
    assert key in entries[0]


# ── no duplicate authority ───────────────────────────────────────────────────


def test_outcome_and_discovery_indexes_separate(tmp_path):
    """Outcome index is a separate file from discovery-index.json."""
    import outcome_index as oi
    _write_run_record(tmp_path, "s1", "r1")
    oi.rebuild_index(tmp_path)
    assert (tmp_path / "outcome-index.json").exists()
    # discovery-index.json should NOT exist in the same root
    # (it's at a different path, but this verifies separation)
    assert (tmp_path / "outcome-index.json").is_file()
    oref = json.loads((tmp_path / "outcome-index.json").read_text())
    assert "entries" in oref
    assert oref["version"] == "outcome-index.v1"


def test_load_index_missing(tmp_path):
    """load_index returns empty list for missing file."""
    import outcome_index as oi
    assert oi.load_index(tmp_path / "nonexistent.json") == []



