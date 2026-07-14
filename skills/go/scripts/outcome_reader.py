"""Outcome correlation reader — read-only queries over the outcome index.

PURPOSE: Answer "what happened after acting?" — correlates discovery surfaces
with subsequent outcomes. Returns only facts + provenance. Never returns
recommendations or authoritative conclusions.

USAGE:
    from outcome_reader import query_by_surface, query_by_run

    results = query_by_surface(index, fingerprint="sha256:...")
    results = query_by_run(index, run_id="go-abc123")
    summary = get_outcome_summary(index)

All results are advisory. No mechanism reads outcome data to block, modify,
or authorize execution.
"""

from __future__ import annotations
from typing import Any

# ── query helpers ────────────────────────────────────────────────────────────


def _normalize_fingerprint(entry: dict) -> str:
    return str(entry.get("discovery_reference", {}).get("surface_fingerprint", "") or "")


def query_by_surface(
    index_entries: list[dict],
    surface_fingerprint: str = "",
) -> dict:
    """Find all runs with the given discovery surface fingerprint.

    Returns correlation facts: what outcomes occurred for this discovery surface.
    """
    if not surface_fingerprint:
        return {"correlated_runs": [], "count": 0}
    matched = [
        e for e in index_entries
        if _normalize_fingerprint(e) == surface_fingerprint
    ]
    return _build_correlation_result(matched)


def query_by_run(
    index_entries: list[dict],
    run_id: str = "",
) -> dict:
    """Find the correlation entry for a specific run_id."""
    if not run_id:
        return {"correlated_runs": [], "count": 0}
    matched = [e for e in index_entries if e.get("run_id") == run_id]
    return _build_correlation_result(matched)


def query_by_outcome(
    index_entries: list[dict],
    qa_verdict: str = "",
    completion_verdict: str = "",
    lifecycle_status: str = "",
) -> dict:
    """Find runs matching specific outcome filters. Any filter may be empty (skip)."""
    matched = []
    for e in index_entries:
        o = e.get("outcome_reference", {}) or {}
        if qa_verdict and str(o.get("qa_verdict", "")) != qa_verdict:
            continue
        if completion_verdict and str(o.get("completion_verdict", "")) != completion_verdict:
            continue
        if lifecycle_status and str(o.get("lifecycle_status", "")) != lifecycle_status:
            continue
        matched.append(e)
    return _build_correlation_result(matched)


def query_by_surface_with_redo(
    index_entries: list[dict],
    surface_fingerprint: str = "",
) -> dict:
    """Find runs with the given surface fingerprint that had redo outcomes."""
    by_surface = query_by_surface(index_entries, surface_fingerprint)
    redo = [r for r in by_surface["correlated_runs"]
            if r.get("outcome_reference", {}).get("qa_verdict") == "redo"]
    return _build_correlation_result(redo)


def _build_correlation_result(matched: list[dict]) -> dict:
    """Build a correlation result with facts + provenance + counts."""
    total = len(matched)
    qa_accept = sum(1 for e in matched if e.get("outcome_reference", {}).get("qa_verdict") in ("accept", "accept-with-concerns", ""))
    qa_redo = sum(1 for e in matched if e.get("outcome_reference", {}).get("qa_verdict") == "redo")
    qa_error = sum(1 for e in matched if e.get("outcome_reference", {}).get("qa_verdict") == "error")
    blocked = sum(1 for e in matched if e.get("outcome_reference", {}).get("lifecycle_status") == "blocked")
    completion_blocked = sum(1 for e in matched if e.get("outcome_reference", {}).get("completion_verdict") == "BLOCK")
    falsified = sum(1 for e in matched if e.get("outcome_reference", {}).get("falsification_result") == "FALSIFIED")

    surface_fingerprints = sorted({
        _normalize_fingerprint(e) for e in matched if _normalize_fingerprint(e)
    })

    return {
        "correlated_runs": [strip_internal(e) for e in matched],
        "count": total,
        "aggregates": {
            "qa_accept": qa_accept,
            "qa_redo": qa_redo,
            "qa_error": qa_error,
            "blocked": blocked,
            "completion_blocked": completion_blocked,
            "falsified": falsified,
        },
        "provenance": {
            "surface_fingerprints_present": len(surface_fingerprints),
            "surface_fingerprints": surface_fingerprints,
        },
    }


def strip_internal(entry: dict) -> dict:
    """Return a copy omitting internal fields.
    The caller explicitly adds internal fields as needed via build_options.
    By default, no internal metadata is returned to callers."""
    return {k: v for k, v in entry.items()
            if not k.startswith("_")}


def get_outcome_summary(index_entries: list[dict]) -> dict:
    """Aggregate summary of all outcomes across the index.

    Returns facts + provenance only. No recommendations.
    """
    total = len(index_entries)
    if total == 0:
        return {
            "total_runs": 0,
            "aggregates": {},
            "surface_count": 0,
        }
    qa_accept = sum(1 for e in index_entries if e.get("outcome_reference", {}).get("qa_verdict") in ("accept", "accept-with-concerns", ""))
    qa_redo = sum(1 for e in index_entries if e.get("outcome_reference", {}).get("qa_verdict") == "redo")
    qa_error = sum(1 for e in index_entries if e.get("outcome_reference", {}).get("qa_verdict") == "error")
    blocked = sum(1 for e in index_entries if e.get("outcome_reference", {}).get("lifecycle_status") == "blocked")
    completion_blocked = sum(1 for e in index_entries if e.get("outcome_reference", {}).get("completion_verdict") == "BLOCK")
    falsified = sum(1 for e in index_entries if e.get("outcome_reference", {}).get("falsification_result") == "FALSIFIED")

    surfaces = set()
    for e in index_entries:
        fp = _normalize_fingerprint(e)
        if fp:
            surfaces.add(fp)

    return {
        "total_runs": total,
        "aggregates": {
            "qa_accept": qa_accept,
            "qa_redo": qa_redo,
            "qa_error": qa_error,
            "blocked": blocked,
            "completion_blocked": completion_blocked,
            "falsified": falsified,
        },
        "surface_count": len(surfaces),
        "provenance": {
            "schema": "outcome-reader-aggregates.v1",
            "note": "aggregates reflect available state_dir verdict files; missing files cause gaps",
        },
    }


def get_discovery_evidence_for_runs_that_had_redo(
    index_entries: list[dict],
) -> list[dict]:
    """Return the discovery_reference block for every run that had qa_verdict=redo."""
    redo_runs = [
        e for e in index_entries
        if e.get("outcome_reference", {}).get("qa_verdict") == "redo"
    ]
    return [
        {"run_id": e["run_id"], "discovery": e.get("discovery_reference", {})}
        for e in redo_runs
    ]
