# Historical Regression Awareness

Pre-mortems should check whether the target resembles failures already seen in the project.

## Required Search

When project history is available, search:

- repo docs under `docs/operations/`;
- recent test registries or benchmark registries;
- handoff/debugging playbooks;
- prior run logs or summarized incidents;
- repo-local pre-mortem profile.

## Output

```text
## Historical Regression Check
Sources checked:
Similar prior failures:
Differences from prior failures:
Regression tests or probes:
Residual risk:
```

## Examples Of Regression Classes

- stale state causing wrong resource selection;
- error strings stored as successful IDs;
- cleanup prefix too broad;
- auth checks in hot paths;
- metrics counted before validity gates;
- resource-health checks blocking on unrelated processes;
- default profile contamination;
- post-run cleanup masking primary failures.
