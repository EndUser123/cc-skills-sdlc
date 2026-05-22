# Live Probe Planner

When static review cannot prove behavior, produce an executable live-probe plan instead of vague "test this" advice.

## Required Fields

```text
## Live Probe Plan
Probe:
Command or action:
Permission status: authorized | needs permission | not applicable
Expected signal:
State mutation risk:
External service / credential risk:
Cleanup requirement:
Benchmark comparability impact:
Stop condition:
```

## Probe Selection

Prefer the smallest probe that can falsify or validate the risk.

Good probes:

- non-destructive helper import and temporary state creation;
- plugin inventory/cache validation;
- dry-run mode;
- single-item smoke test;
- read-only API/listing check;
- trace review from existing logs.

Avoid by default:

- full live runs;
- external-service mutations;
- quota-consuming operations;
- deletion/cleanup against user resources;
- probes that alter benchmark comparability.
