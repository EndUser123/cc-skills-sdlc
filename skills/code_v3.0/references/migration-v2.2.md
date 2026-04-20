# Migration Notes to /build v2.2.x

## What Changed

- `/build` no longer prompts for git worktree during run startup.
- Execution model is explicit (`single`, `subagents`, `team`, `hybrid`).
- Plan resolution is markdown-first; JSON plan artifacts are metadata only.
- Resume ledger and runtime fingerprint are mandatory.
- Done-claim and skip-governance checks are executable via scripts.

## Operational Changes

- Use scripted ledger updates instead of ad-hoc status text.
- Treat health check as readiness only, not pass/fail test totals.
- Enforce blocker contract whenever stopping before full completion.

## New Scripts

- `scripts/runtime_fingerprint.py`
- `scripts/update_resume_ledger.py`
- `scripts/validate_phase_transition.py`
- `scripts/validate_skip_governance.py`
- `scripts/validate_done_claim.py`

## Adoption Sequence

1. Capture runtime fingerprint in BOOTSTRAP.
2. Initialize ledger before BUILD.
3. Update ledger on every task transition.
4. Run done/skip validators before claiming completion.
