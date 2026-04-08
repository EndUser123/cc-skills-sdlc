# /build Quick Checklist

## Start of Run

- Resolve execution model (`single`, `subagents`, `team`, `hybrid`).
- Resolve markdown plan source (`explicit .md` -> `*plan*.md` -> `plan.md`).
- Initialize scoped task list ID (for team/hybrid or multi-terminal).
- Capture runtime fingerprint.
- Initialize resume ledger from plan.

## Per Task

- RED evidence captured.
- GREEN evidence captured.
- REFACTOR evidence captured.
- Independent VERIFY evidence captured.
- Drift + impact checks recorded.
- Ledger updated with status, owner, attempts, evidence.

## Stop Conditions

- If success: auto-continue to next task.
- If blocked: emit blocker contract with one direct decision question.
- If skipping: require `approved_by`, `rationale`, `risk_note`.

## Done Claim

- All markdown plan tasks complete, or explicitly approved skips.
- Done-claim validator passes.
- Skip-governance validator passes.
- Final confidence calibration included.
