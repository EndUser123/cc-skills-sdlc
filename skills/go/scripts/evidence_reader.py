"""Advisory evidence reader — prior discovery evidence for the current proposal.

Returns advisory matching entries from completed runs only. Active-run evidence
is invisible across sessions. Prior evidence accelerates discovery, never
replaces it. (Discovery Evidence Reuse Foundation, Phase 1.)
"""

from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from typing import Any

INDEX_VERSION = "discovery-index.v1"
INDEX_FILENAME = "discovery-index.json"
ARTIFACTS_ROOT_ENV = "GO_ARTIFACTS_ROOT"
ARTIFACTS_ROOT_DEFAULT = Path("P:/.claude/.artifacts")

STALE_AGE_HOURS_DEFAULT = 72  # evidence older than this is "stale_clock"
_FRESHNESS_HISTORICAL = "historical_observation"
_FRESHNESS_CURRENT = "current_state_claim"
_FRESHNESS_CLASSES = (_FRESHNESS_HISTORICAL, _FRESHNESS_CURRENT)


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


def _parse_iso_z(s: str) -> float:
    """Best-effort parse of ISO-8601 timestamp to epoch seconds."""
    import datetime as _dt
    try:
        # Handle Z suffix and +00:00
        cleaned = s.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(cleaned)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


# ── freshness classification ─────────────────────────────────────────────────


def classify_freshness(
    entry: dict,
    current_dependency_hash: str = "",
    repo_revision: str = "",
    max_age_hours: int = STALE_AGE_HOURS_DEFAULT,
) -> dict:
    """Classify prior evidence freshness for an index entry.

    Returns a dict with:
      freshness: "fresh" | "stale_dependency" | "stale_clock"
      freshest_class: "historical_observation" | "current_state_claim"
      reason: human-readable explanation

    Historical observation evidence is *always* useful as a starting point,
    even when stale — it tells the worker what was found before and where to
    look. Current-state claims need stronger freshness.

    Fresh means: dependency hash matches AND age < max_age_hours.
    stale_dependency means: dependency set has changed (source/config/revision).
    stale_clock means: dependency hash matches but evidence is older than threshold.
    """
    age_hours = _entry_age_hours(entry)
    dep_match = _dependency_matches(entry, current_dependency_hash, repo_revision)

    if dep_match and age_hours < max_age_hours:
        freshness = "fresh"
    elif not dep_match:
        freshness = "stale_dependency"
    else:
        freshness = "stale_clock"

    freshest_class = _FRESHNESS_HISTORICAL
    if freshness == "fresh" and entry.get("status") in ("completed", "pr_ready"):
        freshest_class = _FRESHNESS_CURRENT

    return {
        "freshness": freshness,
        "freshest_class": freshest_class,
        "reason": _freshness_reason(freshness, dep_match, age_hours, max_age_hours),
    }


def _entry_age_hours(entry: dict) -> float:
    created = str(entry.get("created_at", ""))
    epoch = _parse_iso_z(created)
    if epoch <= 0:
        return float("inf")
    now = time.time()
    return (now - epoch) / 3600.0


def _dependency_matches(
    entry: dict,
    current_dependency_hash: str,
    repo_revision: str,
) -> bool:
    if current_dependency_hash:
        stored = entry.get("dependency_hash", "")
        return bool(stored) and stored == current_dependency_hash
    # No current hash provided — fall back to revision comparison
    stored_rev = entry.get("base_revision", "")
    return bool(stored_rev) and bool(repo_revision) and stored_rev == repo_revision


def _freshness_reason(
    freshness: str, dep_match: bool, age_hours: float, max_age: int
) -> str:
    if freshness == "fresh":
        return f"Evidence is {age_hours:.1f}h old, dependency hash matches."
    if freshness == "stale_dependency":
        return (
            "Dependency hash does not match current state — "
            "source files, config, or repo revision have changed."
        )
    return (
        f"Dependency hash matches but evidence is {age_hours:.1f}h old "
        f"(threshold: {max_age}h)."
    )


# ── query ────────────────────────────────────────────────────────────────────


def query(
    index: list[dict],
    surface_fingerprint: str = "",
    surface_labels: list[str] | None = None,
    repo_revision: str = "",
    current_dependency_hash: str = "",
    max_age_hours: int = STALE_AGE_HOURS_DEFAULT,
    limit: int = 5,
) -> dict:
    """Query the index for advisory prior evidence matching the current surface.

    Returns a dict:
    {
      "prior_evidence": [...],           # matched entries, sorted freshness desc
      "count": N,
      "advisory": true,
    }

    Rules enforced:
    - Only completed/done/pr_ready runs are returned (active runs invisible).
    - Surface fingerprint is preferred but not required — a fallback scan over
      surface_label overlap is used when fingerprint is empty.
    - Each entry includes a freshness classification.
    - The result is always advisory (advisory: true).
    """
    surface_labels = surface_labels or []

    candidates: list[dict] = []
    for entry in index:
        if not _is_completed(entry):
            continue
        if surface_fingerprint and entry.get("surface_fingerprint") != surface_fingerprint:
            # Fallback: check label overlap
            if not _label_overlap(entry, surface_labels):
                continue

        freshness = classify_freshness(
            entry,
            current_dependency_hash=current_dependency_hash,
            repo_revision=repo_revision,
            max_age_hours=max_age_hours,
        )
        candidates.append({**entry, "_freshness": freshness})

    # Sort: fresh first, then by age (newest)
    _FRESH_ORDER = {"fresh": 3, "stale_clock": 2, "stale_dependency": 1}

    def _sort_key(e: dict) -> tuple:
        f = e.get("_freshness", {}).get("freshness", "")
        return (_FRESH_ORDER.get(f, 0), e.get("created_at", "") or "")

    candidates.sort(key=_sort_key, reverse=True)
    candidates = candidates[:limit]

    return {
        "prior_evidence": candidates,
        "count": len(candidates),
        "advisory": True,
        "query_timestamp": _now_utc_z(),
    }


def _is_completed(entry: dict) -> bool:
    status = (entry.get("status") or "").lower()
    return status in ("completed", "done", "pr_ready", "unknown")


def _label_overlap(entry: dict, surface_labels: list[str]) -> bool:
    stored = set(entry.get("surface_labels") or [])
    return bool(stored and surface_labels and stored & set(surface_labels))


# ── cross-session policy ─────────────────────────────────────────────────────


def is_active_run(entry: dict) -> bool:
    """Active runs are invisible across sessions."""
    return (entry.get("status") or "").lower() == "active"


def filter_completed_only(entries: list[dict]) -> list[dict]:
    """Return only entries from completed/done/pr_ready runs."""
    return [e for e in entries if _is_completed(e)]
