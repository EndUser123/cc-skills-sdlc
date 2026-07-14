"""Outcome correlation index — rebuildable cache joining discovery evidence to run outcomes.

PURPOSE: "What happened after acting?" — correlates discovery evidence (what we knew
before acting) with objective run outcomes. Lives parallel to discovery-index.json;
the two are joined by run_id.

DOMAIN SEPARATION (load-bearing invariant):
  discovery-index.json  -> authoritative for discovery facts
  outcome-index.json    -> authoritative for outcome facts
Neither becomes authority over behavior.

ARTIFACT LOCATIONS:
  go-runs:     go-runs/{session}/{run}/run-record.json
               go-runs/{session}/{run}/discovery-outcome-link.json
  state_dir:   {artifacts_root}/{TERMINAL}/go/qa-verdict-{run}.json
               {artifacts_root}/{TERMINAL}/go/completion-evidence-review_{run}.json
               {artifacts_root}/{TERMINAL}/go/falsification-result_{run}.json
Join key: run_id.

FAILURE BEHAVIOR (fail-soft, never blocks):
  missing outcome artifact   -> no correlation
  malformed artifact         -> skipped with diagnostic
  incomplete evidence        -> unknown
"""

from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any

INDEX_VERSION = "outcome-index.v1"
INDEX_FILENAME = "outcome-index.json"
ARTIFACTS_ROOT_ENV = "GO_ARTIFACTS_ROOT"
ARTIFACTS_ROOT_DEFAULT = Path("P:/.claude/.artifacts")

_RUN_RECORD_GLOB = "go-runs/*/*/run-record.json"
_OUTCOME_LINK_GLOB = "go-runs/*/*/discovery-outcome-link.json"
_QA_VERDICT_GLOB = "*/go/qa-verdict-*.json"
_COMPLETION_REVIEW_GLOB = "*/go/completion-evidence-review_*.json"
_FALSIFICATION_GLOB = "*/go/falsification-result_*.json"


def _artifacts_root(ar=None) -> Path:
    if ar is not None:
        return Path(ar) if isinstance(ar, (str, Path)) else ar
    return Path(os.environ.get(ARTIFACTS_ROOT_ENV, str(ARTIFACTS_ROOT_DEFAULT)))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _now_utc_z() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run_id_from_qa_path(path: Path) -> str:
    return path.stem[len("qa-verdict-"):] if path.stem.startswith("qa-verdict-") else path.stem


def _run_id_from_completion_path(path: Path) -> str:
    return path.stem[len("completion-evidence-review_"):] if path.stem.startswith("completion-evidence-review_") else path.stem


def _run_id_from_falsification_path(path: Path) -> str:
    return path.stem[len("falsification-result_"):] if path.stem.startswith("falsification-result_") else path.stem


def _collect_qa_verdicts(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(root.glob(_QA_VERDICT_GLOB)):
        data = _read_json(p)
        if not isinstance(data, dict):
            continue
        rid = str(data.get("run_id") or _run_id_from_qa_path(p))
        out[rid] = data
    return out


def _collect_completion_reviews(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(root.glob(_COMPLETION_REVIEW_GLOB)):
        data = _read_json(p)
        if not isinstance(data, dict):
            continue
        rid = str(data.get("run_id") or _run_id_from_completion_path(p))
        out[rid] = data
    return out


def _collect_falsification_results(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(root.glob(_FALSIFICATION_GLOB)):
        data = _read_json(p)
        if not isinstance(data, dict):
            continue
        rid = str(data.get("run_id") or _run_id_from_falsification_path(p))
        out[rid] = data
    return out


def _collect_outcome_links(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(root.glob(_OUTCOME_LINK_GLOB)):
        data = _read_json(p)
        if not isinstance(data, dict):
            continue
        rid = str(data.get("originating_run_id") or "")
        if not rid:
            parts = p.relative_to(root).parts
            rid = parts[2] if len(parts) >= 3 else p.stem
        out[rid] = data
    return out


def _build_entry(
    run_id: str, session_id: str,
    run_record: dict | None, link: dict | None,
    qa: dict | None, completion: dict | None, falsification: dict | None,
    source_artifacts: list[str],
) -> dict:
    rr = run_record or {}
    lk = link or {}
    discovery_ref = {
        "artifact_path": str(lk.get("evidence_path", "")),
        "surface_fingerprint": str(lk.get("surface_fingerprint", "")),
        "finding_count": int(lk.get("finding_count", 0) or 0),
        "structural_issue_count": int(lk.get("structural_issue_count", 0) or 0),
        "task_intent": str(lk.get("task_intent", "")),
        "evidence_retrieved": bool(lk.get("evidence_path", "")),
    }
    outcome_ref = {
        "lifecycle_status": str(rr.get("lifecycle_status", "") or "unknown"),
        "qa_verdict": str(qa.get("qa_status", "") or "") if qa else "",
        "qa_summary": str(qa.get("summary", "") or "") if qa else "",
        "completion_verdict": str(completion.get("verdict", "") or "") if completion else "",
        "completion_blocking_gaps": list(completion.get("blocking_gaps", []) or []) if completion else [],
        "falsification_result": str(falsification.get("verdict", "") or "") if falsification else "",
    }
    writers: list[str] = []
    if run_record is not None: writers.append("run-record.json")
    if link is not None: writers.append("discovery-outcome-link.json")
    if qa is not None: writers.append("qa-verdict")
    if completion is not None: writers.append("completion-evidence-review")
    if falsification is not None: writers.append("falsification-result")
    return {
        "schema_version": "1",
        "run_id": run_id,
        "session_id": session_id,
        "repository": str(rr.get("repository", "") or ""),
        "revision": str(rr.get("base_revision", "") or ""),
        "discovery_reference": discovery_ref,
        "outcome_reference": outcome_ref,
        "generated_at": _now_utc_z(),
        "provenance": {"writers": writers, "source_artifacts": source_artifacts},
    }


def load_index(index_path: Path) -> list[dict]:
    raw = _read_json(index_path)
    if not isinstance(raw, dict):
        return []
    entries = raw.get("entries", [])
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _write_index(index_path: Path, entries: list[dict]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(index_path.suffix + ".tmp")
    tmp.write_text(json.dumps({"version": INDEX_VERSION, "entries": entries}, indent=2), encoding="utf-8")
    tmp.replace(index_path)


def rebuild_index(artifacts_root: Path | None = None, index_path: Path | None = None) -> dict:
    """Walk source artifacts and rebuild the outcome correlation index.
    Returns summary dict {entries, skipped, diagnostics, ...}. Idempotent."""
    root = _artifacts_root(artifacts_root)
    idx = index_path or root / INDEX_FILENAME
    qa_map = _collect_qa_verdicts(root)
    completion_map = _collect_completion_reviews(root)
    falsification_map = _collect_falsification_results(root)
    link_map = _collect_outcome_links(root)
    entries: list[dict] = []
    skipped = 0
    diagnostics: list[str] = []
    for rr_path in sorted(root.glob(_RUN_RECORD_GLOB)):
        rr = _read_json(rr_path)
        if not isinstance(rr, dict):
            skipped += 1; diagnostics.append(f"malformed run-record: {rr_path}")
            continue
        run_id = str(rr.get("run_id", ""))
        if not run_id:
            parts = rr_path.relative_to(root).parts; run_id = parts[2] if len(parts) >= 3 else rr_path.stem
        session_id = str(rr.get("session_id", ""))
        if not session_id:
            parts = rr_path.relative_to(root).parts; session_id = parts[1] if len(parts) >= 3 else ""
        link = link_map.get(run_id)
        qa = qa_map.get(run_id)
        completion = completion_map.get(run_id)
        falsification = falsification_map.get(run_id)
        sa = [str(rr_path)]
        if link: sa.append(str(link.get("evidence_path", "")))
        entries.append(_build_entry(run_id, session_id, rr, link, qa, completion, falsification, sa))
    entries.sort(key=lambda e: e.get("run_id", ""), reverse=True)
    if entries:
        _write_index(idx, entries)
    return {
        "entries": len(entries), "skipped": skipped, "diagnostics": diagnostics,
        "qa_verdicts_found": len(qa_map), "completion_reviews_found": len(completion_map),
        "falsification_results_found": len(falsification_map), "outcome_links_found": len(link_map),
    }


def prune_entry(index_path: Path, run_id: str) -> bool:
    current = load_index(index_path)
    before = len(current)
    current = [e for e in current if e.get("run_id") != run_id]
    if len(current) == before:
        return False
    _write_index(index_path, current); return True
