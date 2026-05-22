# Stop/Go Decision Model

Every standard or deep pre-mortem must end with a stop/go decision.

## Decisions

- `GO`: no unresolved CRITICAL/HIGH findings and required validation is complete.
- `GO WITH WATCHPOINTS`: remaining risks are bounded, reversible, monitored, and not expected to invalidate the objective.
- `STATIC ONLY - LIVE VALIDATION REQUIRED`: static review found no blocker, but the objective depends on behavior that static checks cannot prove.
- `NO-GO UNTIL FIXED`: unresolved blocker, data-safety gap, invalid metric risk, missing hard gate, or missing required validation.

## Required Fields

```text
## Stop/Go Decision
Decision:
Reason:
Blocking findings:
Watchpoints:
Required before GO:
```

## Rules

- Missing destructive/live preflight means `NO-GO UNTIL FIXED`.
- Missing required live validation means `STATIC ONLY - LIVE VALIDATION REQUIRED`, not `GO`.
- Unknown evidence strength on a HIGH/CRITICAL finding prevents `GO`.
- A profile-specific invalidation rule overrides generic optimism.
