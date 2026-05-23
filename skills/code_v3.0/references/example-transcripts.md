# /build Example Transcripts

## Example: Continue Existing Plan

Input:
`/build continue with the plan`

Expected behavior:
1. Resolve plan source from markdown precedence.
2. Select execution model and announce it.
3. Initialize runtime fingerprint + resume ledger.
4. Resume from first incomplete task.
5. Continue task loop until completion or blocker contract.

## Example: Blocker Contract

Output format:

`BLOCKED: verifier cannot resolve test file path`

`Current task: AT-006 daemon integration`

`Why stopped: verifier attempted /mnt/p/... but runtime is windows (P://...)`

`Needs decision: should I re-run verification using windows path mode now?`

1. Re-run verifier in windows path mode and continue
2. Switch session to WSL path mode and retry
3. Pause for manual environment correction

## Example: Done Claim

Minimum done summary:
- `Tasks complete: 14/14`
- `Skipped tasks: none` (or approved skip list)
- Task-level evidence pointers in ledger
- Final `validate_done_claim.py` = PASS
- Final `validate_skip_governance.py` = PASS
