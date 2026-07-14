# Adaptive Discovery & Evidence-Guided Planning — Design Assessment

## Verdict: ADAPTIVE_DISCOVERY_DESIGN_READY_FOR_REVIEW

---

## 1. Current Discovery Architecture

/go presently operates a **layered, deterministic classification pipeline** with no adaptive depth. Discovery breadth and depth are set at proposal time by static keyword classifiers and never re-evaluated during execution.

### Pipeline (single-pass, pre-work)

```
prompt → rewrite_goal()
       → classify_dispatch()           [pi / claude / local / pause]
       → classify_intent()             [decide | investigate | validate | implement | mixed]
       → detect_risk_signals()         [high_risk, prompt_review_required]
       → derive_execution_tier()       [direct_answer | local_surgical | local_rigorous | full_go | pause_for_authorization]
       → classify_operational_discovery() [required: bool, surfaces: list]
       → classify_mechanism_change()   [NO_CHANGE..BLOCKED if operational_discovery.required]
       → derive_report_gate()          [discovery_evidence_required, discovery_incomplete flags]
       → generate_proposal()
         → _inject_prior_evidence()    [evidence_index query → advisory prior_evidence block]
```

### Discovery mechanisms (5 total)

| # | Mechanism | Where | Trigger | Breadth | Authority |
|---|-----------|-------|---------|---------|-----------|
| 1 | **Risk signal detection** | `detect_risk_signals()` | Keyword match (28 high-risk, 7 low-risk, model affinity, risky-vs-safe) | Binary: high_risk or not, plus model_affinity, prompt_review_required | Advisory — affects tier, not scope |
| 2 | **Intent classification** | `classify_intent()` | Regex patterns for decide/investigate/validate/implement/mixed | 5 categories | Deterministic — gates report structure and authority level |
| 3 | **Operational discovery contract** | `classify_operational_discovery()` | Word-boundary match against 11 surface groups (hook, gate, worktree, state, markers, cache, session, export, artifact-lifecycle, branch) | Boolean required + surface list + verification ranking + lifecycle inventory | Advisory — worker MUST produce discovery_evidence before verified recommendation |
| 4 | **Evidence reader (prior runs)** | `_inject_prior_evidence()` | Surface fingerprint + label overlap on discovery-index | Max 5 entries, freshness-classified | Advisory only — never blocks |
| 5 | **Worker discovery evidence** | `discovery_evidence_{run_id}.json` | Worker observes structural issues during task execution | 8 canonical structural_issue categories | Advisory — fed into mechanism_change resolution and report_gate |

### Post-work discovery merge

```
worker output → discovery-evidence_{run_id}.json
             → apply_discovery_evidence_merge()    [merges into proposal]
             → emit_discovery_evidence_telemetry()  [observability, non-blocking]
             → _persist_evidence()                  [copy to go-runs artifact store + index append]
```

### Key architectural properties

- **Single-pass classification.** All discovery scope is decided before the worker starts. No mid-run re-assessment.
- **Deterministic, no LLM.** Classification is pure keyword/regex on the raw prompt / rewritten goal. No model used.
- **Advisory evidence only.** Prior evidence and worker findings accelerate but never block. There is no "insufficient discovery" gate — only a "discovery_incomplete" advisory label in the report.
- **Worker-driven structural findings.** The only runtime discovery happens through the worker's ad-hoc observations, not systematic exploration. The discovery-evidence contract says "if you observe a structural issue, report it" — it never says "find structural issues in these areas."
- **No discovery depth selection.** An "investigate" intent on a hook surface gets the same discovery contract as "implement" on the same surface. The difference is in the report gate (completion claims), not in what the worker is asked to discover.
- **No sufficiency criteria.** The report gate can say "discovery_incomplete" if findings are missing when required, but there is no mechanism to say "this much discovery is enough for this task."
- **No evidence gap reporting.** The system knows whether discovery_evidence was written (telemetry), but never tells the worker "you haven't looked at X yet."
- **No automated discovery expansion.** If the worker encounters a surface that wasn't classified at proposal time, there is no mechanism to re-classify and expand discovery scope.

---

## 2. Existing Capability Inventory

### Risk classification (CL-1)
Keyword-based high/medium/low risk detection. 28 high-risk and 7 low-risk markers. Used primarily for execution tier derivation. **Strengths:** Deterministic, no model needed. **Limitations:** Keywords may not cover new risk patterns, no severity ranking.

### Execution tiers (CL-2)
5-level tier: direct_answer → local_surgical → local_rigorous → full_go → pause_for_authorization. Derived from intent + dispatch + risk. Determines delegation strategy and mutation scope. **Strengths:** Simple progression. **Limitations:** The boundary between "surgical" and "rigorous" is purely cost/complexity heuristics — not evidence sufficiency.

### Intent classification (CL-3)
Regex-based 5-category classifier (decide/investigate/validate/implement/mixed). **Strengths:** Zero false positives from model hallucination. **Limitations:** A "mixed" intent (the catch-all) gets flattened to the most permissive tier, potentially under-discovering for the investigate portion of an implement+investigate task.

### Operational discovery contract (CL-4)
11 surface groups detected by word-boundary match. Worker contract to identify writer/storage/reader/lifecycle/authority/stale-direction. **Strengths:** Source-anchored, deterministic, no model needed. **Limitations:** The contract only activates when surface keywords appear in the prompt — a user who says "move the cache invalidation logic" (no surface keyword) gets zero discovery contract even though cache surfaces are clearly involved. All verification paths ranked the same regardless of discovery depth needed.

### Mechanism-change resolution (CL-5)
6-result resolution path (NO_CHANGE through BLOCKED). Report-only enforcement for NO_CHANGE/BLOCKED. **Strengths:** Prevents blind editing. **Limitations:** Activated only through operational_discovery.required — same surface-keyword dependency. No independent trigger for meta-change tasks.

### Discovery evidence index & reader (CL-6)
SHA256 fingerprint + dependency hash index over completed go-runs. Freshness classification (fresh/stale_dependency/stale_clock). Cross-session policy (active runs invisible). Advisory-only invariant. **Strengths:** Rebuildable from artifacts, no mutable global memory, no state sharing across sessions for active runs. **Limitations:** The fingerprint is based on surface_labels (structural_issue categories like "dead_producer_consumer"), not on semantic task similarity. Two runs differing by intent but sharing a "hook" surface get the same fingerprint. No evidence cascade: if prior evidence exists for an adjacent surface, the reader doesn't surface it.

### Discovery evidence telemetry (CL-7)
Non-blocking per-run JSONL telemetry: whether the worker wrote findings, finding count, structural issue count, source (dedicated file vs claude-task-result fallback). **Strengths:** Zero-overhead observability. **Limitations:** No aggregate query, no trend analysis, no cross-run correlation. Telemetry is pure logging — no feedback loop.

### Closure check & reproduction policy (CL-8)
Reproduction-first requirement for bug-fix tasks. Classification-based closure_check.required + repro_policy. **Strengths:** Prevents "fixed" claims without symptom reproduction. **Limitations:** Only activates on explicit bug-fix keywords. A task that discovers a bug during implementation (not the primary intent) gets no closure check.

### Report gate (CL-9)
Multi-dimensional gate controlling completion claims: discovery_evidence_required, mechanism_change_report_only, allow_completion_claim. **Strengths:** Fine-grained control over "verified" labeling. **Limitations:** The gate is advisory — it sets flags that the report generator reads, but there is no enforcement layer. A misbehaving worker can claim Fixed even when discovery_incomplete is true.

---

## 3. Current Discovery Failure Modes

### F-1: Surface-keyword dependency blind spots
Discovery contracts only activate when the prompt contains a known surface keyword. A prompt like "Make the worktree cleanup logic not delete active sessions" mentions "cleanup" and "sessions" but may not include "worktree" — the contract never fires. **Frequency: High.** Users describe intent, not surface membership.

### F-2: No mid-run scope re-classification
Discovery scope is frozen at proposal time. A worker tasked with "implement a new gate" who discovers during source reading that the task also requires router.py changes and hooks.json registration gets no expanded discovery contract. The worker can report findings through discovery_evidence, but the contract doesn't tell them what to look for in the newly discovered surface. **Frequency: Medium.** Common with hook/gate/router tasks that span multiple surfaces.

### F-3: Discovery breadth is binary, not proportional
`operational_discovery.required` is a single boolean. All operational surfaces get the same contract (identify writer/storage/reader/lifecycle/authority). A one-line hook registration gets the same discovery requirement as a new router dispatcher. **Frequency: Medium.** Tunnel-vision on keywords flattens real variation in discovery scope.

### F-4: No evidence gap awareness
The system tracks whether the worker wrote discovery_evidence (telemetry), but never what the worker *didn't* examine. A worker who looked at 2 of 8 required discovery checkpoints (writer/storage/reader/lifecycle/authority/stale-direction/current-state/verification-paths) gets the same "discovery_evidence_passes: true" as one who examined all 8. **Frequency: High.** The telemetry records finding count, not surface coverage.

### F-5: Evidence reader only matches exact fingerprints
The evidence reader matches by exact surface_fingerprint or label overlap. Two similar-but-not-identical tasks (e.g., "fix the Stop hook's output format" vs "add JSON validation to the Stop hook" — both involve hooks, both have "output" and "stop" surface overlap) don't cross-pollinate. **Frequency: Medium.** Limits evidence reuse across related surfaces.

### F-6: Stale clock heuristic is fixed
The 72-hour STALE_AGE_HOURS_DEFAULT is a single constant for all evidence types. A dependency-verified finding about a stable code path (e.g., "the Settings class hasn't changed in 6 months") is treated the same as one about a volatile path. **Frequency: Low.** But high-impact when wrong — re-verifying a stable structural finding wastes effort.

### F-7: No adaptive depth selection
An "investigate" intent always gets the same discovery breadth regardless of prompt length, complexity, or risk signals. A 3-line "investigate why the Stop hook is failing" gets the same discovery contract as a 300-line architectural audit. **Frequency: High.** The only differentiator is execution_tier, which gates mutation scope, not discovery breadth.

### F-8: Discovery telemetry has no feedback loop
The `telemetry-discovery-evidence_{run_id}.jsonl` file is written and forgotten. There is no aggregate analysis, no trend detection, no mechanism to say "80% of workers are missing the 'current state' checkpoint — expand the contract or reduce the requirement." **Frequency: Persistent structural gap.**

### F-9: Worker discovery evidence is self-selected
The discovery-evidence contract says "if you observe a structural issue, report it." It never says "examine these specific areas for structural issues." Workers self-select what to report, creating systematic under-reporting of issues outside their immediate task focus. **Frequency: High.** By design — the contract is advisory, not prescriptive.

### F-10: Capability claims can skip discovery
A task that invokes capability claims ("shipped", "absorbed", "production") gets a capability_claim_audit requirement, but there is no cross-reference with operational_discovery. A capability claim on a hook surface triggers the audit but not the operational discovery contract — the writer/storage/reader check is skipped. **Frequency: Medium.** The two classification paths (keyword surfaces vs capability claims) are independent.

---

## 4. Proposed Adaptive Discovery Model

### Core principle

**The minimum sufficient discovery required to safely make a change, adapted to what the task needs rather than what keywords it contains.**

Not more discovery — more *targeted* discovery, proportional to the task's actual surface, risk, and uncertainty at each execution phase.

### Model overview

Three-phase adaptive cycle replaces the single-pass classification:

```
Phase 1: Initial scope (existing proposal, unchanged)
  prompt → rewrite → classify → generate_proposal
  (Same deterministic pipeline. No changes.)

Phase 2: Evidence-driven expansion (NEW — operational)
  After worker starts, if the discovered surface exceeds the classified surface:
    → re-classify remaining scope
    → expand discovery contract if needed
    → emit discovery-requirement-change_{run_id}.json
  
Phase 3: Sufficiency verification (NEW — report-time)
  Before report gate:
    → verify each required checkpoint has evidence
    → classify evidence gaps by severity (missing | partial | adequate)
    → emit evidence-coverage_{run_id}.json
    → downgrade completion claims if gaps exist
```

### Key additions (5 mechanisms, all NEW)

#### M-A: Dynamic surface re-classification (addresses F-1, F-2)
When the worker's source reading discovers a surface not in the proposal's `operational_discovery.surfaces`, the worker writes `discovery-surface-change_{run_id}.json`. The merge reader re-classifies and expands the contract.

**Design criteria:**
- **Problem:** Fixed-at-proposal discovery misses surfaces the worker discovers.
- **Evidence:** Any /go run that touches hooks/gates/routers and wasn't classified as an operational surface at proposal time.
- **Root cause:** Classification runs on the user's prompt, not on the code the worker reads.
- **Cost of inaction:** Workers operate without the discovery contract for legitimate surfaces they discover during the task.
- **Existing capability analysis:** None — no re-classification mechanism exists.
- **Authority:** Worker-initiated, merge-reader-validated. Never blocks — advisory expansion.
- **Storage:** Run-local JSON file, merged at artifact time, discarded with the run. No persistent state.
- **Freshness:** Run-scoped. Doesn't survive the run except in telemetry.
- **Failure behavior:** No surface-change file = no expansion (current behavior preserved). Malformed file = ignored.
- **Cognitive impact:** Worker must recognize when they've crossed into a new surface and file the change. Low friction — one JSON write.
- **Verification:** Test that a worker-discovered surface produces an expanded contract. Test that a surface-change file without findings passes the merge reader.

#### M-B: Proportionate discovery breadth (addresses F-3, F-7)
Replace the `operational_discovery.required` boolean with a 3-level breadth selector:
- `narrow` — single-surface, well-understood (one known mechanism extension). Contract: identify writer/storage/reader.
- `standard` — multi-surface, moderate uncertainty (current default). Contract: full 7-item checklist.
- `comprehensive` — broad architectural change, high risk, or multi-surface with uncertainty. Contract: full checklist + verification ranking + empirical oracle preferred + lifecycle inventory.

Derived from: prompt length + risk signals + surface count + intent + execution tier.

**Design criteria:**
- **Problem:** Single boolean flattens real variation in discovery scope.
- **Evidence:** A one-line hook fix gets the same discovery contract as a new router dispatcher.
- **Root cause:** No scope dimension — only binary required/not-required.
- **Cost of inaction:** Workers waste cognitive overhead on oversized contracts for simple tasks; miss contract depth for complex ones.
- **Existing capability analysis:** `detect_risk_signals()` provides high_risk boolean that could feed breadth. `prompt_length >= 240` is already used for recon classification — extend to discovery breadth.
- **Authority:** Deterministic heuristic (no LLM). Same classification tier as existing intent/risk classifiers.
- **Storage:** In-memory (part of proposal dict). No new storage.
- **Freshness:** Per-run, set at proposal time. Surface-change file can trigger re-classification (see M-A).
- **Failure behavior:** Conservative: if breadth derivation fails, default to `standard`. Never `narrow` by default.
- **Cognitive impact:** None — classification is invisible to the worker. Only the contract changes.
- **Verification:** Test breadth derivation for each dimension (high risk = comprehensive, single surface = narrow, etc.). Test `standard` fallback on unknown inputs.

#### M-C: Evidence coverage gate (addresses F-4, F-9)
At report time, before the report gate finalizes completion claims, a deterministic checker verifies each required checkpoint has a corresponding finding. The claim is:
- coverage ≥ 80% and at least one verified finding → "adequate"
- coverage ≥ 50% → "partial"
- coverage < 50% → "insufficient"

Only "adequate" allows completion claims. "Partial" downgrades to advisory. "Insufficient" blocks verified claims and surfaces what was missed.

**Design criteria:**
- **Problem:** The system knows whether findings exist but not what the worker skipped.
- **Evidence:** Telemetry shows finding counts but no coverage tracking. Workers can meet "discovery_evidence_passes: true" after examining 2 of 8 checkpoints.
- **Root cause:** No coverage model — only existence model.
- **Cost of inaction:** Verified-but-under-discovered claims pass through with false confidence.
- **Existing capability analysis:** `derive_report_gate()` already handles "discovery_incomplete" — it can be extended with coverage-derived severity. The evidence telemetry JSONL is the right raw material.
- **Authority:** Deterministic (coverage % is computed, not judged). But note: this is the one mechanism where I would argue for relaxing the "no LLM" constraint. Coverage classification is a pure structural check — does a JSON field exist for each checkpoint? That's a grep, not a judgment.
- **Storage:** Run-local `evidence-coverage_{run_id}.json`. Discarded with the run. Telemetry aggregates coverage stats.
- **Freshness:** Run-local, generated at report time.
- **Failure behavior:** If coverage computation fails, default to "insufficient" (fail-closed). The report still works — it just can't make verified claims.
- **Cognitive impact:** Workers now see "evidence coverage: partial (missing: lifecycle/cleanup path, current state)" in the report — actionable gap info.
- **Verification:** Test 80%, 50%, 0% coverage thresholds. Test fail-closed on missing coverage file. Test that coverage telemetry is structured correctly.

#### M-D: Adaptive evidence reader search (addresses F-5)
The evidence reader query gets two additional search modes beyond exact fingerprint match:
1. **Surface similarity search** — if no exact fingerprint match, expand to runs sharing ≥2 surface labels.
2. **Intent-aware filtering** — if the current task has a "decide" or "investigate" intent, also return evidence from "implement" runs that had matching labels (implement runs often encounter the most structural findings).

**Design criteria:**
- **Problem:** Evidence reader only matches exact fingerprints or single-label overlap.
- **Evidence:** Two related tasks (Stop hook output format vs JSON validation) share "hook" and "output" surfaces but differ in fingerprint → no cross-pollination.
- **Root cause:** Flat matching model with no expansion heuristics.
- **Cost of inaction:** Historical evidence is underutilized. Workers re-discover known structural issues.
- **Existing capability analysis:** `_label_overlap()` already computes intersection — extend to threshold-based matching. The existing `_FRESH_ORDER` sort can be extended with a relevance score.
- **Authority:** Advisory only (same invariant). Expansion never overrides the advisory flag.
- **Storage:** No new storage — existing index is sufficient for expanded queries.
- **Freshness:** Query-time expansion. No persistent changes.
- **Failure behavior:** Expansion fails silently — falls back to exact match. The advisory flag is always true.
- **Cognitive impact:** Workers see more relevant prior evidence. If too many false positives, the limit parameter caps expansion.
- **Verification:** Test that surface similarity search returns runs with ≥2 shared labels. Test that implement-to-investigate cross-pollination works. Test no false expansion when no matches.

#### M-E: Evidence telemetry feedback loop (addresses F-8)
A post-run aggregator (`evidence-coverage-analyzer.py`) that reads telemetry-discovery-evidence JSONL files and produces aggregate stats:
- What proportion of runs achieve adequate coverage?
- Which checkpoints are most commonly missed?
- What's the average finding count per surface type?
- Which surfaces have the highest "insufficient coverage" rate?

Output is a structured JSON summary (`evidence-coverage-trends.json`) in the artifacts root. Not a live dashboard — an offline analysis that can inform contract adjustments.

**Design criteria:**
- **Problem:** Telemetry is written and forgotten. No aggregate analysis.
- **Evidence:** The telemetry JSONL has structural_issue_count, finding_count, and source, but no reader processes it.
- **Root cause:** No aggregation mechanism exists.
- **Cost of inaction:** Contract adjustments are guesswork. Can't measure whether the discovery evidence contract is working.
- **Existing capability analysis:** The existing `telemetry-discovery-evidence_{run_id}.jsonl` format has everything needed for aggregate stats. No format changes needed.
- **Authority:** Offline, run on demand (not per-run). The aggregator is never invoked in the hot path.
- **Storage:** `{artifacts_root}/evidence-coverage-trends.json`. Lightweight — one file, rebuilt on demand.
- **Freshness:** As-of-last-run. The aggregator timestamps its output.
- **Failure behavior:** No output if no telemetry files found. Never blocks /go.
- **Cognitive impact:** Zero — the aggregator runs offline.
- **Verification:** Test aggregation over 0, 1, 5, 100 telemetry files. Test correct checkpoint-missed counting. Test timestamp freshness.

### M-A through M-E interaction summary

```
Proposal time:
    classify_operational_discovery() → breadth: narrow|standard|comprehensive (M-B)
    evidence_reader.query() → adaptive search (M-D)

Worker runtime:
    worker finds new surface → discovery-surface-change_{run_id}.json (M-A)
    merge reader → re-classify → expand contract

Report time:
    evidence_coverage() → coverage % per checkpoint (M-C)
    coverage < 50% → insufficient → block verified claims
    coverage ≥ 50% → report as-is → advisory

Post-run (offline):
    evidence-coverage-analyzer.py → aggregate stats (M-E)
    stat: "80% of comprehensive runs miss lifecycle check" 
    → adjust contract or add guidance
```

---

## 5. Alternatives Considered

### A1: Full LLM-based discovery classifier
Replace keyword classifiers with a model that reads the prompt and the current code state to determine discovery scope.

**Rejected because:** The current deterministic pipeline is a design strength, not a weakness — zero false positives from hallucination, zero latency, zero model cost. An LLM classifier would add complexity, cost, and brittleness for marginal gain. The prompt alone is insufficient context for LLM-based scope determination (the code state matters more), and reading code state adds per-run latency. Key quote from design constraints: "No replacing evidence with model confidence."

### A2: Persistent cross-session pattern database
Store discovery findings in a queryable database (SQLite/JSON) that all sessions read from to build a collective pattern map.

**Rejected because:** Violates the "no global mutable memory" constraint. The current index is a cache rebuildable from artifacts — a database would introduce state management, reconciliation, and staleness issues. The evidence reader's advisory-only invariant is a safety property; a queryable DB would invite authoritative use.

### A3: Mandatory discovery before any implementation
Require every non-trivial task to pass through a discovery gate before the worker can edit files. Full-discovery-first model.

**Rejected because:** Over-discovery is as harmful as under-discovery. An `implement` intent on a `local_surgical` tier with a single known surface doesn't need a full discovery pass — the user already knows what to change. The constraint says: "The objective is not 'more discovery.' The objective is: The minimum sufficient discovery required to safely make a change."

### A4: Evidence cascade graph
Build a DAG of surface relations (hook → gate → router → state), so that classifying a task as "hook" automatically expands discovery to include gate/router/state.

**Rejected (deferred) because:** The surface relations are project-specific and require maintenance. A cache-invalidation task doesn't need a hook discovery just because both touch state dirs. If empirical evidence (M-E) shows specific surfaces are systematically co-missed, we can add a data-driven cascade instead of a static one.

### A5: Worker-proactive discovery expansion
Give the worker a tool (e.g., `expand_discovery()` bash command) that re-classifies the prompt on demand based on what the worker has read.

**Rejected because:** Adds a new command (against constraints: "No new commands unless a real user workflow requires it"). The file-based surface-change mechanism (M-A) achieves the same effect with zero new tool surface — the worker writes JSON, the merge reader acts. Simpler, more testable, less cognitive overhead.

### A6: Prompt-based discovery breadth derivation with LLM
Use a small model to read the prompt and recommend discovery breadth (narrow/standard/comprehensive) based on semantic content rather than keyword matches.

**Rejected because:** Same reasoning as A1: deterministic breadth derivation is adequate (prompt length, risk signals, surface count, intent), and the cost of over-classifying to `standard` is low. An LLM would occasionally hallucinate "comprehensive" for a trivial prompt or "narrow" for a complex one — the deterministic heuristic is better at the extremes where correctness matters.

---

## 6. Recommended Implementation Sequence

### Phase 2a: Coverage gate (M-C) — 2 days
**Why first:** The highest-impact gap is that discovery checkpoints have no coverage tracking. Without coverage, the breadth classifier (M-B) and surface expansion (M-A) produce contracts with no verification that they were followed.

**Steps:**
1. Add `evidence_coverage()` to `preflight_propose.py` — reads the discovery evidence and checks each required checkpoint for a matching finding.
2. Add `evidence-coverage_{run_id}.json` output — structured coverage report.
3. Modify `derive_report_gate()` to read coverage and downgrade completion claims at <50% and <80% thresholds.
4. Add coverage info to `build_plain_english_report()` — e.g., "Evidence coverage: partial (missing: lifecycle/cleanup path, current state)."
5. Write tests: 0% threshold, 50% threshold, 80% threshold, fail-closed on missing coverage file.

### Phase 2b: Proportionate breadth (M-B) — 1 day
**Why second:** Makes the coverage gate meaningful by issuing discovery contracts proportional to the task, so "insufficient coverage" means something about the task rather than a fixed checklist.

**Steps:**
1. Add breadth derivation to `classify_operational_discovery()` — compute breadth from prompt length, risk signals, surface count, and intent.
2. Update the return dict to include `discovery_breadth: "narrow"|"standard"|"comprehensive"`.
3. Modify the checklist to vary by breadth level.
4. Wire into `derive_report_gate()` — comprehensive tasks need higher coverage.
5. Write tests: breadth derivation for each dimension, standard fallback.

### Phase 2c: Adaptive evidence reader search (M-D) — 1 day
**Why third:** Increases evidence utilization with zero new failure modes — the advisory invariant is unchanged. Higher value from historical runs means the evidence persistence cost pays off sooner.

**Steps:**
1. Add surface similarity search to `evidence_reader.query()` — match on ≥2 shared surface labels.
2. Add intent-aware filtering — decide/investigate queries return implement-run evidence.
3. Add relevance score to query results (label overlap count).
4. Preserve advisory flag on all expanded results.
5. Write tests: surface similarity, intent cross-pollination, no-false-expansion.

### Phase 2d: Dynamic surface re-classification (M-A) — 1 day
**Why fourth:** Requires M-C and M-B to be in place so that re-classification produces a meaningful contract with tracked coverage. Without coverage tracking, re-classification expands the contract but can't tell whether the worker fulfilled it.

**Steps:**
1. Define `discovery-surface-change_{run_id}.json` schema (surface + observed context + proposed re-classification).
2. Add surface-change reader to `apply_discovery_evidence_merge()` — detects the file, re-runs classification on the expanded surface, updates the proposal's `operational_discovery` block.
3. Add the surface-change contract to the worker instructions in `task_prompt()` — tell the worker HOW to file a surface-change observation.
4. Write tests: surface-change triggers re-classification, malformed file ignored, no false positive.

### Phase 2e: Evidence telemetry feedback loop (M-E) — 1 day
**Why last:** Requires enough runs under the coverage gate (Phase 2a, ~1-2 weeks of real usage) to produce meaningful aggregate data. Building the analyzer before runs exist produces an empty report.

**Steps:**
1. Create `evidence-coverage-analyzer.py` — reads all `telemetry-discovery-evidence_*.jsonl` in the artifacts root, aggregates by surface type and breadth level.
2. Output structured JSON summary with checkpoint coverage rates, common failure patterns, and timestamp.
3. Add a CLI flag to invoke on demand (not per-run): `python evidence-coverage-analyzer.py`.
4. Write tests: aggregation over 0, 1, N telemetry files, correct counting.

### Total: ~6 days implementation

### Risk-adjusted estimate: 8 days
- Phase 2a (highest risk: coverage gate could affect existing runs) — 3 days
- Phase 2b (low risk — purely additive) — 1 day
- Phase 2c (low risk — query extension) — 1 day
- Phase 2d (moderate risk — worker contract change) — 2 days
- Phase 2e (low risk — offline analysis) — 1 day

---

## 7. Risks

### R-1: Coverage gate blocks valid completion claims (M-C)
**Severity:** Medium. **Likelihood:** Low.
If the coverage threshold is too strict (>80% for comprehensive tasks that legitimately only need 3 of 4 checkpoints), workers would get false "insufficient coverage" downgrades.
**Mitigation:** Thresholds are advisory, not hard-gated. The coverage report surfaces the downgrade but doesn't block the .pr-ready signal. The `derive_report_gate()` call path is advisory-only. Start with 50% threshold for "partial" and monitor telemetry for false positives.

### R-2: Dynamic re-classification creates infinite loop (M-A)
**Severity:** Low. **Likelihood:** Low.
A surface-change file triggers re-classification, which produces a new contract, which the worker must fulfill, which could generate another surface-change file.
**Mitigation:** Limit re-classification to one expansion per run. The merge reader tracks `reclassification_count` — at >1, surface-change files are silently ignored. The limit is documented in the merge reader logic.

### R-3: Adaptive evidence reader over-matches (M-D)
**Severity:** Low. **Likelihood:** Medium.
Surface similarity search could return irrelevant evidence (e.g., a "gate" task getting findings from an unrelated "gate" task that happens to share the same surface label).
**Mitigation:** The advisory flag is invariant — irrelevant evidence has no authority. The relevance score (label overlap count) lets the report generator show confidence. Workers can see and ignore irrelevant evidence. The limit parameter caps noise.

### R-4: Proportionate breadth misclassifies complex-but-short prompts (M-B)
**Severity:** Low. **Likelihood:** Low.
A short prompt like "Fix the auth race condition" involves auth, session state, possibly hooks or gate — but shortness signals "narrow."
**Mitigation:** Risk signals and intent override prompt length. "Race condition" triggers risk_signals high_risk, which forces `comprehensive` regardless of length. Surface count also feeds breadth — a prompt that mentions auth + session + hook gets `comprehensive`.

### R-5: Worker contract changes reduce adoption (M-A, M-C)
**Severity:** Medium. **Likelihood:** Medium.
Adding surface-change filing and coverage tracking to the worker contract increases the cognitive burden on subagents (Claude/pi). If surface-change filing becomes rote, workers stop doing it.
**Mitigation:** Coverage is computed automatically from existing discovery_evidence findings — the worker doesn't do anything new for M-C. Surface-change filing (M-A) is optional — no finding = no change = current behavior. Over-tracking in telemetry (M-E) would show whether adoption is sufficient.

### R-6: Scope creep — adaptive discovery becomes "all discovery, all the time" (systemic)
**Severity:** High. **Likelihood:** Low (with explicit constraint enforcement).
The constraint says: "Not more discovery. The minimum sufficient discovery required to safely make a change." Adaptive discovery's purpose is precision — not expansion. The risk is that each mechanism's justification ("we should check one more thing") adds layers until discovery is a multi-minute pre-flight for every task.
**Mitigation:** Every new checkpoint or expansion must be explicitly justified against the minimum-sufficient principle. Each mechanism in this design was evaluated for whether its coverage is proportional — the coverage gate (M-C) is the only one that can block, and it only blocks verified completion claims, not the work. Rejected mechanisms (A1-A6) demonstrate the minimum-sufficient analysis.

---

## 8. Acceptance Criteria

### M-C (Evidence coverage gate)
- [ ] AC-C1: `evidence_coverage()` computes coverage % from discovery_evidence findings vs required checkpoints
- [ ] AC-C2: Coverage ≥80% → "adequate" → completion claims allowed
- [ ] AC-C3: Coverage ≥50% → "partial" → completion claims downgraded to advisory
- [ ] AC-C4: Coverage <50% → "insufficient" → verified claims blocked
- [ ] AC-C5: Fail-closed: if coverage computation fails, default to "insufficient"
- [ ] AC-C6: Coverage telemetry written to `telemetry-discovery-evidence_{run_id}.jsonl`
- [ ] AC-C7: At least 8 test cases covering threshold boundaries, fail-closed, and malformed input

### M-B (Proportionate discovery breadth)
- [ ] AC-B1: `classify_operational_discovery()` returns breadth: "narrow" | "standard" | "comprehensive"
- [ ] AC-B2: Breadth derivation uses prompt length, risk signals, surface count, and intent
- [ ] AC-B3: Narrow → reduced checkpoint list (3 items)
- [ ] AC-B4: Comprehensive → full checklist + verification ranking + lifecycle inventory
- [ ] AC-B5: Standard → current default (7-item checklist)
- [ ] AC-B6: Fallback to "standard" on unknown/invalid inputs
- [ ] AC-B7: At least 6 test cases covering each breadth derivation dimension

### M-D (Adaptive evidence reader search)
- [ ] AC-D1: query() supports surface similarity search (≥2 shared labels)
- [ ] AC-D2: query() supports intent-aware filtering (decide/investigate returns implement-run evidence)
- [ ] AC-D3: Expanded results include relevance score (label overlap count)
- [ ] AC-D4: Advisory flag is always true — expansion never changes it
- [ ] AC-D5: No expansion when surface_labels is empty (degenerate case)
- [ ] AC-D6: At least 6 test cases covering similarity, intent filtering, and degenerate cases

### M-A (Dynamic surface re-classification)
- [ ] AC-A1: `discovery-surface-change_{run_id}.json` schema defined and validated
- [ ] AC-A2: Surface-change detected by merge reader → re-classification triggered
- [ ] AC-A3: Re-classification updates the proposal's `operational_discovery` block
- [ ] AC-A4: Malformed surface-change file silently ignored (no crash)
- [ ] AC-A5: Maximum 1 re-classification per run (>1 ignored)
- [ ] AC-A6: Worker contract updated to include surface-change filing instructions
- [ ] AC-A7: At least 5 test cases covering detection, re-classification, malformed input, and caps

### M-E (Evidence telemetry feedback loop)
- [ ] AC-E1: `evidence-coverage-analyzer.py` reads all telemetry-discovery-evidence JSONL files
- [ ] AC-E2: Aggregates by surface type and breadth level
- [ ] AC-E3: Reports checkpoint coverage rates (what % of runs achieved adequate coverage per checkpoint)
- [ ] AC-E4: Reports common failure patterns (which checkpoints most commonly missed)
- [ ] AC-E5: Timestamps the output with as-of-last-run
- [ ] AC-E6: Never blocks /go — invoked offline
- [ ] AC-E7: At least 4 test cases covering 0, 1, N files and degenerate output

### Global acceptance criteria
- [ ] AC-G1: All 27 existing Discovery Evidence Reuse tests still pass
- [ ] AC-G2: Full /go test suite at 979+ passing, 0 regressions
- [ ] AC-G3: No new commands added (all mechanisms use existing tool surface)
- [ ] AC-G4: No global mutable memory created (all state is run-local or rebuildable from artifacts)
- [ ] AC-G5: Advisory invariant preserved on all evidence operations
- [ ] AC-G6: No LLM-based classifiers (all mechanisms are deterministic heuristics or structural checks)

---

## Mechanism Map Summary

| Mechanism | F-1 | F-2 | F-3 | F-4 | F-5 | F-6 | F-7 | F-8 | F-9 | F-10 | Cost | Reversibility |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:----:|:----:|:-------------:|
| M-A DynSurface | ✓ | ✓ | - | - | - | - | - | - | - | - | 1d | High (no persistent state) |
| M-B Breadth | - | - | ✓ | - | - | - | ✓ | - | - | - | 1d | High (purely additive) |
| M-C Coverage | - | - | - | ✓ | - | - | - | - | ✓ | ✓ | 2d | Medium (affects report gate) |
| M-D AdapReader | - | - | - | - | ✓ | - | - | - | - | - | 1d | High (query extension, no state) |
| M-E TeleLoop | - | - | - | - | - | - | - | ✓ | - | - | 1d | High (offline analysis only) |

- **F-6** (stale clock heuristic): Not addressed in this phase. A future improvement could make `STALE_AGE_HOURS_DEFAULT` path-sensitive (stable code paths → longer threshold, volatile paths → shorter), but that requires path-volatility data we don't have yet. Tracked as deferred.
- **F-10** (capability claims skip discovery): Indirectly addressed by M-C (coverage gate would flag missing discovery for capability-claim tasks that also touch operational surfaces). Direct fix (cross-reference capability_claims with operational_discovery) is a one-line change in `derive_report_gate()` — included in M-C scope.

### Cost summary

| Phase | Effort | Risk | Dependencies |
|-------|--------|------|-------------|
| 2a: Coverage gate | 2-3d | Medium (affects claims) | None |
| 2b: Breadth selection | 1d | Low | 2a (gives breadth meaning) |
| 2c: Adaptive reader | 1d | Low | None |
| 2d: Surface change | 1-2d | Moderate (worker contract) | 2a, 2b (contract needs meaning) |
| 2e: Telemetry loop | 1d | Low | 2a (needs run data) |
| **Total** | **6-8d** | | |

---

ADAPTIVE_DISCOVERY_DESIGN_READY_FOR_REVIEW
