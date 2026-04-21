# /go → /tdd → /refactor Routing Notes

## Schema linkage

```
run-status.verification_result_path  → verification-result.schema.json instance
run-status.block_state_path         → block-state.schema.json instance
run-status.dispatch_results[]       → code-result.schema.json instances
verification-result.tdd.run_id       → TDD run session
```

## Run-status as canonical live-state object

`run-status.json` is the orchestrator's live state. It is the single authoritative object for:
- what step is currently executing (`current_step`)
- whether progression is blocked and why (`block_state_path`)
- what verification evidence exists (`verification_result_path`)
- what decomposed code functions returned (`dispatch_results[]`)
- what recommendations are pending (`recommendations[]`)

Treat `verification-result.json` as the canonical readiness object — it aggregates all gate outcomes (command checks, simplify, review passes, TDD, PR readiness) into one machine-readable fact.

## Routing table

| Condition | Route | Why |
|-----------|-------|-----|
| code changes detected | `/tdd` first | Enforces RED/GREEN/REFACTOR before simplify/review |
| `/tdd` complete + behavior stable | `/refactor` if simplify flags debt | Cleanup without behavior change |
| code changes + high ambiguity | `/tdd` → `/design_v1.1` | Architecture clarity needed before full TDD |
| planning gap or scope unclear | `/planning` | Decomposition needed before any implementation |
| config/infra only | direct verify → reviews | No TDD needed; skip to quality gates |

## /go auto-invoke chain for code tasks

```
1. /t          → test discovery, populates test-gaps_{run_id}.json
2. /gap        → loads gaps from /t output
3. /tdd        → RED phase (if gaps) or GREEN phase (if scaffolded)
   → /refactor → post-TDD cleanup if simplify flags debt
4. /simplify   → quality gate
5. 7-pass review → correctness, scope, tests, simplicity, regressions, maintainability, pr-ready
```

## Blocking transitions

- `/tdd` fails RED three times → block with `reason_code: verification_failed`
- `/simplify` finds HIGH/CRITICAL → block with `reason_code: simplify_failed`
- review pass returns REVIEW_REQUIRED → block with `reason_code: review_failed`
- max retries exhausted → block with `reason_code: max_attempts_reached`

## Resume semantics

When resuming a blocked run:
1. Read `block-state.json` to understand why blocked
2. Check `block_state.can_retry` — if false, requires user input
3. If `block_state.waiver_allowed`, operator can waive and retry
4. On retry, clear `.blocked_` flag and re-enter at last incomplete step
