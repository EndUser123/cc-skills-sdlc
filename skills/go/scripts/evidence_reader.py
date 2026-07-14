"""Advisory evidence reader — prior discovery evidence for the current proposal.

Returns advisory matching entries from completed runs only. Active-run evidence
is invisible across sessions. Prior evidence accelerates discovery, never
replaces it. (Discovery Evidence Reuse Foundation, Phase 1 + Adaptive.)

Adaptive expansions (M-D):
- Surface similarity search: exact fingerprint first, then label overlap.
- Intent-aware retrieval: cross-intent evidence when useful.
"""

from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from typing import Any

INDEX_VERSION = "discovery-index.v1"
INDEX_FILENAME = "discovery-index.json"
ARTIFACTS_ROOT_ENV = "GO_ARTIFACTS_ROOT"
ARTIFACTS_ROOT_DEFAULT = Path("P:/.claude/.artifacts")

STALE_AGE_HOURS_DEFAULT = 72
_FRESHNESS_HISTORICAL = "historical_observation"
_FRESHNESS_CURRENT = "current_state_claim"

# How many shared surface labels trigger a similarity match.
SIMILARITY_MIN_LABELS_DEFAULT = 2

# Cross-intent relevance: which prior intents benefit which current intents.
# Key = current task_intent, value = set of prior intents to include.
_RELEVANT_INTENT_CROSSWALK: dict[str, set[str]] = {
    "investigate": {"implement", "validate"},
    "decide": {"implement", "investigate"},
    "validate": {"implement"},
    "mixed": {"implement", "investigate", "validate"},
}


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


# ── relevance scoring ─────────────────────────────────────────────────────────


def _compute_relevance_score(
    entry: dict,
    surface_labels: list[str],
    match_type: str,
    label_overlap_count: int = 0,
) -> float:
    """Compute a relevance score for a matching entry.

    Scoring:
      1.0  — exact surface fingerprint match
      0.9  — cross-intent with exact fingerprint match
      0.5–0.8 — surface similarity (proportional to label overlap)
      0.0  — no meaningful overlap
    """
    if match_type == "exact":
        return 1.0
    if match_type == "cross_intent_exact":
        return 0.9
    if match_type in ("similarity", "cross_intent_similarity"):
        stored = set(entry.get("surface_labels") or [])
        if not stored or not surface_labels:
            return 0.0
        max_possible = max(len(stored), len(surface_labels))
        if max_possible == 0:
            return 0.0
        base = label_overlap_count / max_possible
        # Penalize cross-intent matches
        if match_type == "cross_intent_similarity":
            base *= 0.85
        # Clamp to [0.5, 0.8] range for similarity matches
        return max(0.5, min(0.8, base))
    return 0.0


def _compute_overlap_count(entry: dict, surface_labels: list[str]) -> int:
    stored = set(entry.get("surface_labels") or [])
    query_set = set(surface_labels or [])
    return len(stored & query_set)


# ── matching helpers ──────────────────────────────────────────────────────────


def _is_completed(entry: dict) -> bool:
    status = (entry.get("status") or "").lower()
    return status in ("completed", "done", "pr_ready", "unknown")


def _label_overlap(entry: dict, surface_labels: list[str]) -> bool:
    stored = set(entry.get("surface_labels") or [])
    return bool(stored and surface_labels and stored & set(surface_labels))


def _intent_matches_for_retrieval(
    entry_intent: str, current_intent: str
) -> bool:
    """Check if a prior entry's intent is retrievable by the current intent."""
    if not current_intent or not entry_intent:
        return False
    if entry_intent == current_intent:
        return True
    relevant = _RELEVANT_INTENT_CROSSWALK.get(current_intent, set())
    return entry_intent in relevant


# ── query ────────────────────────────────────────────────────────────────────


def query(
    index: list[dict],
    surface_fingerprint: str = "",
    surface_labels: list[str] | None = None,
    repo_revision: str = "",
    current_dependency_hash: str = "",
    max_age_hours: int = STALE_AGE_HOURS_DEFAULT,
    limit: int = 5,
    task_intent: str = "",
    min_similarity_labels: int = SIMILARITY_MIN_LABELS_DEFAULT,
) -> dict:
    """Query the index for advisory prior evidence matching the current surface.

    Matching strategy (tiered, additive):
      1. Exact surface_fingerprint match (existing behavior).
      2. If results < limit, surface similarity: label overlap >= min_similarity_labels.
      3. If task_intent is set, intent-aware cross-pollination.

    All results are advisory-only, completed runs only.
    Each result carries relevance_score (0.0-1.0) and overlap_reason.

    Returns:
    {
      "prior_evidence": [...],
      "count": N,
      "advisory": true,
      "query_timestamp": "...",
      "match_strategy": "exact" | "similarity" | "mixed",
    }
    """
    surface_labels = surface_labels or []

    seen_ids: set[str] = set()
    exact_candidates: list[dict] = []
    similarity_candidates: list[dict] = []
    cross_intent_candidates: list[dict] = []

    for entry in index:
        run_id = entry.get("run_id", "")
        if not _is_completed(entry):
            continue

        entry_fingerprint = entry.get("surface_fingerprint", "")
        entry_intent = entry.get("task_intent", "")
        label_overlap_count = _compute_overlap_count(entry, surface_labels)
        freshened = {**entry, "_freshness": classify_freshness(
            entry,
            current_dependency_hash=current_dependency_hash,
            repo_revision=repo_revision,
            max_age_hours=max_age_hours,
        )}

        # Tier 1: exact fingerprint match
        if surface_fingerprint and entry_fingerprint == surface_fingerprint:
            freshened["relevance_score"] = _compute_relevance_score(
                entry, surface_labels, "exact"
            )
            freshened["overlap_reason"] = "exact surface fingerprint match"
            freshened["_match_type"] = "exact"
            exact_candidates.append(freshened)
            seen_ids.add(run_id)
            continue

        # Tier 2: surface similarity (label overlap >= threshold)
        if label_overlap_count >= min_similarity_labels and run_id not in seen_ids:
            freshened["relevance_score"] = _compute_relevance_score(
                entry, surface_labels, "similarity",
                label_overlap_count=label_overlap_count,
            )
            freshened["overlap_reason"] = (
                f"surface similarity: {label_overlap_count} shared labels"
            )
            freshened["_match_type"] = "similarity"
            similarity_candidates.append(freshened)
            seen_ids.add(run_id)
            continue

        # Tier 3: intent-aware cross-pollination
        if (task_intent
                and run_id not in seen_ids
                and _intent_matches_for_retrieval(entry_intent, task_intent)
                and label_overlap_count >= 1):
            is_exact = bool(surface_fingerprint) and entry_fingerprint == surface_fingerprint
            match_type = "cross_intent_exact" if is_exact else "cross_intent_similarity"
            freshened["relevance_score"] = _compute_relevance_score(
                entry, surface_labels, match_type,
                label_overlap_count=label_overlap_count,
            )
            intent_label = entry_intent or "unknown"
            freshened["overlap_reason"] = (
                f"cross-intent ({intent_label} -> {task_intent}): "
                f"{label_overlap_count} shared labels"
            )
            freshened["_match_type"] = match_type
            cross_intent_candidates.append(freshened)
            seen_ids.add(run_id)

    # Assemble: exact first, then similarity, then cross-intent
    _FRESH_ORDER = {"fresh": 3, "stale_clock": 2, "stale_dependency": 1}

    def _sort_key(e: dict) -> tuple:
        f = e.get("_freshness", {}).get("freshness", "")
        return (_FRESH_ORDER.get(f, 0), e.get("created_at", "") or "")

    for group in (exact_candidates, similarity_candidates, cross_intent_candidates):
        group.sort(key=_sort_key, reverse=True)

    combined = (exact_candidates + similarity_candidates + cross_intent_candidates)[:limit]

    # Determine match strategy description
    has_exact = len(exact_candidates) > 0
    has_similarity = len(similarity_candidates) > 0
    has_cross = len(cross_intent_candidates) > 0
    if has_exact and (has_similarity or has_cross):
        strategy = "mixed"
    elif has_exact:
        strategy = "exact"
    elif has_similarity:
        strategy = "similarity"
    else:
        strategy = "none"

    return {
        "prior_evidence": combined,
        "count": len(combined),
        "advisory": True,
        "query_timestamp": _now_utc_z(),
        "match_strategy": strategy,
    }


# ── cross-session policy ─────────────────────────────────────────────────────


def is_active_run(entry: dict) -> bool:
    """Active runs are invisible across sessions."""
    return (entry.get("status") or "").lower() == "active"


def filter_completed_only(entries: list[dict]) -> list[dict]:
    """Return only entries from completed/done/pr_ready runs."""
    return [e for e in entries if _is_completed(e)]
