"""Lightweight derived index over completed discovery-evidence artifacts.

The index is a cache, rebuildable from go-runs artifacts. It stores enough
metadata to match prior runs to current proposals without loading every
artifact. None of this is authoritative — prior evidence accelerates discovery,
never replaces it. (Discovery Evidence Reuse Foundation, Phase 1.)
"""

from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from typing import Any

INDEX_VERSION = "discovery-index.v1"
INDEX_FILENAME = "discovery-index.json"
ARTIFACTS_ROOT_ENV = "GO_ARTIFACTS_ROOT"
ARTIFACTS_ROOT_DEFAULT = Path("P:/.claude/.artifacts")

_DISCOVERY_EVIDENCE_GLOB = "go-runs/*/*/discovery-evidence_*.json"


def _artifacts_root(ar=None) -> Path:
    if ar is not None:
        return Path(ar) if isinstance(ar, (str, Path)) else ar
    return Path(os.environ.get(ARTIFACTS_ROOT_ENV, str(ARTIFACTS_ROOT_DEFAULT)))


# ── helpers ──────────────────────────────────────────────────────────────────


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _now_utc_z() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── fingerprint & dependency hash ────────────────────────────────────────────


def compute_surface_fingerprint(
    rewritten_goal: str = "",
    surface_labels: list[str] | None = None,
    task_intent: str = "",
) -> str:
    """Deterministic SHA256 of the discovery surface a run explored.

    Matches on surface labels (semantic categories like "hook", "gate",
    "worktree") + normalized goal + intent. Two runs with the same fingerprint
    explored a similar discovery surface.
    """
    labels = sorted(surface_labels or [])
    return _hash(
        *labels,
        rewritten_goal.strip().lower(),
        task_intent.strip().lower(),
    )


def compute_dependency_hash(
    source_blob_hashes: list[str] | None = None,
    config_path_hashes: list[str] | None = None,
    repo_revision: str = "",
) -> str:
    """SHA256 of the dependency set the evidence rested on.

    source_blob_hashes: hashes of source files inspected during discovery.
    config_path_hashes: hashes of registration/config files consulted.
    repo_revision: git revision when discovery ran.

    If any dependency has changed, the prior evidence is stale and must be
    re-verified before use.
    """
    deps = sorted(source_blob_hashes or []) + sorted(config_path_hashes or [])
    return _hash(*deps, repo_revision.strip().lower())


# ── index entry helpers ──────────────────────────────────────────────────────


def _build_index_entry(
    discovery_path: Path,
    run_id: str,
    session_id: str,
    status: str,
    repository: str = "",
    base_revision: str = "",
    surface_fingerprint: str = "",
    dependency_hash: str = "",
    surface_labels: list[str] | None = None,
    finding_count: int = 0,
    structural_issue_count: int = 0,
    evidence_summary: str = "",
) -> dict:
    return {
        "index_version": INDEX_VERSION,
        "run_id": run_id,
        "session_id": session_id,
        "created_at": _now_utc_z(),
        "status": status,
        "repository": repository,
        "base_revision": base_revision,
        "surface_fingerprint": surface_fingerprint,
        "dependency_hash": dependency_hash,
        "surface_labels": sorted(surface_labels or []),
        "finding_count": finding_count,
        "structural_issue_count": structural_issue_count,
        "evidence_summary": evidence_summary[:500] if evidence_summary else "",
        "artifact_path": str(discovery_path.resolve()),
    }


def _entry_sort_key(e: dict) -> str:
    """Sort entries by run_id descending (newest first)."""
    return e.get("run_id", "")


# ── index read / write / prune / rebuild ─────────────────────────────────────


def load_index(index_path: Path) -> list[dict]:
    """Return index entries. Returns empty list if missing or malformed."""
    raw = _read_json(index_path)
    if not isinstance(raw, dict):
        return []
    entries = raw.get("entries", [])
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


def append_index_entry(index_path: Path, entry: dict) -> None:
    """Append one entry to the index file. Creates the file if absent."""
    current = load_index(index_path)
    current.append(entry)
    current.sort(key=_entry_sort_key, reverse=True)
    _write_index(index_path, current)


def _write_index(index_path: Path, entries: list[dict]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(index_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps({"version": INDEX_VERSION, "entries": entries}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(index_path)


def rebuild_index(
    artifacts_root: Path | None = None,
    index_path: Path | None = None,
) -> int:
    """Walk go-runs artifacts and rebuild the index from scratch.

    Returns entry count. This is the recovery path — the index is a cache.
    """
    root = _artifacts_root(artifacts_root)
    idx = index_path or root / INDEX_FILENAME
    entries: list[dict] = []

    # Walk go-runs/{session_id}/{run_id}/discovery-evidence_{run_id}.json
    for de_path in sorted(root.glob(_DISCOVERY_EVIDENCE_GLOB)):
        data = _read_json(de_path)
        if not isinstance(data, dict):
            continue
        findings = data.get("findings", [])
        if not isinstance(findings, list):
            continue
        run_id = str(data.get("run_id", de_path.stem.replace("discovery-evidence_", "")))

        # Derive session_id and run record from path structure
        # path: go-runs/{session_id}/{run_id}/discovery-evidence_{run_id}.json
        rel = de_path.relative_to(root)
        parts = rel.parts
        session_id = parts[1] if len(parts) >= 3 else ""
        derived_run_id = parts[2] if len(parts) >= 3 else run_id

        # Read run record for status and revision
        rr_path = root / "go-runs" / session_id / derived_run_id / "run-record.json"
        rr = _read_json(rr_path) if rr_path.is_file() else None
        status = str(rr.get("lifecycle_status", "")) if isinstance(rr, dict) else ""
        repository = str(rr.get("repository", "")) if isinstance(rr, dict) else ""
        base_revision = str(rr.get("base_revision", "")) if isinstance(rr, dict) else ""

        finding_count = len(findings)
        if finding_count == 0:
            continue
        si_count = sum(
            1 for f in findings
            if isinstance(f, dict) and isinstance(f.get("structural_issues"), list)
        )

        surface_labels = sorted({
            si
            for f in findings
            if isinstance(f, dict)
            for si in (f.get("structural_issues") or [])
        })

        entry = _build_index_entry(
            discovery_path=de_path,
            run_id=derived_run_id,
            session_id=session_id,
            status=status or "unknown",
            repository=repository,
            base_revision=base_revision,
            surface_labels=list(surface_labels),
            finding_count=finding_count,
            structural_issue_count=si_count,
        )
        entries.append(entry)

    entries.sort(key=_entry_sort_key, reverse=True)
    if entries:
        _write_index(idx, entries)
    return len(entries)


def prune_entry(index_path: Path, run_id: str) -> bool:
    """Remove the entry for a specific run_id. Returns True if removed."""
    current = load_index(index_path)
    before = len(current)
    current = [e for e in current if e.get("run_id") != run_id]
    if len(current) == before:
        return False
    _write_index(index_path, current)
    return True
