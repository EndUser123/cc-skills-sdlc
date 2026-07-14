# Discovery Outcome Feedback — Phase 1: Outcome Correlation Foundation

## Final Report

---

## 1. Existing Outcome Mechanisms Reused

| Mechanism | Reuse Classification | How |
|---|---|---|
| `run-record.json` | `REUSE_EXISTING` | Primary source — every iteration starts from run records (lifecycle_status, run_id, session_id) |
| `discovery-outcome-link.json` | `REUSE_EXISTING` | Discovery reference data (fingerprint, finding_count, evidence_path) — was orphaned, now consumed |
| `qa-verdict-{run_id}.json` (terminal-scoped) | `REUSE_EXISTING` | QA status correlated via run_id glob across all terminal state dirs |
| `completion-evidence-review_{run_id}.json` (terminal-scoped) | `REUSE_EXISTING` | Verdict + blocking_gaps correlated via run_id |
| `falsification-result_{run_id}.json` (terminal-scoped) | `REUSE_EXISTING` | Falsification verdict correlated via run_id |
| `evidence_index.py` patterns | `REUSE_EXISTING` | Atomic write pattern, rebuild_index pattern, entry sort, load_index — matched the discovery index contract |
| `evidence_reader.py` patterns | `REUSE_EXISTING` | Read-only query interface, aggregate results, advisory-only returns |

---

## 2. New Files

| File | Lines | Purpose |
|---|---|---|
| `skills/go/scripts/outcome_index.py` | ~220 | Rebuildable outcome correlation index. Walks run-records, globs terminal-scoped verdict files, joins by run_id. Atomic writes. Fail-soft. |
| `skills/go/scripts/outcome_reader.py` | ~170 | Read-only query interface: `query_by_surface`, `query_by_run`, `query_by_outcome`, `get_outcome_summary`. Returns facts + provenance + counts. Never returns recommendations. |
| `skills/go/tests/test_outcome_correlation.py` | ~350 | 26 tests covering rebuild, correlation (QA/completion/falsification), reader queries, hypothesis safety, missing/malformed data, provenance, domain separation. |

---

## 3. Artifact Model

### `outcome-index.json` (rebuildable cache)

```
Location: {artifacts_root}/outcome-index.json
Schema:   outcome-index.v1
Writer:   outcome_index.py:rebuild_index()
Readers:  outcome_reader.py (query_by_*)
Authority: None — advisory-only cache. No mechanism reads it to gate execution.
Freshness: As-of-last-rebuild. Index carries generated_at per entry.
Failure:  Fail-soft: missing source = null fields, malformed = skipped with diagnostic.
Rebuild:  Delete and re-run rebuild_index(). Idempotent — same source = same output.
Retention: Safe to delete at any time. No source evidence lost (all data derived).
```

### Entry schema

```json
{
  "schema_version": "1",
  "run_id": "...",
  "session_id": "...",
  "repository": "...",
  "revision": "...",
  "discovery_reference": {
    "surface_fingerprint": "...",
    "finding_count": 0,
    "evidence_retrieved": false
  },
  "outcome_reference": {
    "lifecycle_status": "...",
    "qa_verdict": "...",
    "completion_verdict": "...",
    "falsification_result": "..."
  },
  "provenance": {
    "writers": [
      "run-record.json",
      "discovery-outcome-link.json",
      "qa-verdict"
    ],
    "source_artifacts": [
      "{root}/go-runs/{session}/{run}/run-record.json"
    ]
  }
}
```

---

## 4. Authority Boundaries

| Action | Authority | Mechanism |
|---|---|---|
| Reading outcome data | Read-only queries | `outcome_reader` — returns advisory results |
| Blocking `/go` execution | **Never** | No outcome mechanism writes markers or exit codes |
| Modifying completion decisions | **Never** | No reader feeds into orchestrator STEP gates |
| Modifying discovery scope | **Never** | Separate domain — discovery-index.json untouched |
| Modifying routing | **Never** | No routing table reads outcome data |
| Modifying behavior | **Never** | No automatic changes. This is pure observation. |

The outcome index is a **cache**. It is rebuildable from source artifacts. Delete it and nothing changes — the next `rebuild_index()` restores it. No mechanism reads it to authorize, block, or modify anything.

---

## 5. Evidence Flow

```text
GO-RUNS TREE (shared):
  run-record.json ──────────────────────┐
  discovery-outcome-link.json ──────────┤
                                        │
TERMINAL STATE_DIRS (scoped):           │
  go/qa-verdict-{run}.json ────────────┤
  go/completion-evidence-review_{run}.json ─┤
  go/falsification-result_{run}.json ──┘
                                        │
                                        ▼
                              outcome_index.py
                              rebuild_index()
                              (glob + join by run_id)
                                        │
                                        ▼
                              outcome-index.json
                              (cache, rebuildable)
                                        │
                                        ▼
                              outcome_reader.py
                              query_by_surface()
                              query_by_run()
                              get_outcome_summary()
                                        │
                                        ▼
                              Advisory results (facts + counts)
                              Never block, never modify behavior
```

---

## 6. Correlation Examples

**QA redo correlation**: A run with `qa-verdict-r1.json: qa_status=redo` and `run-record.json: run_id=r1` produces an outcome entry with `outcome_reference.qa_verdict="redo"`. The `query_by_surface` reader can aggregate all redo outcomes for a given discovery fingerprint.

**Completion BLOCK correlation**: A run with `completion-evidence-review_r1.json: verdict=BLOCK` and `blocking_gaps=["Missing writer"]` produces an outcome entry with `completion_verdict="BLOCK"` and `completion_blocking_gaps=["Missing writer"]`.

**Falsification result**: A run with `falsification-result_r1.json: verdict=FALSIFIED` produces `falsification_result="FALSIFIED"`.

**Missing data**: A run with no QA verdict file leaves `qa_verdict=""`. A run with no completion review leaves `completion_verdict=""`. No false conclusions.

---

## 7. Tests (26 total)

| Category | Count | What |
|---|---|---|
| Rebuild from run records | 6 | Basic, empty, corrupted regeneration, malformed, deterministic |
| QA verdict correlation | 3 | Found, missing, malformed |
| Completion review correlation | 1 | Verdict + blocking gaps |
| Falsification correlation | 1 | Verdict |
| Outcome link correlation | 1 | Fingerprint + finding count |
| Reader queries | 4 | By surface, by run, summary, empty index |
| Hypothesis safety | 3 | No false conclusions, no hypothesis fields, provenance retained |
| Domain separation | 2 | Separate index file, missing index returns empty |

**Regression**: 54 discovery evidence + analyzer tests pass. Full /go suite: 1032 passed, 2 skipped (previously 1006 + 26 new = 1032). Zero regressions.

---

## 8. Limitations

1. **Terminal-scoped verdict files**: QA, completion, and falsification verdicts live in terminal-scoped state dirs. The index globs `*/go/qa-verdict-*.json` across the artifacts root — if a terminal dir uses a non-standard path, the glob misses it. No fix without changing the terminal state dir contract.

2. **No cross-terminal dedup**: If two terminals produced a verdict for the same run_id (e.g., during a redo), both are found — the last glob-sorted entry wins. Acceptable for Phase 1 (terminal isolation means same run_id shouldn't exist in two terminals).

3. **No authoritativeness on verdict fields**: QA verdict contains `qa_status` which is the authoritative field. The reader trusts it. If the verdict schema changes, the reader must update.

4. **No consumption yet**: The index is written and readable but no mechanism reads it to make decisions. This is intentional (Phase 1 = pure observation) but means the value is deferred.

5. **Candidate preparation groundwork is implicit**: The design required "candidate preparation" data structures. The index schema explicitly avoids hypothesis language (uses null fields, not blame terms). A future candidate generator can read this data and apply its own hypothesis rules without re-scanning source artifacts.

---

## 9. Rollback Plan

**Rollback scope**: Delete `outcome_index.py`, `outcome_reader.py`, `test_outcome_correlation.py`. No existing code was modified — no behavioral changes to roll back.

**Verification**: `pytest skills/go/tests/test_discovery_evidence_reuse.py` and full suite still pass without these files.

**Data**: `outcome-index.json` is a cache. Delete it with no data loss — source artifacts (run-records, verdicts) are untouched.

---

## Explicit Answers

### Is outcome data authoritative?

**No.** Outcome data is stored in a rebuildable cache (`outcome-index.json`). It is derived from source artifacts (run-records, QA verdicts, completion reviews). The source artifacts are authoritative for their own domain (lifecycle status, QA status, etc.). The index is a correlation layer — it joins facts, it does not create them.

### Can deleting the outcome index lose source evidence?

**No.** The index is pure cache. Every fact it contains is derived from a source artifact in the go-runs tree or terminal state dirs. Delete the index file and the source artifacts remain. `rebuild_index()` restores the index from source.

### Can outcome correlation change execution?

**No.** No mechanism reads the outcome index to block, authorize, or modify execution. The index is written but never consumed by any gate, dispatcher, or orchestrator step. It is advisory observation only — the same advisory boundary as the discovery evidence reader.

### Can the system distinguish evidence from hypothesis?

**Yes, structurally.** The index stores only evidence fields (read from verifiable artifacts). No hypothesis fields exist in the schema. The `hypothesis_language_not_present` test verifies this — the only way a hypothesis enters the system is if a future candidate generator explicitly adds it as a new field. That generator would be in a separate module with its own tests and authority boundary.

Specific structural separations:
- Fields are named after their sources: `qa_verdict` (not `qa_failure`), `lifecycle_status` (not `status_is_good`)
- `discovery_reference` contains `finding_count`, `evidence_retrieved` — not `discovery_adequacy` or `discovery_success`
- `outcome_reference.completion_blocking_gaps` is a list of strings read directly from the completion review artifact
- Missing data = empty/null fields, not "insufficient" or "failed" labels

### What future evidence would justify candidate generation?

The deferred candidate generation workstream (Phase 2 of the design) would be justified when:

1. **Outcome index has ≥10 correlated entries** — enough data to observe patterns (which surfaces have redo rates > 20%? which fingerprints correlate with completion blocks?).
2. **At least 2 distinct run outcomes are observed** (e.g., both `qa_verdict=redo` and `lifecycle_status=blocked` are present in the index).
3. **At least 3 distinct discovery surface fingerprints** exist in the index (enough to distinguish surface-specific patterns from global noise).
4. **No automatic consumption** of candidates — the generator must write `hypothesis` fields to a separate `discovery-improvement-candidates_{run_id}.jsonl` file (not the outcome index), and only a human can promote them.

The current Phase 1 infrastructure provides all the structured data a future candidate generator would need: surface fingerprints, finding counts, QA verdicts, completion verdicts, blocking gaps, falsification results, all joined by run_id and provenanced back to source artifacts.

---

`PASS_OUTCOME_CORRELATION_FOUNDATION_WITH_LIMITATIONS`
