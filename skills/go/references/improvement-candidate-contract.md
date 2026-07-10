# Improvement-Candidate Contract

A lightweight, source-backed contract for reviewable improvement candidates
exchanged between the meta-skills around `/go`. A candidate is an
**artifact, not implementation approval**. Passing the validator means the file
is well-formed; promotion to runtime is a separate, explicit task owned by a
reviewer.

**Files:**

| Path | Role |
|------|------|
| `schemas/improvement_candidate.schema.json` | Structural reference (JSON Schema 2020-12). Convention mirror for external tooling. |
| `scripts/validate_improvement_candidate.py` | Authoritative checker. **Pure stdlib** — no `jsonschema` dependency. Owns cross-field rules the JSON Schema cannot express. |
| `references/examples/IC-*.json` | Reference fixtures (one valid + hook, one valid + behave, one intentionally invalid). |
| `tests/test_improvement_candidate_contract.py` | Pytest suite pinning validator behavior and fixture examples. |

## Why candidate artifacts exist

Each adjacent skill (`/friction`, `/behave`, `/skeptic`, `/dne`, `/evolve`,
`/genius`) produces a different *kind* of observation: workflow pain, LLM
failure, semantic gap, risk-prioritization, modernization debt, premise
challenge. Without a shared shape, those observations either get lost in
free-form notes or get auto-promoted into runtime (the failure mode the
integration review explicitly rejected). The candidate contract fixes both:
every observation lands as a structured file that a human reviews before
anything changes in `/go` or any other skill.

## How each adjacent skill produces candidates

| Skill | Typical `candidate_type` | Typical `target_layer` | Notes |
|-------|---------------------------|------------------------|-------|
| `/friction` | `workflow_friction`, `hook_candidate` | `hook` (proposed, never auto-promoted), `prompt_only` | `/friction` may *suggest* a hook in `proposed_change`, but `target_layer=hook` still requires the full hook promotion checklist (deterministic_decision, lifecycle_necessity, tested_script_underneath, safe_failure_direction, explicit_registration_plan). A PASS through the validator does **not** register a hook. |
| `/behave` | `llm_behavior_failure`, `overclaim_or_evidence_gap` | `prompt_only`, `advisory_review`, `validation_script` | Hypothesis-then-falsify output serializes into `observed_problem` (symptom), `evidence` (citations), and `falsification_condition`. `review_status` defaults to `proposed`. |
| `/skeptic` | `semantic_coverage_gap`, `overclaim_or_evidence_gap`, `documentation_gap` | `validation_script`, `report_contract`, `prompt_only`, `docs` | Findings become candidates with `evidence_tier` reflecting the strongest citation. Hallucination/overreach → `overclaim_or_evidence_gap`. |
| `/dne` | `risk_model`, `documentation_gap` | `report_contract`, `prompt_only` | `/dne`'s risk formula is a *prioritization input*, not a gate. A candidate may propose adding it to `/go`'s advisory tier (with calibration evidence in `promotion_requirements.items`). |
| `/evolve` | `technical_debt`, `cleanup_candidate`, `documentation_gap` | `modernization_campaign`, `prompt_only`, `orchestrator` | The candidate IS the `/evolve` handoff. `target_skill_or_system='go'` + `recommended_destination='modernization_campaign'` flags it for a phased audit/strategy/execute/harden campaign. |
| `/genius` | `documentation_gap`, `risk_model` | `prompt_only`, `report_contract`, `do_not_implement` | Manual framing tool. Candidates are framed observations, not runtime proposals. `do_not_implement` is a valid destination when the reframe shows the proposal would solve the wrong problem. |
| `/go` | `cleanup_candidate`, `semantic_coverage_gap`, `technical_debt` | any | `/go` itself can emit candidates when `discovery_evidence` or CER surfaces a structural finding that is out of scope for the current task. |
| `manual` | any | any | Reserved for director-emitted candidates. |

## How candidates are reviewed

1. The producer writes `IC-<KEY>-<LOCAL>.json` and runs the validator. **Validator PASS = well-formed, not approved.**
2. A human reviewer (or a structured review step in a future tool) reads `observed_problem`, `evidence`, `expected_benefit`, `falsification_condition`, and `promotion_requirements.items`.
3. Reviewer updates `review_status` (one of `proposed | needs_evidence | accepted_for_backlog | rejected | implemented | superseded`) and appends to `reviewer_notes`.
4. Promotion to runtime (`implemented`) requires **every** item in `promotion_requirements.items` to carry `satisfied=true` and a non-empty `evidence` citation. The validator enforces this.
5. The implementation task that actually changes code/hooks is a **separate** task with its own risk surface — it does NOT inherit "PASS" from the candidate validator.

## What cannot auto-promote

- Nothing. Candidates never auto-promote. No hook fires because a candidate's `target_layer='hook'`. No gate activates because a candidate's `target_layer='runtime_gate'`. No `/evolve` campaign starts because a candidate's `recommended_destination='modernization_campaign'`. Each promotion is an explicit implementation task.
- In particular, `review_status='proposed'` does NOT imply implementation. The validator does not reject `proposed`; it rejects `implemented` without promotion evidence.

## Safe self-learning without autonomous mutation

The contract gives the meta-skill ecosystem a place to *accumulate* learnings
without giving any single producer the authority to *apply* them. The
producer records what it saw, with citations; the reviewer decides what
deserves a runtime change; the implementation task is gated by `/go`'s own
evidence rules (or whatever process owns the targeted skill).

## How this differs from `/go` runtime gates

`/go` runtime gates (`Stop_enforce_gate.py`, `completion_evidence_review.py`,
`omission_audit.py`, `completion_verify.py`, `go_continuation_gate.py`) are
**wired, registered, and authoritative** at dispatch or completion time. A
candidate file is the opposite: unwired, unregistered, advisory. Conflating
the two is the failure mode this contract prevents.

- Runtime gates read state (`.pr-ready`, `task-proposal_*.json`, `claude-task-result_*.json`) and produce a verdict (BLOCK / REVISE / PROCEED).
- Candidates live in `references/examples/` (or wherever a producer drops them) and produce **no** verdict. They are inputs to a human review, not inputs to a hook.

## How `/evolve` receives modernization candidates

When `target_skill_or_system='go'` and `recommended_destination='modernization_campaign'`, the candidate is the **handoff packet** for `/evolve`:

- `observed_problem` names the debt or smell.
- `affected_layer` names where the debt lives (e.g., `orchestrator`).
- `promotion_requirements.items` should enumerate the `/evolve` prerequisites: baseline captured (`/profile --baseline` analog), CC>10 hotspots identified, SoloDevConstitutionalFilter pass recorded, ADR scope declared.
- `/evolve` reads the candidate, runs its 4-phase AUDIT→STRATEGY→EXECUTE→HARDEN, and only then produces tasks for `/go`.

## How `/friction` feeds workflow pain candidates

`/friction`'s output (interaction-friction markers, workflow-automation candidates) maps to `candidate_type='workflow_friction'` or `'hook_candidate'`. If `target_layer='hook'`, the candidate must enumerate the full hook promotion checklist (`HOOK_PROMOTION_KEYS` in the validator). This is the *only* path by which a `/friction` recommendation could land in the registry — and it still requires an explicit implementation task.

## How `/behave` feeds LLM-failure candidates

`/behave`'s hypothesis-then-falsify output becomes a candidate with:

- `observed_problem`: the symptom (e.g., "Lines 41-54 empty Python output").
- `evidence`: the unfalsified hypotheses and the tests that distinguished them.
- `evidence_tier`: usually `execution_artifact` (logs/test output) or `source_inspection`.
- `falsification_condition`: the observation that would show the diagnosis wrong.
- `target_layer`: typically `prompt_only` or `advisory_review`, never `runtime_gate` (because the failure is in the model's reasoning, not in a gate).

## How `/skeptic` feeds semantic/evidence gap candidates

`/skeptic`'s findings become candidates with `candidate_type` ∈
`{semantic_coverage_gap, overclaim_or_evidence_gap, documentation_gap}`.
`evidence_tier` reflects the strongest citation (usually `source_inspection`
or `official_doc_or_spec`). High-`risk` candidates that propose a new
runtime gate must carry `mechanism_trace` and the full runtime-gate
promotion checklist (`RUNTIME_GATE_PROMOTION_KEYS`).

## How `/dne` contributes risk-prioritization ideas without becoming a gate

`/dne` may produce a candidate with `candidate_type='risk_model'` and
`target_layer='report_contract'` or `'prompt_only'`. The candidate may
propose *adding* a risk score to `/go`'s advisory tier, with
`promotion_requirements.items` requiring corpus TP/FP evidence before the
score can even appear as input. **The validator never promotes this to a
gate** — that is a separate decision gated by the gate-discrimination rule
(real-corpus TP/FP first).

## How `/genius` remains a manual framing tool

`/genius` candidates are framed observations, often with
`recommended_destination='do_not_implement'` when the reframe shows the
original proposal would solve the wrong problem. The contract treats
`do_not_implement` as a first-class destination — it is itself a useful
artifact for future readers.

## Promotion requirements (summary)

| `target_layer` | Required `promotion_requirements.items` keys |
|----------------|----------------------------------------------|
| `prompt_only`, `docs`, `report_contract`, `advisory_review`, `skill_handoff`, `modernization_campaign`, `do_not_implement` | None mandatory (reviewer-defined checklist). |
| `validation_script`, `orchestrator` | Non-null `mechanism_trace` (full trace). |
| `runtime_gate` | Non-null `mechanism_trace` + items keys ⊇ `{real_boundary_test, calibration_data, fail_direction_decision, owner_approval}`. |
| `hook` | Non-null `mechanism_trace` + items keys ⊇ `{deterministic_decision, lifecycle_necessity, tested_script_underneath, safe_failure_direction, explicit_registration_plan}`. |

For `review_status='implemented'`: **every** item must have `satisfied=true` and a non-empty `evidence` citation. The validator enforces this.

## Quick reference

- **Write a candidate**: hand-author `IC-<KEY>-<LOCAL>.json`, run the validator.
- **Validate one file**: `python scripts/validate_improvement_candidate.py --file references/examples/IC-FRI-...json`
- **Validate a directory**: `python scripts/validate_improvement_candidate.py --dir references/examples/`
- **Run the suite**: `pytest tests/test_improvement_candidate_contract.py -v`