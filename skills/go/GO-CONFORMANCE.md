# /go_2.0 Conformance Checklist

**Governing rule:** Every decision that can block, resume, recommend, or complete a `/go` run must be derivable from machine-readable artifacts, not just markdown prose or terminal output.

Truth source assignment:
- **Live execution state:** `run-status.schema.json`
- **Readiness / gate outcome:** `verification-result.schema.json`
- **Blocked reason and recovery:** `block-state.schema.json`
- **Delegated implementation outcome:** `code-result.schema.json`
- **Human-readable explanation:** markdown — never authoritative over JSON

---

## Critical

### GO-CONF-001 — FIXED
block-state written at 4 hard-stops: max_attempts, verification_failed, simplify_failed, review_failed. All with `schema_version`, `reason_code`, `opened_at`, `evidence_paths`.

### GO-CONF-002 — FIXED
run-status initialized at task selection (STEP 1); updated at verification pass (STEP 3) with `verification_result_path`.

### GO-CONF-003 — FIXED
`task_outcome()` reads run-status.json first. Flags as atomic fallback. Stdout token parsing removed.

### GO-CONF-004 — OPEN
`$ref: "code-result.schema.json"` in `dispatch_results[]` may not resolve in all JSON Schema validators. `code-result.schema.json` exists with correct `$id`. Risk is low for validators that support `$id`-based resolution.

---

## High

### GO-CONF-005 — OPEN
Naming convention split: status fields use hyphens (`reviews-passed`), reason codes use underscores (`verification_failed`). Affects `ralph-go-loop.sh` status matching vs `run-status.schema.json` enum values. Requires one canonical convention decision.

### GO-CONF-006 — OPEN
ROUTING.md has 15 routing rows covering all required branches. Still prose-based — not enforced in code.

### GO-CONF-007 — FIXED
After `/tdd` invocation, SKILL.md now reads `tdd-receipt_{RUN_ID}.json` and blocks if `validated=false` or receipt missing. Blocks with `reason_code: tdd_validation_failed`.

### GO-CONF-008 — FIXED
`workflow_steps` now lists all 10 steps including `test_discovery` and `tdd_decision`.

### GO-CONF-009 — FIXED
Flag filename `.pr-ready_$RUN_ID` (hyphen) is consistent across SKILL.md artifact layout, `ralph-go-loop.sh`, and `go-safe.sh`.

---

## Medium

### GO-CONF-010 — FIXED
STEP 3 now writes `verification-result_{RUN_ID}.json` after successful verification, populating all required fields including `task_id`, `status`, `verification_commands`, `simplify`, and `generated_at`.

### GO-CONF-011 — FIXED
Pre-mortem and stakeholder sync now write structured recommendation objects to `run-status.recommendations[]` with `type`, `prompt`, `evidence`, `resolved`, `resolved_at`.

### GO-CONF-012 — OPEN
Recommendation type strings: schema enum uses `pre-mortem` (hyphen); `block-state.schema.json` has no `pre-mortem` reason code — different semantic space but potential confusion.

### GO-CONF-013 — FIXED
All 4 new schemas (`run-status`, `verification-result`, `block-state`, `code-result`) now declare `schema_version`.

### GO-CONF-014 — FIXED
`tasks-file.schema.json` created with full validation of tasks.json structure including `id`, `title`, `objective`, `status`, `priority`, `scope_in`, `scope_out`, `forbidden_files`, `acceptance_criteria`, `verification_commands`, `requires_approval`, `notes`.

---

## Low

### GO-CONF-015 — FIXED
SKILL.md title updated to `/go_2.0 — Verify, Simplify, Ship`.

### GO-CONF-016 — FIXED
`go-safe.sh` now invokes `/go_2.0` explicitly instead of matching any `/go`.

---

## Current open items

| ID | Severity | Area | Title |
|----|----------|------|-------|
| GO-CONF-004 | critical | schema | `$ref` resolution for `dispatch_results[]` |
| GO-CONF-005 | high | naming | Status hyphens vs reason code underscores |
| GO-CONF-006 | high | routing | Routing table not machine-enforced |
| GO-CONF-012 | medium | recommendation | Type string inconsistency (hyphen/enum vs underscore/reason) |

**Fixed this session (12 of 16):** 001, 002, 003, 007, 008, 009, 010, 011, 013, 014, 015, 016.

---

## Step graph — artifact completion matrix

| Step | Completion artifact | Failure artifact | Retry artifact |
|------|-------------------|-----------------|----------------|
| worktree_enforcement | `.worktree-ready_` | `.blocked_` + `block-state_` | none |
| task_selection | `active-task_.json` + `run-status_` | `.blocked_` + `block-state_` | none |
| task_contract | `.task-defined_` | `.blocked_` + `block-state_` | none |
| test_discovery | `test-gaps_.json` | none | none |
| tdd_decision | `tdd-receipt_.json` | `.blocked_` + `block-state_` | none |
| verify_end_to_end | `.verified_` + `verification-summary_` + `run-status_` | `.blocked_` + `block-state_` + `.attempt_N_` | `.attempt_N_` |
| simplify_code | `.simplified_` + `simplify-summary_` | `.blocked_` + `block-state_` | none |
| seven_pass_review | `.reviews-passed_` + `review-summary_` | `.blocked_` + `block-state_` | none |
| local_pr_artifacts | `pr-ready_.md` + `.pr-ready_` | none | none |
| loop_check | `run-status_.final_promise` | none | none |

---

## Routing branch matrix

| Branch condition | Predicate | Action | Artifacts | Terminal state |
|-----------------|-----------|--------|-----------|----------------|
| no code changes | `CODE_FILE_COUNT == 0` | skip TDD → simplify | — | continue |
| tests only | `CODE_FILE_COUNT > 0 && DOCS_ONLY` | `/t` RED only | `tdd-receipt_` | continue |
| implementation | `CODE_FILE_COUNT > 0 && !DOCS_ONLY` | `/t` → `/gap` → `/tdd` → validate | `test-gaps_`, `tdd-receipt_`, `block-state_` | continue or blocked |
| config/infra | diff classify | verify → reviews | — | continue |
| `/t` no gaps | `test-gaps_` empty | skip `/gap` → `/tdd` | — | continue |
| gap insufficient | confidence < threshold | block or recommend | — | blocked |
| TDD not validated | `validated == false` | block | `block-state_` | BLOCKED |
| TDD RED fails 3x | retry_count >= 3 | block | `block-state_` | BLOCKED |
| simplify HIGH/CRITICAL | grep CRITICAL/HIGH | block | `block-state_` | BLOCKED |
| review REVIEW_REQUIRED | pass status | block | `block-state_` | BLOCKED |
| max attempts | attempt >= MAX_ATTEMPTS | block | `block-state_` | BLOCKED |
| verification passes | exit_code == 0 | simplify | `verification-summary_` | continue |
| recommendations emitted | `recommendations.length > 0` | surface + await + write | `run-status_` | depends |
| stakeholder sync required | `requires_approval == true` | surface + await + write | `run-status_` | depends |
| more tasks remain | loop check | next cycle | — | MORE_TASKS_IN_PLAN |
| all tasks complete | loop check | exit | — | ALL_TASKS_COMPLETE |
