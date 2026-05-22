# Finding Synthesis

Synthesis should reduce noise and improve actionability.

## Deduplication And Clustering

Cluster findings by failure mode, not by file or specialist.

For each cluster, state:

- failure mode;
- affected files/components;
- contributing specialists;
- highest justified severity;
- evidence strength;
- recommended fix;
- validation or falsifier.

## Evidence Strength Labels

Each HIGH/CRITICAL finding must include one of:

- `Observed`: directly seen in source, logs, command output, trace, or artifact.
- `Inferred`: follows from observed evidence but not directly executed.
- `Unverified`: plausible but not currently supported enough for action.
- `Requires live validation`: cannot be decided statically.

## Falsifiers

Every HIGH/CRITICAL finding must include:

```text
Falsifier: this finding is wrong or downgraded if <specific command/artifact/trace> shows <specific result>.
```

Findings without falsifiers are weaker and should not be used as sole blockers unless the risk is data loss, security, or irreversible live operation.

## Wrong-Order Risk

Flag recommendations that become dangerous or misleading if applied too early, too late, or before prerequisite validation.
