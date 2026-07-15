"""Hypothesis generator — deterministic analyzer consuming outcome correlation data.

PURPOSE: Convert correlated observations into ranked, reviewable improvement hypotheses.
This is NOT autonomous self-modification. Hypotheses are advisory-only — they cannot
change behavior, block completion, or alter discovery.

CONSUMES:
  outcome_index entries (from outcome_index.py rebuild_index)
  discovery-index entries (from evidence_index.py load_index)
  telemetry data (from evidence_coverage_analyzer.py)

PRODUCES:
  improvement-hypotheses_{run_id}.jsonl — deterministic, no LLM, no promotion

EPISTEMIC RULES (load-bearing):
  - correlation != causation — hypotheses always list multiple explanations
  - "possible discovery gap" NOT "discovery failed"
  - missing data = unknown, not negative conclusion
  - counter-evidence preserved alongside supporting evidence
"""

from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any

HYPOTHESIS_SCHEMA_VERSION = "improvement-hypothesis.v1"
DEFAULT_OUTPUT_DIR = None  # caller supplies output path


def _now_utc_z() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _gen_id() -> str:
    return f"hyp-{_now_utc_z()[:19].replace(':', '')}-{os.urandom(2).hex()}"


# ── hypothesis lifecycle states ───────────────────────────────────────────────

ALLOWED_STATUSES = frozenset({
    "GENERATED",
    "UNDER_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "DUPLICATE",
    "INSUFFICIENT_EVIDENCE",
    "ALREADY_SOLVED",
    "STALE",
})

STALE_AGE_DAYS_DEFAULT = 90

# Confidence-to-evidence-tier mapping for candidate bridge.
_CONFIDENCE_TO_TIER: dict[float, str] = {
    0.0: "inference",
    0.3: "inference",
    0.4: "inference",
    0.5: "source_inspection",
    0.6: "source_inspection",
    0.7: "execution_artifact",
    0.8: "execution_artifact",
    1.0: "execution_artifact",
}


def _confidence_to_tier(confidence: float) -> str:
    for threshold, tier in sorted(_CONFIDENCE_TO_TIER.items(), reverse=True):
        if confidence >= threshold:
            return tier
    return "inference"


def _hypothesis_type_to_candidate_type(hyp_type: str) -> str:
    """Map hypothesis observation type to improvement-candidate type."""
    mapping: dict[str, str] = {
        "possible_discovery_gap": "semantic_coverage_gap",
        "possible_evidence_reuse_opportunity": "overclaim_or_evidence_gap",
        "possible_discovery_overreach": "semantic_coverage_gap",
        "possible_process_gap": "workflow_friction",
        "possible_implementation_issue": "workflow_friction",
        "positive_evidence_reuse": "documentation_gap",
        "positive_first_pass_validation": "documentation_gap",
        "positive_discovery_success": "documentation_gap",
        "unknown": "documentation_gap",
    }
    return mapping.get(hyp_type, "documentation_gap")


# ── hypothesis types ─────────────────────────────────────────────────────────

HYPOTHESIS_TYPES = frozenset({
    "possible_discovery_gap",
    "possible_evidence_reuse_opportunity",
    "possible_discovery_overreach",
    "possible_process_gap",
    "possible_implementation_issue",
    "positive_evidence_reuse",
    "positive_first_pass_validation",
    "positive_discovery_success",
    "unknown",
})


# ── ranking scores per dimension ─────────────────────────────────────────────

# All scoring is deterministic: derived from counts and field presence.
# Frequency: how often does this pattern appear?
# Impact: severity of the outcome signal (blocked > redo > error)
# Evidence quality: how well supported are the observations?
# Scope: how many distinct surfaces/runs are affected?
# Reversibility: can improvement be tested safely?


def _frequency(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    ratio = count / total
    if ratio >= 0.5:
        return 1.0
    if ratio >= 0.3:
        return 0.8
    if ratio >= 0.15:
        return 0.6
    if ratio >= 0.05:
        return 0.4
    if count > 0:
        return 0.2
    return 0.0


def _impact_score(outcome_ref: dict) -> float:
    """Determine impact from outcome signals. Highest individual signal wins."""
    lc = str(outcome_ref.get("lifecycle_status", ""))
    qa = str(outcome_ref.get("qa_verdict", ""))
    cv = str(outcome_ref.get("completion_verdict", ""))
    fr = str(outcome_ref.get("falsification_result", ""))

    if fr == "FALSIFIED":
        return 1.0
    if cv == "BLOCK":
        return 0.9
    if lc == "blocked":
        return 0.8
    if qa == "redo":
        return 0.6
    if qa == "error":
        return 0.5
    if lc == "completed" and (qa in ("accept", "accept-with-concerns") or not qa):
        return 0.2  # positive outcome
    return 0.3


def _evidence_quality(outcome_ref: dict, discovery_ref: dict) -> float:
    """How many evidence sources exist for this run?"""
    sources = 0
    if outcome_ref.get("qa_verdict"):
        sources += 1
    if outcome_ref.get("completion_verdict"):
        sources += 1
    if outcome_ref.get("falsification_result"):
        sources += 1
    if discovery_ref.get("surface_fingerprint"):
        sources += 1
    if discovery_ref.get("finding_count", 0) > 0:
        sources += 1
    # Cap at 1.0
    return min(sources / 5.0, 1.0)


def _scope_surface_count(entries: list[dict]) -> int:
    return len({e.get("discovery_reference", {}).get("surface_fingerprint", "") for e in entries if e.get("discovery_reference", {}).get("surface_fingerprint")})


# ── rule table (deterministic) ───────────────────────────────────────────────


def _classify_run(entry: dict) -> list[dict]:
    """Classify a single outcome entry into hypotheses with confidence scores.

    Returns list of hypothesis dicts. Always returns at least one (may be "unknown").
    Multiple hypotheses are possible — never collapses to a single explanation.
    """
    dr = entry.get("discovery_reference", {}) or {}
    outcome = entry.get("outcome_reference", {}) or {}
    lifecycle = str(outcome.get("lifecycle_status", "") or "")
    qa = str(outcome.get("qa_verdict", "") or "")
    completion = str(outcome.get("completion_verdict", "") or "")
    falsification = str(outcome.get("falsification_result", "") or "")
    findings = int(dr.get("finding_count", 0) or 0)
    struct = int(dr.get("structural_issue_count", 0) or 0)
    evidence_retrieved = bool(dr.get("evidence_retrieved", False))
    fingerprint = str(dr.get("surface_fingerprint", "") or "")

    hypotheses: list[dict] = []

    # ── Negative outcome rules ────────────────────────────────────────────

    is_redo = (qa == "redo")
    is_blocked = (lifecycle == "blocked")
    is_completion_block = (completion == "BLOCK")
    is_falsified = (falsification == "FALSIFIED")
    is_negative = is_redo or is_blocked or is_completion_block or is_falsified

    if not is_negative:
        # ── Positive outcomes ─────────────────────────────────────────────
        if lifecycle == "completed" and qa in ("accept", "accept-with-concerns", ""):
            if evidence_retrieved and findings > 0:
                hypotheses.append({
                    "statement": "Prior evidence was available and findings were produced — discovery likely adequate",
                    "confidence": 0.7,
                    "supporting_evidence": ["evidence_retrieved", f"finding_count={findings}"],
                    "counter_evidence": [],
                    "hypothesis_type": "positive_discovery_success",
                })
            elif evidence_retrieved:
                hypotheses.append({
                    "statement": "Discovery retrieved prior evidence but produced no new findings — possible confirmation or scope saturation",
                    "confidence": 0.5,
                    "supporting_evidence": ["evidence_retrieved", "finding_count=0"],
                    "counter_evidence": [],
                    "hypothesis_type": "positive_evidence_reuse",
                })
            else:
                hypotheses.append({
                    "statement": "Run completed successfully with no evidence issues — positive outcome without discovery correlation",
                    "confidence": 0.4,
                    "supporting_evidence": ["lifecycle_status=completed", "no_verdict_issues"],
                    "counter_evidence": [],
                    "hypothesis_type": "positive_first_pass_validation",
                })
        else:
            hypotheses.append({
                "statement": "Run completed without negative signals — no hypothesis warranted",
                "confidence": 0.3,
                "supporting_evidence": [],
                "counter_evidence": [],
                "hypothesis_type": "unknown",
            })
    else:
        # ── Negative: possible discovery gap ──────────────────────────────
        if (is_redo or is_blocked) and findings == 0 and not evidence_retrieved:
            hypotheses.append({
                "statement": "No findings produced and no prior evidence was retrieved — possible discovery scope gap",
                "confidence": 0.7,
                "supporting_evidence": [f"finding_count={findings}", "evidence_retrieved=false",
                                        f"qa_verdict={qa}" if qa else f"lifecycle_status={lifecycle}"],
                "counter_evidence": ["finding count may be valid if no issues exist"],
                "hypothesis_type": "possible_discovery_gap",
            })
        elif (is_redo or is_blocked) and findings == 0 and evidence_retrieved:
            hypotheses.append({
                "statement": "Prior evidence was retrieved but produced no findings — possible evidence mismatch or stale evidence",
                "confidence": 0.5,
                "supporting_evidence": ["evidence_retrieved=true", "finding_count=0"],
                "counter_evidence": ["stale evidence may have been correctly irrelevant"],
                "hypothesis_type": "possible_evidence_reuse_opportunity",
            })
        elif is_redo and findings > 0:
            hypotheses.append({
                "statement": "Discovery found issues but implementation required redo — possible implementation gap, not discovery failure",
                "confidence": 0.6,
                "supporting_evidence": [f"finding_count={findings}", "qa_verdict=redo"],
                "counter_evidence": ["findings may have been irrelevant or incomplete"],
                "hypothesis_type": "possible_implementation_issue",
            })
        elif is_completion_block:
            gaps = outcome.get("completion_blocking_gaps", [])
            has_writer_gap = any("writer" in g.lower() for g in gaps)
            if has_writer_gap:
                hypotheses.append({
                    "statement": "Completion blocked on missing writer — possible wrong-layer fix or incomplete implementation",
                    "confidence": 0.8,
                    "supporting_evidence": [f"completion_blocking_gaps={gaps}"],
                    "counter_evidence": [],
                    "hypothesis_type": "possible_process_gap",
                })
            else:
                hypotheses.append({
                    "statement": "Completion blocked by review gaps — possible implementation completeness gap",
                    "confidence": 0.5,
                    "supporting_evidence": [f"completion_blocking_gaps={gaps}"],
                    "counter_evidence": [],
                    "hypothesis_type": "possible_process_gap",
                })
        elif is_falsified:
            hypotheses.append({
                "statement": "Worker claims were falsified — possible verification gap or incorrect claim",
                "confidence": 0.7,
                "supporting_evidence": ["falsification_result=FALSIFIED"],
                "counter_evidence": [],
                "hypothesis_type": "possible_process_gap",
            })

        # ── Negative: possible discovery overreach ────────────────────────
        if (is_redo or is_blocked) and fingerprint and struct > 0 and findings > struct:
            hypotheses.append({
                "statement": "Large discovery scope with mostly non-structural findings followed by redo — possible overreach",
                "confidence": 0.4,
                "supporting_evidence": [f"finding_count={findings}", f"structural_issue_count={struct}"],
                "counter_evidence": ["high finding count may indicate thoroughness, not overreach"],
                "hypothesis_type": "possible_discovery_overreach",
            })

    # Always ensure at least "unknown" if nothing matched
    if not hypotheses:
        hypotheses.append({
            "statement": "Insufficient evidence to classify — uncorrelated outcome",
            "confidence": 0.0,
            "supporting_evidence": [],
            "counter_evidence": [],
            "hypothesis_type": "unknown",
        })

    return hypotheses


# ── hypothesis generation ────────────────────────────────────────────────────


def generate(
    index_entries: list[dict],
    output_path: Path | None = None,
) -> list[dict]:
    """Generate hypotheses from outcome index entries.

    Produces one hypothesis group per run. Returns list of hypothesis dicts.
    If output_path is given, appends to JSONL file.
    """
    if not index_entries:
        return []

    hypotheses_list: list[dict] = []
    for entry in index_entries:
        run_id = entry.get("run_id", "")
        dr = entry.get("discovery_reference", {}) or {}
        outcome = entry.get("outcome_reference", {}) or {}
        run_hypotheses = _classify_run(entry)

        # Build supporting run list from this entry
        supporting_run = {
            "run_id": run_id,
            "session_id": entry.get("session_id", ""),
            "surface_fingerprint": dr.get("surface_fingerprint", ""),
            "lifecycle_status": outcome.get("lifecycle_status", ""),
            "qa_verdict": outcome.get("qa_verdict", ""),
            "completion_verdict": outcome.get("completion_verdict", ""),
        }
        discovery_artifacts = [dr.get("artifact_path", "")] if dr.get("artifact_path") else []
        outcome_artifacts = [a for a in [
            f"qa-verdict:{outcome.get('qa_verdict', '')}" if outcome.get('qa_verdict') else "",
            f"completion:{outcome.get('completion_verdict', '')}" if outcome.get('completion_verdict') else "",
        ] if a]

        # Group by hypothesis type for aggregation
        for h in run_hypotheses:
            hyp = {
                "schema_version": HYPOTHESIS_SCHEMA_VERSION,
                "hypothesis_id": _gen_id(),
                "generated_at": _now_utc_z(),
                "observation": {
                    "type": h["hypothesis_type"],
                    "description": h["statement"],
                    "run_count": 1,
                },
                "evidence": {
                    "runs": [supporting_run],
                    "discovery_artifacts": discovery_artifacts,
                    "outcome_artifacts": outcome_artifacts,
                },
                "hypotheses": [{
                    "statement": h["statement"],
                    "confidence": h["confidence"],
                    "supporting_evidence": h["supporting_evidence"],
                    "counter_evidence": h["counter_evidence"],
                }],
                "investigation_value": {
                    "frequency": 0.0,  # populated by aggregate()
                    "impact": _impact_score(outcome),
                    "evidence_quality": _evidence_quality(outcome, dr),
                    "reversibility": 0.7,  # default: most discovery improvements are reversible
                },
                "status": "GENERATED",
                "status_history": [{"status": "GENERATED", "changed_at": _now_utc_z(), "reason": "initial_generation"}],
                "last_observed_at": _now_utc_z(),
                "observation_count": 1,
                "dedup_group": "|".join(filter(None, [
                    dr.get("surface_fingerprint", ""),
                    h["hypothesis_type"],
                ])),
                "provenance": {
                    "writer": "hypothesis_generator.py",
                    "source": "outcome_index",
                    "generated_at": _now_utc_z(),
                },
            }
            hypotheses_list.append(hyp)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "a", encoding="utf-8") as f:
            for h in hypotheses_list:
                f.write(json.dumps(h, default=str) + "\n")

    return hypotheses_list


# ── aggregation ──────────────────────────────────────────────────────────────


def aggregate(hypotheses: list[dict]) -> list[dict]:
    """Group hypotheses by type and compute aggregate scores.

    Returns ranked list of aggregated hypothesis groups.
    """
    if not hypotheses:
        return []

    groups: dict[str, dict[str, Any]] = {}
    for h in hypotheses:
        htype = h.get("observation", {}).get("type", "unknown")
        if htype not in groups:
            groups[htype] = {
                "hypothesis_type": htype,
                "description": h.get("observation", {}).get("description", ""),
                "count": 0,
                "runs": [],
                "avg_confidence": 0.0,
                "sum_impact": 0.0,
                "sum_evidence_quality": 0.0,
                "frequencies": [],
                "reversibility_sum": 0.0,
            }
        g = groups[htype]
        g["count"] += 1
        if h.get("evidence", {}).get("runs"):
            g["runs"].extend(h["evidence"]["runs"])
        confidence = h.get("hypotheses", [{}])[0].get("confidence", 0) if h.get("hypotheses") else 0
        g["avg_confidence"] += confidence
        g["sum_impact"] += h.get("investigation_value", {}).get("impact", 0)
        g["sum_evidence_quality"] += h.get("investigation_value", {}).get("evidence_quality", 0)
        g["reversibility_sum"] += h.get("investigation_value", {}).get("reversibility", 0.7)

    total = len(hypotheses)
    ranked = []
    for htype, g in groups.items():
        n = g["count"]
        freq = _frequency(n, total)
        avg_conf = g["avg_confidence"] / n if n > 0 else 0
        avg_impact = g["sum_impact"] / n if n > 0 else 0
        avg_quality = g["sum_evidence_quality"] / n if n > 0 else 0
        avg_rev = g["reversibility_sum"] / n if n > 0 else 0

        ranked.append({
            "hypothesis_type": htype,
            "count": n,
            "frequency_score": round(freq, 2),
            "avg_confidence": round(avg_conf, 2),
            "avg_impact": round(avg_impact, 2),
            "avg_evidence_quality": round(avg_quality, 2),
            "reversibility": round(avg_rev, 2),
            "runs": g["runs"],
        })

    ranked.sort(key=lambda x: (x["frequency_score"], x["avg_impact"]), reverse=True)
    return ranked


# ── queries (read-only) ──────────────────────────────────────────────────────


def query_by_type(hypotheses: list[dict], htype: str) -> list[dict]:
    """Filter hypotheses by type."""
    return [h for h in hypotheses
            if h.get("observation", {}).get("type") == htype]


def query_by_surface(hypotheses: list[dict], fingerprint: str) -> list[dict]:
    """Filter hypotheses by discovery surface fingerprint."""
    if not fingerprint:
        return []
    return [h for h in hypotheses
            for r in h.get("evidence", {}).get("runs", [])
            if r.get("surface_fingerprint") == fingerprint]


def top_by_value(hypotheses: list[dict], limit: int = 5) -> list[dict]:
    """Return top N hypotheses ranked by investigation value."""
    scored = sorted(
        hypotheses,
        key=lambda h: (
            h.get("investigation_value", {}).get("impact", 0) +
            h.get("investigation_value", {}).get("evidence_quality", 0)
        ),
        reverse=True,
    )
    return scored[:limit]


def get_summary(hypotheses: list[dict]) -> dict:
    """Aggregate summary of all hypotheses."""
    total = len(hypotheses)
    by_type: dict[str, int] = {}
    for h in hypotheses:
        htype = h.get("observation", {}).get("type", "unknown")
        by_type[htype] = by_type.get(htype, 0) + 1
    distinct_runs = set()
    for h in hypotheses:
        for r in h.get("evidence", {}).get("runs", []):
            distinct_runs.add(r.get("run_id"))
    return {
        "total_hypotheses": total,
        "distinct_run_count": len(distinct_runs),
        "by_type": by_type,
        "generated_at": _now_utc_z(),
    }
