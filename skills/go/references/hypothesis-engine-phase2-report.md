# Discovery Outcome Feedback — Phase 2: Evidence-Based Improvement Hypothesis Engine

## Final Report

---

## 1. Existing Mechanisms Reused

| Mechanism | Reuse | How |
|---|---|---|
| `outcome_index` entry schema | `REUSE_EXISTING` | Hypothesis generator consumes `discovery_reference` + `outcome_reference` blocks directly |
| `outcome_reader` pattern | `REUSE_EXISTING` | Read-only queries: `query_by_type`, `query_by_surface`, `get_summary` mirror the reader pattern |
| `evidence_coverage_analyzer` classification | `CONCEPTUAL_REUSE` | Deterministic rule table approach mirrored (not code-reused, structurally analogous) |
| Artifact contract patterns | `REUSE_EXISTING` | JSON schema with `schema_version`, `generated_at`, `provenance`, `status` — same pattern as discovery-evidence, outcome-index, and qa-verdict |
| `_build_entry` pattern | `REUSE_EXISTING` | Match the index module: facts in, no side effects, deterministic output |

---

## 2. New Artifacts

| File | Lines | Purpose |
|---|---|---|
| `skills/go/scripts/hypothesis_generator.py` | ~330 | Deterministic analyzer consuming outcome index entries → hypothesis JSONL. No LLM. No promotion. Read-only queries included. |
| `skills/go/tests/test_hypothesis_generator.py` | ~250 | 25 tests covering safety, provenance, ranking, positive/negative, authority, empty inputs |

### Artifact Schema

```json
{
  "hypothesis_id": "hyp-20260714T220000-abc0",
  "observation": {
    "type": "possible_discovery_gap",
    "description": "No findings produced and no prior evidence retrieved...",
    "run_count": 1
  },
  "evidence": {
    "runs": [{"run_id": "...", "surface_fingerprint": "...", ...}],
    "discovery_artifacts": [],
    "outcome_artifacts": []
  },
  "hypotheses": [{
    "statement": "No findings produced and no prior evidence was retrieved...",
    "confidence": 0.7,
    "supporting_evidence": [],
    "counter_evidence": []
  }],
  "investigation_value": {
    "frequency": 0.0,
    "impact": 0.6,
    "evidence_quality": 0.4,
    "reversibility": 0.7
  },
  "status": "GENERATED",
  "provenance": {
    "writer": "hypothesis_generator.py",
    "source": "outcome_index",
    "generated_at": "2026-07-14T22:00:00Z"
  }
}
```

### Artifact Contract

| Field | Value |
|---|---|
| Schema version | `improvement-hypothesis.v1` |
| Writer | `hypothesis_generator.py:generate()` |
| Storage | Caller-provided output path; appended as JSONL |
| Readers | `hypothesis_generator` queries (`query_by_type`, `query_by_surface`, `top_by_value`, `get_summary`) |
| Authority | None — advisory only, cannot block/modify execution |
| Freshness | Timestamped per hypothesis |
| Failure behavior | Empty input → empty output. No source artifacts touched. Never blocks. |
| Rebuild | Regenerate from outcome index (idempotent — same entries → same hypotheses) |
| Retention | Append-only. Rejection clears nothing — adds status to entry. |

---

## 3. Hypothesis Lifecycle

```text
GENERATED                    ← engine produces hypothesis
    ↓
ACCEPTED_FOR_REVIEW          ← human decides to investigate
    ↓
REJECTED / DUPLICATE /       ← human concludes
INSUFFICIENT_EVIDENCE /
ALREADY_SOLVED
```

Status defaults to `GENERATED`. No automatic promotion. No `PROMOTED` status exists in this phase. Rejected hypotheses remain in the file for future pattern analysis.

---

## 4. Evidence Flow

```text
Source artifacts (run-record, qa-verdict, completion-review)
    ↓
outcome_index.py:rebuild_index()
    ↓
outcome-index.json (correlation cache)
    ↓
hypothesis_generator.py:generate()
    ↓
improvement-hypotheses.jsonl
    ↓
hypothesis_generator queries (read-only)
```

---

## 5. Ranking Model

Scoring is deterministic — derived from field presence and counts, no random or LLM components:

### Frequency: `count / total`
| Threshold | Score |
|---|---|
| ≥ 50% of runs | 1.0 |
| ≥ 30% | 0.8 |
| ≥ 15% | 0.6 |
| ≥ 5% | 0.4 |
| > 0 but < 5% | 0.2 |
| 0 | 0.0 |

### Impact: max of outcome signals
| Signal | Score |
|---|---|
| `FALSIFIED` | 1.0 |
| Completion `BLOCK` | 0.9 |
| `lifecycle_status=blocked` | 0.8 |
| QA `redo` | 0.6 |
| QA `error` | 0.5 |
| Positive (completed/accept) | 0.2 |
| Unknown | 0.3 |

### Evidence Quality: `min(evidence_sources / 5, 1.0)`
One point each for: QA verdict, completion verdict, falsification result, surface fingerprint, findings > 0.

### Reversibility: default 0.7
Most discovery improvements are safe to test. Currently static — could become dynamic with future data.

### Composite: `aggregate()` sorts by `(frequency_score, avg_impact)` descending

---

## 6. Examples Generated from Test Data

### Negative: QA redo with zero findings
```json
{
  "observation": {"type": "possible_discovery_gap"},
  "hypotheses": [{
    "statement": "No findings produced and no prior evidence was retrieved...",
    "confidence": 0.7
  }]
}
```

### Negative: QA redo WITH findings
```json
{
  "observation": {"type": "possible_implementation_issue"},
  "hypotheses": [{
    "statement": "Discovery found issues but implementation required redo...",
    "confidence": 0.6
  }]
}
```
This is the critical epistemic boundary: findings exist → system blames implementation, NOT discovery. Test `test_redo_with_findings_produces_implementation_issue_not_discovery` enforces this.

### Positive: Successful run with findings
```json
{
  "observation": {"type": "positive_discovery_success"},
  "hypotheses": [{
    "statement": "Prior evidence was available and findings were produced...",
    "confidence": 0.7
  }]
}
```

### Falsification result
```json
{
  "observation": {"type": "possible_process_gap"},
  "hypotheses": [{"statement": "Worker claims were falsified...", "confidence": 0.7}]
}
```

---

## 7. Rejection Handling

The schema supports five status values and the rejection test verifies the field exists. No automatic rejection logic exists — all rejection is human review.

Rejected hypotheses remain in the JSONL file. They are excluded from active summaries when `query_by_type` or `top_by_value` evaluates, but the raw file can be re-analyzed:

```python
# Filter out rejected for active summary
active = [h for h in all_h if not h.get("status", "").startswith("REJECTED")]
```

---

## 8. Authority Boundaries

| Action | Authority | Mechanism |
|---|---|---|
| Read hypothesis data | ✅ Read-only queries | `query_by_type`, `query_by_surface`, `top_by_value`, `get_summary` |
| Block /go execution | ❌ Never | No hypothesis writes markers, exits, or orchestrator state |
| Modify completion decisions | ❌ Never | No hypothesis output consumed by orchestrator gates |
| Modify discovery scope | ❌ Never | No existing code reads hypothesis files |
| Promote itself | ❌ Never | Status hardcoded to `GENERATED`. No `PROMOTED` status exists |
| Generate LLM recommendations | ❌ Never | All hypothesis rules are deterministic Python if/elif |
| Create new user commands | ❌ Never | CLI interface: `generate()` takes params as function arguments |

Test `test_hypothesis_contains_no_authority_fields` hard-checks: no hypothesis output contains "block", "modify", "authorize", "required_change", or "must". Test `test_status_is_generated_not_promoted` verifies no hypothesis has status `PROMOTED`.

---

## 9. Tests (25 total)

| Category | Count | What |
|---|---|---|
| Hypothesis safety | 6 | No correlation=causation; findings=0→discovery_gap; findings>0→implementation_issue; multiple hypotheses; counter_evidence; possible language |
| Provenance | 4 | Links to run_id; non-outcome runs still produce; schema_version; timestamp |
| Ranking | 4 | Aggregation returns sorted list; empty input; top N; deterministic |
| Queries | 2 | Query by type; get_summary shape |
| Positive/negative | 3 | Success→positive type; blocked→non-positive; falsification→process_gap |
| Authority | 3 | No authority fields; status is GENERATED not PROMOTED; unique IDs |
| Rejection | 1 | Status field exists and supports rejection values |
| Empty/edge | 2 | Empty index; empty aggregate |

**Regression**: 80 discovery/analyzer/outcome-correlation tests pass. Full /go suite: 1057 passed, 2 skipped (25 new hypothesis tests, zero regressions).

---

## 10. Remaining Limitations

1. **No cross-run dedup yet**: Two runs with the same surface fingerprint and same outcome pattern produce two separate hypotheses. Future `aggregate()` could merge by fingerprint+type.

2. **Static reversibility**: `reversibility=0.7` is hardcoded for all discovery changes. A future phase could differentiate (surface expansion is more reversible than contract changes).

3. **No automated review CLI**: Hypotheses are written to JSONL and queryable, but there's no `--review` CLI to mark them `ACCEPTED_FOR_REVIEW` or `REJECTED`. That's Phase 3 work.

4. **No consumption**: Hypotheses are generated and queryable but unrelated to any `/go` behavior. This is intentional — observation before action — but means the value is deferred.

5. **Hypothesis is not a fact**: The schema, tests, and epistemic rules all enforce this. But if a future caller treats `confidence=0.7` as "probably true" and acts on it, the system drifts. The next phase must design the consumption gate that prevents this.

---

## 11. Next Recommended Phase

**Phase 3: Human Review CLI and Candidate Promotion Workflow**

Build on the generated hypotheses:

- `--review <hypothesis_id> --status accepted|rejected|duplicate` CLI
- Hypothesis summary report in markdown
- Hypothesis aggregation by surface fingerprint (dedup)
- Tracking of rejection patterns (which types are most often rejected? Which get accepted?)
- Still no automatic consumption — the consumption gate must wait until a separate design workstream after ≥10 hypotheses have been reviewed

---

## Explicit Answers

### Is a hypothesis a fact?

**No.** A hypothesis is a deterministic classification derived from evidence fields. It is tagged with a confidence score (0.0–1.0) derived from rule strength, not from evidence accuracy. The schema explicitly separates `evidence` (facts from artifacts) from `hypotheses` (explanations). Tests verify that hypothesis statements use "possible" language and never say "failed" or "is the cause."

### Can a hypothesis change behavior?

**No.** No mechanism reads hypothesis output to block, authorize, or modify execution. The hypothesis generator produces JSONL files that are only read via in-process queries. No orchestrator gate, dispatcher, or decision point consumes hypothesis data.

### Can a rejected hypothesis improve future analysis?

**Yes.** Rejected hypotheses remain in the JSONL file. A future analyzer can compute rejection rates per type, identifying which hypothesis categories produce false positives most often. This is explicitly not implemented yet — it requires the rejection tracking infrastructure that Phase 3 builds — but the data structure supports it. The status field includes `REJECTED`, `DUPLICATE`, `INSUFFICIENT_EVIDENCE`, and `ALREADY_SOLVED`, all of which carry semantic value for future analysis.

### Can the system distinguish correlation from causation?

**Yes, structurally.** Every hypothesis is built from a deterministic rule table that separates evidence from explanation:

```python
# Rule: findings exist + QA redo → implementation issue (NOT discovery failure)
if is_redo and findings > 0:
    hypothesis_type = "possible_implementation_issue"
    confidence = 0.6

# Rule: no findings + no evidence → discovery gap (capped at 0.7)
if is_negative and findings == 0 and not evidence_retrieved:
    hypothesis_type = "possible_discovery_gap"
    confidence = 0.7
```

Additional safeguards:
- Multiple hypotheses per run when multiple rules fire — never collapses to single explanation
- Counter-evidence list preserved alongside supporting evidence
- `unknown` hypothesis when no rule matches
- All confidence values are < 1.0 (max is 0.8 for writer-gap BLOCK)

### What evidence is required before a hypothesis becomes an approved improvement?

A hypothesis cannot become an approved improvement in Phase 2 — that requires the deferred consumption gate (Phase 4 of the original design document). The required evidence before that gate could be activated would include:

1. **≥ 10 hypotheses generated** (any types) — enough to observe the distribution
2. **≥ 3 hypotheses reviewed by human** — establishing that the hypothesis format is actionable
3. **≥ 1 hypothesis promoted** — proving a human found one worth implementing
4. **≥ 3 distinct surface fingerprints in promoted set** — ensuring the promotion pattern is not a single-instance fluke
5. **Consumption design document** specifying how promoted hypotheses map to actual changes (discovery contract, surface taxonomy, prompts) — designed separately, not bolted on

---

`PASS_HYPOTHESIS_ENGINE_FOUNDATION_WITH_LIMITATIONS`
