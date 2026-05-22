# Review Lenses

Use this file to prevent blind spots. A pre-mortem does not need every lens at maximum depth, but it must state which lenses were applied and which were intentionally deferred.

## Core Lenses

- Logic review: wrong branch, inverted condition, impossible state, missing invariant, bad ordering, off-by-one, wrong assumption.
- State-machine review: lifecycle transitions, stale state, resume, retry, partial completion, cleanup, idempotency.
- I/O and validation review: paths, globs, prefixes, parse failures, missing files, external command outputs, malformed input.
- Security and data-safety review: credentials, auth, delete/mutate scope, user-owned resources, injection, fail-closed behavior.
- Performance review: hot-path blocking calls, subprocess churn, N+1 loops, retries, contention, resource saturation.
- Testing review: missing regression tests, mocks hiding risk, static-vs-live coverage, deterministic failure reproduction.
- Compliance/contract review: schemas, plugin manifests, CLI contracts, hook contracts, output format, consumer requirements.
- Quality review: maintainability, package ownership, install/update path, stale compatibility paths, source-of-truth drift.
- RCA/causal-chain review: symptom fixes, missing falsifiers, recurrence risk, observability needed to confirm root cause.
- Observability/tracing review: logs, metrics, spans, stage labels, failure attribution, artifact preservation.

## Required Lens Coverage Output

The final synthesis must include:

- lenses applied;
- lenses skipped or deferred;
- why skipped lenses were safe to skip;
- recommended follow-up if a skipped lens could change the stop/go decision.

## Logic Review Gate

Logic review is mandatory for:

- code changes;
- implementation plans;
- cleanup/deletion/migration work;
- live-run, benchmark, download, auth, or retry logic;
- stateful workflows, resumable workflows, hooks, and worker orchestration.

If `adversarial-logic` is not dispatched for one of those targets, the pre-mortem must state why logic review was not needed.
