# Investigation Types

Pre-mortems must separate static investigation from non-static investigation. Do not blur "we inspected the code" with "we observed the system running."

## Static Investigation

Static investigation is read-only analysis of artifacts that already exist.

Examples:

- source code, tests, scripts, configs, manifests, docs, plans, and schemas;
- existing logs, traces, benchmark outputs, and artifacts;
- git diffs, file layout, dependency references, and naming conventions;
- saved browser or service state files without launching the service.

Static investigation can identify predictable failures without mutating state or contacting external services.

Required output:

- finding;
- evidence path or artifact;
- inference boundary when behavior is not directly proven;
- static verification that would strengthen or falsify the finding.

## Non-Static Investigation

Non-static investigation observes or exercises a system beyond existing artifacts.

Examples:

- running tests, scripts, smoke checks, benchmarks, or profilers;
- launching browsers, subprocesses, servers, workers, or agents;
- calling external services or authenticated CLIs;
- probing NotebookLM, APIs, auth state, network behavior, resource pressure, or live traces;
- creating, mutating, or deleting files, notebooks, caches, profiles, or other state.

Non-static investigation can validate runtime behavior, but it can also consume quota, alter state, invalidate benchmarks, or affect user resources.

Required output:

- exact command or action proposed/performed;
- expected signal;
- state mutation risk;
- external-service or credential risk;
- rollback or cleanup requirement;
- whether the result is safe to compare against prior runs.

## Permission Boundary

Static investigation is the default.

Non-static investigation requires explicit user permission when it would:

- modify local or remote state;
- contact authenticated or external services;
- create/delete/mutate user-visible resources;
- start live benchmark/trial/download work;
- consume meaningful quota, cost, or time;
- disrupt unrelated processes.

If non-static investigation is useful but not authorized, report it as "Recommended live probe" with the exact command/action and why it matters.

## Trace / Live-Run Review

When reviewing live traces or run outputs, distinguish:

- setup/preflight;
- hot path;
- retry/recovery;
- cleanup/postflight;
- metric aggregation;
- artifact preservation.

For throughput and benchmark work, state whether the evidence validates:

- functional correctness;
- throughput/VPH;
- stability over time;
- clean environment assumptions;
- cleanup before and after;
- comparability with prior runs.
