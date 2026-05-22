# Destructive And Live Preflight

Use this gate before cleanup, deletion, migration, live runs, benchmarks, auth changes, worker orchestration, browser-profile work, or external service operations.

## Required Checklist

- Objective:
- Safe targets:
- Must-not-touch targets:
- Naming or ID convention:
- Auth/session assumption:
- State files involved:
- Cleanup before:
- Cleanup after:
- Rollback path:
- Audit trail:
- Failure behavior if list/parse/auth/validation fails:
- Whether cleanup failure preserves the primary failure:
- Whether the operation affects metrics or benchmark comparability:

## Hard Fail Conditions

Return `NO-GO UNTIL FIXED` if:

- safe targets are title/prefix/glob based with no fail-closed guard;
- must-not-touch resources are undefined;
- list/parse/auth/validation failure does not fail closed;
- rollback is unavailable for low-reversibility changes;
- benchmark comparability can be invalidated without detection;
- cleanup can mask the primary failure context.
