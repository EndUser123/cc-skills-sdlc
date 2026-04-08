# /build Troubleshooting

## Path Translation Error (`P:\` vs `/mnt/p/`)

Symptoms:
- Verifier cannot find files that builder just modified.
- Commands pass in one runtime and fail in another.

Actions:
1. Run `runtime_fingerprint.py` and confirm `path_mode`.
2. Normalize all command paths to the active mode.
3. Re-run only the failed verification step with normalized paths.

## Silent Stop After RED/GREEN

Symptoms:
- Agent says task is done after partial TDD cycle.
- Build pauses without blocker contract.

Actions:
1. Mark task `blocked` in ledger.
2. Re-run task with explicit completion guard (`red+green+refactor+verify`).
3. Continue automatically after pass; do not wait for user input.

## Multi-Terminal Collisions

Symptoms:
- Two sessions edit same task simultaneously.
- Ownership in task list is ambiguous.

Actions:
1. Use scoped task list ID per run.
2. Require explicit owner before `in_progress`.
3. If owner mismatch is detected, stop duplicate execution and ask lead for reassignment.

## Done-Claim Fails

Symptoms:
- `validate_done_claim.py` returns `FAIL`.

Actions:
1. Read missing evidence lines from output.
2. Update ledger evidence pointers for missing fields.
3. Re-run validator before any "done" response.
