# Evidence Tiers and Quality

## Evidence Tiers
Confidence tags: `(Tier [0-4], [0-100]%)`

| Tier | Ceiling | Sources |
|------|---------|---------|
| **Tier 1** | 95% | Execution artifacts, logs, test output, telemetry |
| **Tier 2** | 85% | Official docs, specs, peer-reviewed reference |
| **Tier 3** | 75% | Static analysis, logical derivation, symbols |
| **Tier 4** | 50% | Comments, unverified claims, speculation |

## Rules of Evidence
- **Weakest Link**: Overall confidence cannot exceed the weakest tier in the causal chain.
- **Mixed Tiers**: Ceiling = lowest tier used for a critical claim.
- **No Evidence**: Maximum 50% confidence (Tier 4).
- **Direct Observation**: Tier 1 requires tool output from the *current* turn/session.

## Completeness Criteria
- **Mechanism**: How it fails (log/trace).
- **State**: What the system looked like (state file/DB).
- **Outcome**: The final observable failure (transcript/output).
- **Authority**: The registration/config (settings.json).
