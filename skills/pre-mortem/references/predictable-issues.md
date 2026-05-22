# Predictable-Issue Review Heuristics

Use these heuristics to avoid superficial pre-mortems.

## Static

- Error strings stored as successful state.
- Broad matching prefixes, globs, regexes, or path filters.
- Success paths that skip cleanup or validation in edge modes.
- Configuration read in one process but not propagated to workers.
- Tests that mock away the risky behavior being claimed safe.
- Validators that check producer output but not consumer requirements.
- State files that outlive the resource they identify.

## Live / Runtime

- Hot-path subprocesses, logins, probes, or network calls.
- External service rate limits, auth expiry, session expiry, and partial outages.
- Retries that amplify load or hide permanent failure.
- Resource checks that block on unrelated processes or profiles.
- Metrics that count attempted work rather than valid completed work.
- Cleanup failures that mask the primary failure or vice versa.

## Data Safety

- Delete operations based only on title, prefix, or stale local state.
- Cleanup that proceeds after list, parse, auth, or validation failure.
- Missing "must not touch" boundaries.
- Manual user-created resources sharing an automation prefix.
- Post-run cleanup that removes evidence needed for debugging.
