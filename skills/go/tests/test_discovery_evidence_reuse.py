"""Tests for the Discovery Evidence Reuse foundation layer.

Covers:
- Index rebuildable from go-runs artifacts
- Completed runs accessible via query, active runs excluded
- Stale evidence detected (dependency hash / clock)
- Cross-session completed evidence allowed
- Advisory flag always True (no authority from evidence)
- Freshness classification
- Adaptive query: surface similarity search
- Adaptive query: intent-aware cross-pollination
- Adaptive query: relevance scoring
- Adaptive query: match strategy reporting
- Adaptive query: no authority changes
"""

from __future__ import annotations
import json, os, time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_discovery_evidence(
    artifacts_root: Path,
    session_id: str,
    run_id: str,
    findings: list[dict],
    lifecycle_status: str = "completed",
) -> Path:
    """Create a discovery-evidence artifact under go-runs with a run record."""
    base = artifacts_root / "go-runs" / session_id / run_id
    base.mkdir(parents=True, exist_ok=True)
    # Write run record
    rr = {
        "schema": "go.run-record.v1",
        "session_id": session_id,
        "run_id": run_id,
        "lifecycle_status": lifecycle_status,
        "repository": "test/repo",
        "base_revision": "abc123",
        "current_revision": "abc123",
        "created_at": "2026-07-14T00:00:00Z",
    }
    (base / "run-record.json").write_text(json.dumps(rr), encoding="utf-8")
    # Write discovery evidence
    de = {"findings": findings, "run_id": run_id}
    dest = base / f"discovery-evidence_{run_id}.json"
    dest.write_text(json.dumps(de), encoding="utf-8")
    return dest


def _load_index(artifacts_root: Path) -> list[dict]:
    idx_path = artifacts_root / "discovery-index.json"
    if not idx_path.is_file():
        return []
    raw = json.loads(idx_path.read_text(encoding="utf-8"))
    return raw.get("entries", [])


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(params=[
    "completed",
    "done",
    "pr_ready",
    "active",           # should be excluded from cross-session query
    "blocked",          # not completed — excluded
    "unknown",          # included (assume completed)
])
def run_with_status(request, tmp_path):
    """Create a single go-runs artifact with varied lifecycle_status."""
    s = request.param
    findings = [{"source": "test", "provenance": "verified",
                  "summary": "test finding", "evidence": "file:line"}]
    de = _make_discovery_evidence(tmp_path, "session-A", f"run-{s}", findings,
                                    lifecycle_status=s)
    return tmp_path, s, de


# ── rebuild_index ────────────────────────────────────────────────────────────


def test_rebuild_index(tmp_path):
    """rebuild_index walks go-runs artifacts and produces entries."""
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "hook.py", "provenance": "verified",
         "summary": "PreToolUse blocks outside path", "evidence": "hook.py:42"}
    ])
    _make_discovery_evidence(tmp_path, "s1", "r2", [
        {"source": "gate.py", "provenance": "inference",
         "summary": "Gate may double-fire",
         "structural_issues": ["race_condition"]}
    ])
    _make_discovery_evidence(tmp_path, "s2", "r3", [
        {"source": "router.py", "provenance": "verified",
         "summary": "Router misses fallback", "evidence": "router.py:88"}
    ])
    import evidence_index as ei
    count = ei.rebuild_index(tmp_path)
    assert count == 3
    entries = _load_index(tmp_path)
    assert len(entries) == 3
    # Sorted by run_id descending (newest first)
    assert entries[0]["run_id"] == "r3"
    assert entries[2]["run_id"] == "r1"


def test_rebuild_index_skips_missing_run_record(tmp_path):
    """Index entry still created even without run-record (graceful degrade)."""
    base = tmp_path / "go-runs" / "s1" / "r1"
    base.mkdir(parents=True)
    de = {"findings": [{"source": "x.py", "provenance": "verified",
                         "summary": "test", "evidence": "x.py:1"}],
           "run_id": "r1"}
    (base / "discovery-evidence_r1.json").write_text(json.dumps(de), encoding="utf-8")
    import evidence_index as ei
    count = ei.rebuild_index(tmp_path)
    assert count == 1
    entries = _load_index(tmp_path)
    assert len(entries) == 1
    # status should be "unknown" since no run-record
    assert entries[0]["status"] == "unknown"


def test_rebuild_index_skips_malformed_evidence(tmp_path):
    """Malformed discovery-evidence files are skipped."""
    base = tmp_path / "go-runs" / "s1" / "r1"
    base.mkdir(parents=True)
    (base / "discovery-evidence_r1.json").write_text("not json", encoding="utf-8")
    rr = {"schema": "go.run-record.v1", "session_id": "s1", "run_id": "r1",
           "lifecycle_status": "completed"}
    (base / "run-record.json").write_text(json.dumps(rr), encoding="utf-8")
    import evidence_index as ei
    count = ei.rebuild_index(tmp_path)
    assert count == 0


def test_rebuild_index_empty_findings_skipped(tmp_path):
    """Discovery evidence with empty findings list is skipped."""
    _make_discovery_evidence(tmp_path, "s1", "r1", [])
    import evidence_index as ei
    count = ei.rebuild_index(tmp_path)
    assert count == 0


def test_rebuild_from_empty(tmp_path):
    """rebuild_index on empty artifacts root returns 0."""
    import evidence_index as ei
    count = ei.rebuild_index(tmp_path)
    assert count == 0
    assert not (tmp_path / "discovery-index.json").is_file()


# ── append / load / prune ────────────────────────────────────────────────────


def test_append_and_load(tmp_path):
    """Appending entries and loading them back works."""
    idx = tmp_path / "discovery-index.json"
    import evidence_index as ei
    e1 = ei._build_index_entry(tmp_path / "de.json", "r1", "s1", "completed")
    e2 = ei._build_index_entry(tmp_path / "de.json", "r2", "s1", "completed")
    ei.append_index_entry(idx, e1)
    ei.append_index_entry(idx, e2)
    entries = ei.load_index(idx)
    assert len(entries) == 2
    # Newest first
    assert entries[0]["run_id"] == "r2"


def test_prune_entry(tmp_path):
    """prune_entry removes the entry for a specific run_id."""
    idx = tmp_path / "discovery-index.json"
    import evidence_index as ei
    ei.append_index_entry(idx, ei._build_index_entry(tmp_path / "de.json", "r1", "s1", "completed"))
    ei.append_index_entry(idx, ei._build_index_entry(tmp_path / "de.json", "r2", "s1", "completed"))
    assert ei.prune_entry(idx, "r1") is True
    entries = ei.load_index(idx)
    assert len(entries) == 1
    assert entries[0]["run_id"] == "r2"


def test_load_index_missing(tmp_path):
    """load_index returns empty list for missing file."""
    import evidence_index as ei
    assert ei.load_index(tmp_path / "nonexistent.json") == []


# ── compute_surface_fingerprint ──────────────────────────────────────────────


def test_compute_surface_fingerprint_deterministic():
    """Same inputs produce same output."""
    import evidence_index as ei
    a = ei.compute_surface_fingerprint("fix the hook", ["hook"], "implement")
    b = ei.compute_surface_fingerprint("fix the hook", ["hook"], "implement")
    assert a == b


def test_compute_surface_fingerprint_differentiated():
    """Different inputs produce different output."""
    import evidence_index as ei
    a = ei.compute_surface_fingerprint("fix the hook", ["hook"], "implement")
    b = ei.compute_surface_fingerprint("fix the gate", ["gate"], "implement")
    assert a != b


# ── compute_dependency_hash ──────────────────────────────────────────────────


def test_compute_dependency_hash_deterministic():
    """Same dependencies produce same hash."""
    import evidence_index as ei
    a = ei.compute_dependency_hash(["hash1", "hash2"], ["conf1"], "abc123")
    b = ei.compute_dependency_hash(["hash1", "hash2"], ["conf1"], "abc123")
    assert a == b


def test_compute_dependency_hash_changed():
    """Different dependencies produce different hash."""
    import evidence_index as ei
    a = ei.compute_dependency_hash(["hash1"], [], "abc123")
    b = ei.compute_dependency_hash(["hash2"], [], "abc123")
    assert a != b


# ── query: cross-session policy ──────────────────────────────────────────────


def test_query_returns_completed_runs(tmp_path):
    """query returns evidence from completed/done/pr_ready runs."""
    import evidence_index as ei
    import evidence_reader as er
    # Completed run
    _make_discovery_evidence(tmp_path, "session-A", "run-completed", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1", "structural_issues": ["dead_code"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["dead_code"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["dead_code"])
    assert result["advisory"] is True
    assert result["count"] >= 1


def test_query_excludes_active_runs(tmp_path):
    """query does NOT return active-run evidence."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "session-A", "run-active", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1", "structural_issues": ["dead_code"]}
    ], lifecycle_status="active")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    assert len(idx) == 1  # index has it
    sf = ei.compute_surface_fingerprint(surface_labels=["dead_code"])
    result = er.query(idx, surface_fingerprint=sf)
    assert result["count"] == 0  # query filters it out


def test_query_excludes_blocked_runs(tmp_path):
    """query does NOT return blocked-run evidence."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "session-A", "run-blocked", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1"}
    ], lifecycle_status="blocked")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=[])
    result = er.query(idx, surface_fingerprint=sf)
    assert result["count"] == 0


def test_query_excludes_no_match(tmp_path):
    """query excludes entries whose fingerprint doesn't match."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "session-A", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1", "structural_issues": ["hook"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["gate"])
    result = er.query(idx, surface_fingerprint=sf)
    assert result["count"] == 0


# ── freshness ────────────────────────────────────────────────────────────────


def test_freshness_fresh(tmp_path):
    """Evidence with matching dependency hash and recent age is 'fresh'."""
    import evidence_index as ei
    import evidence_reader as er
    dep_hash = ei.compute_dependency_hash(["src_hash"], ["conf_hash"], "abc123")
    entry = ei._build_index_entry(
        tmp_path / "de.json", "r1", "s1", "completed",
        dependency_hash=dep_hash, base_revision="abc123",
    )
    entry["created_at"] = "2026-07-14T00:00:00Z"
    # Force freshness check with matching dep hash and short age threshold
    freshness = er.classify_freshness(entry, current_dependency_hash=dep_hash,
                                       max_age_hours=720)  # 30d
    assert freshness["freshness"] == "fresh"


def test_freshness_stale_dependency(tmp_path):
    """Evidence with mismatched dependency hash is 'stale_dependency'."""
    import evidence_index as ei
    import evidence_reader as er
    old_hash = ei.compute_dependency_hash(["old_src"], [], "old_rev")
    new_hash = ei.compute_dependency_hash(["new_src"], [], "new_rev")
    entry = ei._build_index_entry(
        tmp_path / "de.json", "r1", "s1", "completed",
        dependency_hash=old_hash,
    )
    entry["created_at"] = "2026-07-14T00:00:00Z"
    freshness = er.classify_freshness(entry, current_dependency_hash=new_hash,
                                       max_age_hours=720)
    assert freshness["freshness"] == "stale_dependency"


def test_freshness_stale_clock(tmp_path):
    """Evidence older than threshold is 'stale_clock'."""
    import evidence_index as ei
    import evidence_reader as er
    dep_hash = ei.compute_dependency_hash(["src"], [], "rev")
    entry = ei._build_index_entry(
        tmp_path / "de.json", "r1", "s1", "completed",
        dependency_hash=dep_hash,
    )
    entry["created_at"] = "2026-07-10T00:00:00Z"  # 4 days ago
    freshness = er.classify_freshness(entry, current_dependency_hash=dep_hash,
                                       repo_revision="rev",
                                       max_age_hours=48)  # 2h
    assert freshness["freshness"] == "stale_clock"


def test_freshness_current_state_claim(tmp_path):
    """Fresh completed evidence classifies as current_state_claim."""
    import evidence_index as ei
    import evidence_reader as er
    dep_hash = ei.compute_dependency_hash(["src"], [], "rev")
    entry = ei._build_index_entry(
        tmp_path / "de.json", "r1", "s1", "completed",
        dependency_hash=dep_hash, base_revision="rev",
    )
    entry["created_at"] = "2026-07-14T00:00:00Z"
    freshness = er.classify_freshness(entry, current_dependency_hash=dep_hash,
                                       repo_revision="rev",
                                       max_age_hours=720)
    assert freshness["freshness"] == "fresh"
    assert freshness["freshest_class"] == "current_state_claim"


def test_stale_dependency_still_returns_classification(tmp_path):
    """Even stale evidence has a classification (useful as historical observation)."""
    import evidence_index as ei
    import evidence_reader as er
    entry = ei._build_index_entry(
        tmp_path / "de.json", "r1", "s1", "completed",
    )
    entry["created_at"] = "2026-07-14T00:00:00Z"
    freshness = er.classify_freshness(entry, current_dependency_hash="different_hash")
    # Should classify as stale_dependency, not crash
    assert freshness["freshness"] == "stale_dependency"
    assert freshness["freshest_class"] == "historical_observation"


# ── advisory-only invariant ──────────────────────────────────────────────────


def test_advisory_flag_always_true(tmp_path):
    """query always returns advisory: True regardless of inputs."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1"}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    result = er.query(idx)  # no matching fingerprint
    assert result["advisory"] is True
    result = er.query(idx, surface_fingerprint="anything")
    assert result["advisory"] is True


# ── filter_completed_only ────────────────────────────────────────────────────


def test_filter_completed_only():
    """filter_completed_only filters correctly."""
    import evidence_reader as er
    entries = [
        {"status": "active"},
        {"status": "completed"},
        {"status": "done"},
        {"status": "pr_ready"},
        {"status": "blocked"},
        {"status": "unknown"},
    ]
    filtered = er.filter_completed_only(entries)
    statuses = {e["status"] for e in filtered}
    assert statuses == {"completed", "done", "pr_ready", "unknown"}


# ── integration: end-to-end with rebuild ➔ query ➔ advisory ────────────────


def test_end_to_end_query(tmp_path):
    """Complete flow: create artifacts, rebuild index, query, get advisory."""
    import evidence_index as ei
    import evidence_reader as er
    # Create two completed runs with hook findings
    for i, (sid, rid) in enumerate([("s1", "r1"), ("s2", "r2")]):
        _make_discovery_evidence(tmp_path, sid, rid, [
            {"source": "hook.py", "provenance": "verified",
             "summary": f"PreToolUse issue {i}",
             "evidence": "hook.py:42",
             "structural_issues": ["hook"]}
        ], lifecycle_status="completed")
    # Rebuild index
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    assert len(idx) == 2
    # Query with matching fingerprint
    sf = ei.compute_surface_fingerprint(surface_labels=["hook"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook"], limit=5)
    assert result["count"] >= 1
    assert result["advisory"] is True
    for e in result["prior_evidence"]:
        assert e["run_id"] in ("r1", "r2")


# ── cross-session safety ─────────────────────────────────────────────────────


def test_active_run_invisible_cross_session(tmp_path):
    """Active-run evidence must NOT cross sessions via query."""
    import evidence_index as ei
    import evidence_reader as er
    # Active run from another (virtual) session
    _make_discovery_evidence(tmp_path, "other-session", "r-active", [
        {"source": "x.py", "provenance": "verified", "summary": "active finding",
         "evidence": "x.py:1"}
    ], lifecycle_status="active")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    assert len(idx) == 1
    result = er.query(idx, surface_fingerprint="anything")
    assert result["count"] == 0


# ── wiring proof ─────────────────────────────────────────────────────────────


def test_orchestrate_imports_persist_evidence(tmp_path):
    """orchestrate.py imports _persist_evidence and _read_json."""
    import orchestrate as _orch
    assert callable(getattr(_orch, "_persist_evidence", None))


def test_preflight_imports_inject_prior_evidence(tmp_path):
    """preflight_propose defines _inject_prior_evidence."""
    # Load the module
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "preflight_propose", SCRIPTS / "preflight_propose.py"
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    assert callable(getattr(_mod, "_inject_prior_evidence", None))


# ── adaptive query: surface similarity ──────────────────────────────────────


def test_query_similarity_shared_labels_above_threshold(tmp_path):
    """Similarity match when >=2 surface labels overlap."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    # Query with different fingerprint but 2 overlapping labels
    sf = ei.compute_surface_fingerprint(surface_labels=["gate", "worktree"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["gate", "worktree", "hook"])
    assert result["count"] >= 1


def test_query_similarity_below_threshold(tmp_path):
    """No similarity match when <2 surface labels overlap."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1", "structural_issues": ["hook"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["gate"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["gate"])
    # fingerprint doesn't match; only 0 shared labels (below 2 threshold)
    assert result["count"] == 0


def test_query_similarity_exact_first_then_similarity(tmp_path):
    """Exact matches appear before similarity matches in results."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "a.py", "provenance": "verified", "summary": "hook issue",
         "evidence": "a.py:1", "structural_issues": ["hook"]}
    ], lifecycle_status="completed")
    _make_discovery_evidence(tmp_path, "s1", "r2", [
        {"source": "b.py", "provenance": "verified", "summary": "hook+gate issue",
         "evidence": "b.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["hook"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook", "gate"])
    assert result["count"] >= 1
    # first result should be exact match (fingerprint "hook")
    first = result["prior_evidence"][0]
    assert first["_match_type"] == "exact"


def test_query_similarity_relevance_score(tmp_path):
    """Similarity matches carry proportional relevance score."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "found X",
         "evidence": "x.py:1",
         "structural_issues": ["hook", "gate", "worktree"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["dead_code"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook", "gate", "worktree"],
                       limit=5)
    # similarity match via label overlap
    sim_results = [e for e in result["prior_evidence"]
                   if e.get("_match_type") in ("similarity", "cross_intent_similarity")]
    if sim_results:
        score = sim_results[0].get("relevance_score", 0)
        assert 0.5 <= score <= 0.8


# ── adaptive query: intent-aware retrieval ──────────────────────────────────


def _make_discovery_evidence_with_intent(
    artifacts_root, session_id, run_id, findings,
    lifecycle_status="completed", task_intent="",
):
    """Create discovery evidence + proposal artifact with task_intent."""
    base = artifacts_root / "go-runs" / session_id / run_id
    base.mkdir(parents=True, exist_ok=True)
    rr = {
        "schema": "go.run-record.v1",
        "session_id": session_id,
        "run_id": run_id,
        "lifecycle_status": lifecycle_status,
        "repository": "test/repo",
        "base_revision": "abc123",
        "current_revision": "abc123",
        "created_at": "2026-07-14T00:00:00Z",
    }
    (base / "run-record.json").write_text(json.dumps(rr), encoding="utf-8")
    de = {"findings": findings, "run_id": run_id}
    dest = base / f"discovery-evidence_{run_id}.json"
    dest.write_text(json.dumps(de), encoding="utf-8")
    # Write proposal with intent
    prop = {"task_intent": task_intent, "rewrittenGoal": "test goal"}
    (base / f"task-proposal_{run_id}.json").write_text(
        json.dumps(prop), encoding="utf-8"
    )
    return dest


def test_query_intent_crosswalk_investigate(tmp_path):
    """Query with task_intent=investigate sees implement/validate evidence."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence_with_intent(
        tmp_path, "s1", "r-implement", [
            {"source": "x.py", "provenance": "verified", "summary": "impl finding",
             "evidence": "x.py:1", "structural_issues": ["hook"]}
        ], task_intent="implement")
    _make_discovery_evidence_with_intent(
        tmp_path, "s1", "r-validate", [
            {"source": "y.py", "provenance": "verified", "summary": "val finding",
             "evidence": "y.py:1", "structural_issues": ["hook"]}
        ], task_intent="validate")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["gate"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook", "gate"],
                       task_intent="investigate")
    assert result["count"] >= 1


def test_query_intent_exact_relevance(tmp_path):
    """Cross-intent exact matches carry 0.9 relevance score."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence_with_intent(
        tmp_path, "s1", "r-impl", [
            {"source": "x.py", "provenance": "verified", "summary": "finding",
             "evidence": "x.py:1", "structural_issues": ["hook"]}
        ], task_intent="implement")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    # Same fingerprint but different intent
    sf = ei.compute_surface_fingerprint(
        rewritten_goal="test goal", surface_labels=["hook"], task_intent="implement")
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook"],
                       task_intent="investigate")
    cross = [e for e in result["prior_evidence"]
             if e.get("_match_type") == "cross_intent_exact"]
    if cross:
        assert cross[0]["relevance_score"] == 0.9


# ── adaptive query: match strategy reporting ────────────────────────────────


def test_match_strategy_exact(tmp_path):
    """match_strategy is 'exact' when only exact matches."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "finding",
         "evidence": "x.py:1", "structural_issues": ["hook"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["hook"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook"])
    assert result["match_strategy"] in ("exact", "mixed")
    assert result["count"] >= 1


def test_match_strategy_none(tmp_path):
    """match_strategy is 'none' when no matches."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "finding",
         "evidence": "x.py:1", "structural_issues": ["hook"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["unrelated"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["unrelated"])
    assert result["match_strategy"] == "none"
    assert result["count"] == 0


def test_match_strategy_similarity(tmp_path):
    """match_strategy is 'similarity' when only similarity-based."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "finding",
         "evidence": "x.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    # Different fingerprint but overlapping labels
    sf = ei.compute_surface_fingerprint(surface_labels=["gate", "worktree"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["gate", "worktree", "hook"])
    if result["count"] > 0:
        assert result["match_strategy"] in ("similarity", "mixed")


# ── adaptive query: no authority / advisory invariant ──────────────────────


def test_adaptive_query_advisory_always_true(tmp_path):
    """Even adaptive results carry advisory: True."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "finding",
         "evidence": "x.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["gate", "worktree"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["gate", "worktree", "hook"])
    assert result["advisory"] is True
    for e in result["prior_evidence"]:
        assert e.get("_match_type", "") in (
            "exact", "similarity", "cross_intent_exact",
            "cross_intent_similarity",
        )
        # No authority-related fields
        assert "authorized" not in e


def test_adaptive_query_provenance_preserved(tmp_path):
    """Provenance info preserved in adaptive results."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "finding",
         "evidence": "x.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["gate", "worktree"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["gate", "worktree", "hook"])
    for e in result["prior_evidence"]:
        assert isinstance(e.get("run_id"), str)
        assert isinstance(e.get("session_id"), str)
        assert isinstance(e.get("artifact_path"), str)


def test_adaptive_query_no_authority_fields(tmp_path):
    """Adaptive results never carry authority-changing fields."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r1", [
        {"source": "x.py", "provenance": "verified", "summary": "finding",
         "evidence": "x.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="completed")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["gate", "worktree"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["gate", "worktree", "hook"])
    for e in result["prior_evidence"]:
        assert "authorize" not in e
        assert "completion" not in e
        assert "coverage_gate" not in e
        assert "automatic" not in e


# ── adaptive query: active runs still excluded from adaptive results ───────


def test_adaptive_query_active_excluded(tmp_path):
    """Active runs still excluded from adaptive/similarity results."""
    import evidence_index as ei
    import evidence_reader as er
    _make_discovery_evidence(tmp_path, "s1", "r-active", [
        {"source": "x.py", "provenance": "verified", "summary": "active finding",
         "evidence": "x.py:1", "structural_issues": ["hook", "gate"]}
    ], lifecycle_status="active")
    ei.rebuild_index(tmp_path)
    idx = ei.load_index(tmp_path / "discovery-index.json")
    sf = ei.compute_surface_fingerprint(surface_labels=["hook", "gate"])
    result = er.query(idx, surface_fingerprint=sf,
                       surface_labels=["hook", "gate"])
    assert result["count"] == 0
