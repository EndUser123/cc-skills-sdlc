# Discovery Outcome Feedback Loop and GTO Candidate Generation

## Design Assessment

---

## 1. Current Feedback-Loop Architecture

### Mechanism Map

#### 1A. Discovery Evidence Persistence
| Field | Value |
|---|---|
| Writer | `orchestrate.py:_persist_evidence()` L1897 |
| Storage | `go-runs/{session}/{run}/discovery-evidence_{run_id}.json` |
| Reader | `evidence_index.py:rebuild_index()` L163 |
| Authority | None — advisory-only, never gates |
| Freshness | Index built from source artifacts; entry carries `created_at` |
| Failure | `except: pass` — silent, unlogged |
| Consumers | Evidence index → evidence reader → preflight propose |

#### 1B. Discovery-Outcome Link
| Field | Value |
|---|---|
| Writer | `orchestrate.py:_persist_evidence()` L1897–1910 |
| Storage | `go-runs/{session}/{run}/discovery-outcome-link.json` |
| Reader | **NONE** — not consumed by any mechanism |
| Authority | None — written alongside evidence, never read |
| Failure | `except: pass` — silent |
| Consumers | None — `WRITTEN_BUT_ORPHANED` |

#### 1C. Discovery Evidence Index
| Field | Value |
|---|---|
| Writer | `evidence_index.py:rebuild_index()` L163, `append_index_entry()` |
| Storage | `{artifacts_root}/discovery-index.json` |
| Reader | `evidence_reader.py:query()` L212 |
| Authority | None — advisory-only, returns `advisory: True` hardcoded |
| Freshness | Rebuildable from source artifacts |
| Failure | Fail-open — empty index returns zero results |
| Consumers | Preflight propose (`_inject_prior_evidence`) |

#### 1D. Adaptive Evidence Reader
| Field | Value |
|---|---|
| Writer | N/A |
| Reader | `preflight_propose.py:_inject_prior_evidence()` L3217 |
| Authority | None — returns `advisory: True` |
| Failure | Fail-open — any error → empty prior_evidence |
| Consumers | `/go` preflight proposal |

#### 1E. Telemetry Emission
| Writer | `preflight_propose.py:_emit_discovery_evidence_telemetry()` L2942 |
| Storage | `go-runs/{session}/{run}/telemetry-discovery-evidence_{run_id}.jsonl` |
| Reader | `evidence_coverage_analyzer.py:collect_telemetry()` L54 |
| Authority | None — offline only |
| Failure | `except: pass` — silent, never blocks |
| Consumers | Coverage analyzer (manual CLI) |

#### 1F. Run Record / Lifecycle Status
| Writer | `orchestrate.py` |
| Storage | `go-runs/{session}/{run}/run-record.json` |
| Reader | `evidence_index.py:rebuild_index()` L193 |
| Authority | Soft — reader filters active/blocked |
| Failure | Missing → status defaults to `unknown` |
| Consumers | Evidence index |

#### 1G. QA Verdict
| Writer | `run-qa-verification.py` |
| Storage | `qa-verdict-{RUN_ID}.json` |
| Reader | Orchestrator loop (STEP 6) |
| Authority | Blocking — `redo` increments attempt counter |
| Consumers | Orchestrator STEP 6 → loop check |

#### 1H. Completion Evidence Review
| Writer | `completion_evidence_review.py` |
| Storage | `completion-evidence-review_{RUN_ID}.json` |
| Reader | Orchestrator (STEP 6.7); completion verifier |
| Authority | Not directly blocking |
| Failure | `INCOMPLETE` if missing inputs |
| Consumers | Orchestrator → completion verifier |

#### 1I. Completion Verifier
| Writer | Main-loop Claude (STEP 6.8) |
| Storage | `completion-verify-result_{RUN_ID}.json` + ledger |
| Reader | Orchestrator `_apply_completion_verify_result` |
| Authority | Advisory — `ADVISORY_REVISE` does not block |
| Failure | Hard-block only on missing/malformed result |
| Consumers | Orchestrator tail |

#### 1J. Falsification Gate
| Writer | Main-loop Claude attacker |
| Storage | `falsification-result_{RUN_ID}.json` |
| Reader | Orchestrator `_falsification_resume` |
| Authority | Terminal — `FALSIFIED` resolves session pointer |
| Consumers | G4/G5 loop termination |

#### 1K. Debrief
| Writer | `/debrief` skill |
| Storage | TaskCreate/TaskUpdate (in-session) |
| Authority | Advisory |
| Consumers | User |

#### 1L. Pre-Mortem / Red-Team
| Writer | Respective skills |
| Storage | Session-local |
| Authority | Advisory |
| Consumers | User |

### Key Findings

1. **No GTO skill exists.** The pre-mortem references `skills/gto/lib/skill_coverage_detector` but no such directory exists in any cc-skills-* plugin. Always guarded by `try/except ImportError`.
2. **No candidate lifecycle exists anywhere.** No OBSERVED → EVIDENCE_COLLECTED → GTO_CANDIDATE → REVIEWED → PROMOTED/REJECTED pipeline. PROMOTED/REJECTED matches found are snapshot restore transitions, unrelated.
3. **discovery-outcome-link.json is orphaned.** Written alongside every discovery persistence call. Zero readers.
4. **Outcome signals siloed.** QA, completion review, falsification, lifecycle status — all isolated JSON files. No aggregation.
5. **Debrief produces tasks, not mechanism improvements.** It finds root causes but creates TaskCreate items, not "discovery contract too narrow" candidates.
6. **Telemetry analyzer is manual CLI — never invoked automatically.**

---

## 2. Existing Mechanisms That Can Be Reused

| Mechanism | Reuse | How |
|---|---|---|
| `discovery-index.json` | `REUSE_EXISTING` | Has surface_fingerprint, task_intent, run_id, finding_count |
| `discovery-outcome-link.json` | `EXTEND_EXISTING` | Schema exists but orphaned. Extend with outcome fields + reader |
| `run-record.json` | `REUSE_EXISTING` | Lifecycle_status is primary outcome signal |
| `qa-verdict-{RUN_ID}.json` | `REUSE_EXISTING` | Already has qa_status (accept/redo/error) |
| `completion-evidence-review_{RUN_ID}.json` | `REUSE_EXISTING` | Verdict + blocking_gaps |
| `telemetry-discovery-evidence_*.jsonl` | `REUSE_EXISTING` | findings_count, structural_issue_count, source |
| Index entry schema | `EXTEND_EXISTING` | Add `outcome_status` field |
| `_persist_evidence()` | `EXTEND_EXISTING` | Already writes link; needs outcome reader |
| `_inject_prior_evidence()` | `EXTEND_EXISTING` | Could inject outcome stats |
| Test patterns | `REUSE_EXISTING` | `test_discovery_evidence_reuse.py` infrastructure |

---

## 3. Outcome Signals Inventory

### Objective (high trust)
- `lifecycle_status = blocked` (run-record.json)
- QA verdict = `redo` (qa-verdict-{RUN_ID}.json)
- QA verdict = `error` (qa-verdict-{RUN_ID}.json)
- Completion review = `BLOCK` (completion-evidence-review_{RUN_ID}.json)
- Falsification = `FALSIFIED` (falsification-result_{RUN_ID}.json)
- Same fingerprint + different outcome (index analysis, medium trust)

### Subjective (medium — exclude from automation)
User correction (no structured parser), rejected plan, aborted run

### Noisy (exclude)
User frustration, LLM low confidence, long run time, high structural count without redo

**Start with objective signals only in Phase 1.**

---

## 4. Proposed GTO Candidate Model

### Lifecycle
`OUTCOME_DETECTED → EVIDENCE_COLLECTED → CANDIDATE_PRODUCED → REVIEWED → PROMOTED / REJECTED`

### Candidate key fields
- originating_run: run_id, session_id, revision, task_title, task_intent
- discovery_evidence: surface_fingerprint, surface_labels, finding_count, evidence_retrieved
- outcome_evidence: lifecycle_status, qa_verdict, completion_review_verdict, blocking_gaps, failure_classes
- root_cause_hypothesis: array of {hypothesis, confidence, evidence} — ≥2 entries required
- proposed_improvement: summary, destination, change_type, code_change, documentation_change
- status: lifecycle state
- metadata: recurrence_count, human_notes, promoted_at

### Lifecycle Rules
| Transition | Authority |
|---|---|
| outcome_detected → evidence_collected | System (automated) |
| evidence_collected → candidate_produced | System (automated) |
| candidate_produced → reviewed | Human |
| reviewed → promoted | Human |
| reviewed → rejected | Human |
| Auto-archive after 90d | System |

**No automatic promotion.** No mechanism reads promoted candidates to modify behavior.

---

## 5. Alternatives Considered

### A1: Real-time blocking feedback loop — Rejected
Violates observe-before-act. Would need <5% FP rate.

### A2: LLM-generated improvement candidates — Rejected
LLM confidence is not evidence. Exception: `source: "llm"` tag allowed.

### A3: Dedicated candidate database — Rejected
No new persistence. Candidates are JSONL in go-runs artifact tree.

### A4: Use /debrief as generator — Deferred
Works from transcripts, not structured artifact data. Could converge Phase 3.

### A5: Merge into QA verdict — Partially accepted
Extend qa-verdict with failure classes. Candidate derived, not stored inside.

### A6: Auto-promote after N recurrences — Rejected
N may mean systematic failure, not correct improvement.

---

## 6. Failure Modes

| # | Failure | Mitigation |
|---|---|---|
| F-1 | False causality | Dual-hypothesis requirement with mandatory evidence trace |
| F-2 | Candidate noise | Phase 1 limited to rare events (blocked, redo only) |
| F-3 | Confirmation bias | Hard filter: finding_count>0 never produces discovery_failure |
| F-4 | Stale candidates | Auto-archive after 90d (archive ≠ delete) |
| F-5 | Missing outcome evidence | Stays at outcome_detected — fail-closed |
| F-6 | Human never reviews | Acceptable — no mechanism blocks on unread candidates |

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Cognitive load without benefit | Phase 1 limited to rare outcomes; re-evaluate after 2 weeks |
| False causality misleads human | Dual-hypothesis; evidence-cited confidence |
| Schema drift | Versioned schema; old format tolerated |
| Promotion without evidence check | No automatic consumption — separate workstream required |
| Orphaned outcome signals | Fail-open — human can delete or leave |

---

## 8. Recommended Implementation Sequence

### Phase 1: Outcome Correlation (3-4 hours)
1. Extend index schema: `outcome_status`, `outcome_qa_verdict`, `outcome_completion_verdict`
2. Utility module to read discovery-outcome-link files and backfill index. Idempotent.
3. Extend `evidence_reader.query()` return with `outcome_stats` block.
4. Add `evidence_reader.get_outcome_summary(fingerprint)` — aggregate per surface.
5. ≥10 tests.

### Phase 2: Candidate Generator (4-5 hours)
1. `scripts/candidate_generator.py`: detect_outcomes, collect_evidence, classify_failure (deterministic rule table), write_candidate
2. CLI: `python candidate_generator.py [--artifacts-root PATH]`. Idempotent, cursor-tracked.
3. Hypothesis rules:
   - `finding_count==0 AND evidence_retrieved==false` → discovery_failure (0.7)
   - `finding_count>0 AND qa_verdict=="redo"` → implementation_failure (0.6)
   - `true` → unknown (0.0) [fallthrough]
4. ≥15 tests.

### Phase 3: Candidate Review CLI (2-3 hours)
1. `--summary` — markdown report of un-reviewed candidates
2. `--review <id> --status promoted|rejected` — status toggle
3. No automatic consumption
4. ≥5 tests.

### Phase 4: Consumption Gate (deferred)
Deferred until ≥10 produced, ≥3 reviewed, ≥1 promoted.

---

## 9. Acceptance Criteria

### Phase 1
- [ ] Index entry has outcome_status after rebuild
- [ ] query() returns outcome_stats
- [ ] get_outcome_summary() returns aggregate
- [ ] Backward-compatible with no outcome data
- [ ] ≥10 tests

### Phase 2
- [ ] --scan finds blocked/redo runs
- [ ] classify_failure is deterministic (no LLM)
- [ ] Candidate written to go-runs artifact path
- [ ] No candidate for runs without outcome signal
- [ ] Idempotent
- [ ] Missing evidence → graceful (not crash)
- [ ] ≥15 tests

### Phase 3
- [ ] --summary prints markdown
- [ ] --review toggles status
- [ ] Reviewed excluded from summary
- [ ] No automatic consumption
- [ ] ≥5 tests

### Non-Goals
No automatic changes. No new memory/vector DB. No hot-path blocking. No consumption gate.

---

## Explicit Answers

### What is evidence versus hypothesis?
**Evidence**: structured field from a verifiable artifact (run-record, qa-verdict, index entry). **Hypothesis**: deterministic rule table output mapping evidence patterns to classifications. No LLM in the loop. No matching rule → `unknown (0.0)`.

### How does a failed outcome become a candidate?
Scan run-records + qa-verdicts → correlate via run_id → read discovery-outcome-link → read discovery-evidence + completion review → run classify_failure() → write candidate JSONL → advance cursor.

### How do we avoid blaming discovery for unrelated failures?
Hard structural decoupling in rule table: `finding_count>0` never leads to `discovery_failure`. Dual-hypothesis requirement ensures ≥2 explanations. Evidence fields prove each hypothesis.

### How does approved learning return to the system?
**It doesn't — yet.** Consumption Gate deferred until ≥10/3/1 candidates exist. Designing consumption before real data means designing in ignorance.

### What prevents automatic behavior drift?
1. No automatic promotion (human-only toggle)
2. No automatic consumption (promoted is metadata flag)
3. No LLM in hypothesis loop (deterministic code)
4. Reversible by design (append-only JSONL)
5. No new authority boundary (candidates are advisory)
6. Observation period (10/3/1 gate on consumption workstream)

---

`DISCOVERY_OUTCOME_FEEDBACK_DESIGN_READY_FOR_REVIEW`
