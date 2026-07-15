"""Improvement governance layer — lifecycle, dedup, aging, candidate bridge.

PURPOSE: Govern improvement hypotheses WITHOUT autonomous self-modification.
Extends hypothesis_generator with lifecycle management (GENERATED -> UNDER_REVIEW
-> ACCEPTED/REJECTED/...), deduplication, aging, and bridge to improvement-candidate
contract. No function here can block, modify, or authorize execution.
"""

from __future__ import annotations
import datetime as _dt
from typing import Any

import hypothesis_generator as _hg

ALLOWED_STATUSES = _hg.ALLOWED_STATUSES
STALE_AGE_DAYS_DEFAULT = _hg.STALE_AGE_DAYS_DEFAULT


def _now_utc_z() -> str:
    return _hg._now_utc_z()


# -- lifecycle management ------------------------------------------------------


def set_status(hypothesis: dict, new_status: str, reason: str = "") -> dict:
    if new_status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}. Allowed: {sorted(ALLOWED_STATUSES)}"
        )
    hypothesis["status"] = new_status
    history = hypothesis.setdefault("status_history", [])
    history.append({"status": new_status, "changed_at": _now_utc_z(), "reason": reason or ""})
    return hypothesis


def get_by_status(hypotheses: list[dict], status: str) -> list[dict]:
    return [h for h in hypotheses if h.get("status") == status]


# -- deduplication -------------------------------------------------------------


def deduplicate(hypotheses: list[dict]) -> list[dict]:
    if not hypotheses:
        return []

    groups: dict[str, dict] = {}
    for h in hypotheses:
        group_key = h.get("dedup_group", "") or h.get("hypothesis_id", "")
        if group_key not in groups:
            groups[group_key] = {**h, "_merged_count": 1}
            continue

        existing = groups[group_key]
        existing["_merged_count"] = existing.get("_merged_count", 0) + 1

        existing_runs = existing.get("evidence", {}).get("runs", [])
        incoming_runs = h.get("evidence", {}).get("runs", [])
        existing_run_ids = {r.get("run_id") for r in existing_runs}
        for r in incoming_runs:
            if r.get("run_id") not in existing_run_ids:
                existing_runs.append(r)

        existing.setdefault("evidence", {}).setdefault("discovery_artifacts", [])
        for a in h.get("evidence", {}).get("discovery_artifacts", []):
            if a and a not in existing["evidence"]["discovery_artifacts"]:
                existing["evidence"]["discovery_artifacts"].append(a)

        existing.setdefault("evidence", {}).setdefault("outcome_artifacts", [])
        for a in h.get("evidence", {}).get("outcome_artifacts", []):
            if a and a not in existing["evidence"]["outcome_artifacts"]:
                existing["evidence"]["outcome_artifacts"].append(a)

        for inc_h in h.get("hypotheses", []):
            existing_h = existing.get("hypotheses", [])
            if not any(eh.get("statement") == inc_h.get("statement") for eh in existing_h):
                existing_h.append(inc_h)

        existing_gen = existing.get("generated_at", "")
        inc_gen = h.get("generated_at", "")
        if inc_gen and inc_gen < existing_gen:
            existing["generated_at"] = inc_gen
        inc_obs = h.get("last_observed_at", "")
        if inc_obs and inc_obs > existing.get("last_observed_at", ""):
            existing["last_observed_at"] = inc_obs
        existing["observation_count"] = existing.get("_merged_count", 0)

    result = []
    for g in groups.values():
        g.pop("_merged_count", None)
        g.setdefault("observation", {})["run_count"] = g.get("observation_count", 1)
        result.append(g)
    return result


# -- aging / staleness ---------------------------------------------------------


def _age_seconds(last_seen: str) -> float | None:
    if not last_seen:
        return None
    try:
        cleaned = last_seen.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(cleaned)
        return (_dt.datetime.now(_dt.timezone.utc) - dt).total_seconds()
    except (ValueError, TypeError):
        return None


def age_hypotheses(hypotheses: list[dict], max_age_days: int = STALE_AGE_DAYS_DEFAULT) -> list[dict]:
    threshold_sec = max_age_days * 86400
    for h in hypotheses:
        status = h.get("status", "")
        if status not in ("GENERATED", "UNDER_REVIEW"):
            continue
        last_seen = h.get("last_observed_at", "") or h.get("generated_at", "")
        age = _age_seconds(last_seen)
        if age is None:
            continue
        if age > threshold_sec:
            set_status(h, "STALE", reason=f"auto-stale after {max_age_days}d without review")
    return hypotheses


def get_stale(hypotheses: list[dict], max_age_days: int = STALE_AGE_DAYS_DEFAULT) -> list[dict]:
    threshold_sec = max_age_days * 86400
    stale: list[dict] = []
    for h in hypotheses:
        status = h.get("status", "")
        if status not in ("GENERATED", "UNDER_REVIEW"):
            continue
        last_seen = h.get("last_observed_at", "") or h.get("generated_at", "")
        age = _age_seconds(last_seen)
        if age is None:
            continue
        if age > threshold_sec:
            stale.append(h)
    return stale


# -- hypothesis-to-candidate bridge --------------------------------------------


def promote_to_candidate(hypothesis: dict, source_skill: str = "go") -> dict:
    now = _now_utc_z()
    obs = hypothesis.get("observation", {})
    evidence_block = hypothesis.get("evidence", {})
    hyp_list = hypothesis.get("hypotheses", [{}])
    primary = hyp_list[0] if hyp_list else {}
    inv = hypothesis.get("investigation_value", {})
    hyp_type = obs.get("type", "unknown")
    hyp_id = hypothesis.get("hypothesis_id", "unknown")

    evidence_citations: list[str] = []
    for r in evidence_block.get("runs", []):
        rid = r.get("run_id", "")
        fp = r.get("surface_fingerprint", "")
        qa = r.get("qa_verdict", "")
        if rid and fp:
            evidence_citations.append(f"run {rid}, surface {fp}, qa={qa}" if qa else f"run {rid}, surface {fp}")
    for a in evidence_block.get("discovery_artifacts", []):
        if a:
            evidence_citations.append(f"discovery: {a}")
    for a in evidence_block.get("outcome_artifacts", []):
        if a:
            evidence_citations.append(f"outcome: {a}")
    if not evidence_citations:
        evidence_citations = [hypothesis.get("generated_at", "") or now]

    local_slug = _now_utc_z()[:19].replace(":", "").replace("-", "")[:64]
    candidate_id = f"IC-GO-hyp-{local_slug}"

    cv = primary.get("confidence", 0.0)
    conf_str = "high" if cv >= 0.7 else ("medium" if cv >= 0.4 else "low")
    impact = inv.get("impact", 0.0)
    risk = "medium" if impact >= 0.8 else "low"

    hs = hypothesis.get("status", "GENERATED")
    if hs == "ACCEPTED":
        rs = "accepted_for_backlog"
    elif hs in ("REJECTED", "DUPLICATE", "INSUFFICIENT_EVIDENCE", "ALREADY_SOLVED", "STALE"):
        rs = "rejected"
    else:
        rs = "proposed"

    return {
        "candidate_id": candidate_id,
        "created_at": now,
        "source_skill": source_skill,
        "source_session_or_run_id": None,
        "observed_problem": obs.get("description", ""),
        "evidence": evidence_citations,
        "evidence_tier": _hg._confidence_to_tier(cv),
        "frequency": f"{obs.get('run_count', 1)} occurrence(s)",
        "affected_layer": "prompt_only",
        "target_skill_or_system": "go",
        "candidate_type": _hg._hypothesis_type_to_candidate_type(hyp_type),
        "proposed_change": f"Review hypothesis {hyp_id}: {primary.get('statement', '')[:500]}",
        "target_layer": "prompt_only",
        "mechanism_trace": None,
        "confidence": conf_str,
        "risk": risk,
        "expected_benefit": f"Address {hyp_type} pattern: {primary.get('statement', '')[:300]}",
        "failure_mode_prevented": obs.get("description", "")[:500],
        "falsification_condition": "If counter-evidence outweighs supporting evidence, the hypothesis is incorrect.",
        "promotion_requirements": {
            "reviewer_acceptance": False,
            "evidence_basis": "; ".join(evidence_citations[:3]) or "Hypothesis-derived evidence",
            "items": [{"key": "reviewer_signoff", "description": "Director confirms the improvement is worth implementing."}],
        },
        "recommended_destination": "prompt_only",
        "review_status": rs,
        "reviewer_notes": "",
        "_hypothesis_provenance": {
            "hypothesis_id": hyp_id,
            "writer": hypothesis.get("provenance", {}).get("writer", "hypothesis_generator.py"),
            "score_impact": impact,
            "score_quality": inv.get("evidence_quality", 0),
        },
    }
