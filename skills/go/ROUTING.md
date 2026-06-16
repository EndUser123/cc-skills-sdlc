# /go → /tdd → /refactor Routing Notes

## Schema linkage

```
run-status.verification_result_path  → verification-result.schema.json instance
run-status.block_state_path         → block-state.schema.json instance
run-status.dispatch_results[]       → code-result.schema.json instances
verification-result.tdd.run_id       → TDD run session
verification-result.mutation.*       → mutation side-channel gate (mutmut 3.x)
run-status.active_route             → may be "mutation" while a mutation phase is executing
```

## Run-status as canonical live-state object

`run-status.json` is the orchestrator's live state. It is the single authoritative object for:
- what step is currently executing (`current_step`)
- whether progression is blocked and why (`block_state_path`)
- what verification evidence exists (`verification_result_path`)
- what decomposed code functions returned (`dispatch_results[]`)
- what recommendations are pending (`recommendations[]`)
- which side-channel route is active (`active_route` — one of `planning|design_v1.1|code|refactor|tdd|mutation|null`)

Treat `verification-result.json` as the canonical readiness object — it aggregates all gate outcomes (command checks, simplify, review passes, TDD, **mutation**, PR readiness) into one machine-readable fact. The `mutation` block in `verification-result.schema.json` is optional; present only when a mutation phase was executed for a target module in this run.

## Routing table

| Condition | Route | Why |
|-----------|-------|-----|
| code changes detected | `/code` | Execute behavior change, TDD if applicable |
| cleanup without behavior change | `/refactor` | Simplification, deduplication, restructuring |
| architecture unresolved or contract ambiguous | `/design_1.0` | Resolve design before `/code` |
| scope unclear or decomposition needed | `/planning` | Task breakdown before implementation |
| config/infra only | direct verify → reviews | No TDD needed; skip to quality gates |
| mutation audit (planning, test architecture) | `/t --mode mutation` | Coverage strategy + test-tooling selection |
| mutation gate during a TDD run (side-channel) | `/tdd --phase mutation --module <dotted>` | Writes a signed `MutationReceipt`; shared scorer with `/t` |

## /go auto-invoke chain for code tasks

```
1. /t          → test discovery, populates test-gaps_{run_id}.json
2. /gap        → loads gaps from /t output
3. /tdd        → RED phase (if gaps) or GREEN phase (if scaffolded)
   → /tdd --phase mutation --module <dotted>
                  → side-channel quality gate for critical-tier modules
   → /refactor → post-TDD cleanup if simplify flags debt
4. /simplify   → quality gate
5. 7-pass review → correctness, scope, tests, simplicity, regressions, maintainability, pr-ready
6. STEP 6.5 mutation-gate.py
              → for each critical-tier modified module, run the shared scorer
                 and write mutation-gate-{run_id}.json
```

## Blocking transitions

- `/tdd` fails RED three times → block with `reason_code: verification_failed`
- `/simplify` finds HIGH/CRITICAL → block with `reason_code: simplify_failed`
- review pass returns REVIEW_REQUIRED → block with `reason_code: review_failed`
- max retries exhausted → block with `reason_code: max_attempts_reached`
- STEP 6.5 mutation-gate.py exits non-zero (critical module below target) → block with `reason_code: mutation_failed`. Mutation is a side-channel gate: it does NOT advance the TDD lifecycle phase, but it DOES block PR readiness (`status != pr-ready` until waived or fixed).

## Resume semantics

When resuming a blocked run:
1. Read `block-state.json` to understand why blocked
2. Check `block_state.can_retry` — if false, requires user input
3. If `block_state.waiver_allowed`, operator can waive and retry. For mutation failures, waiver requires `treat_equivalent_mutants_under_threshold_as_pass` flag or a signed waiver in `mutation-gate-{run_id}.json` `waiver` field.
4. On retry, clear `.blocked_` flag and re-enter at last incomplete step
