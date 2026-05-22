# Output Contract

Use this contract for final pre-mortem output unless an adapter defines a stricter format.

## Required Sections

1. Intent Summary
2. Health Score
3. Hidden Assumptions and Fragile Dependencies
4. Missing Obvious Actions / Best Practices
5. Risks and Edge Cases
6. Concrete Recommendations
7. Open Questions / Unknowns
8. Recommended Next Steps

## Severity

Use severity tags for findings:

- CRITICAL: likely data loss, security issue, invalid live run, irreversible operation, or broken core contract.
- HIGH: likely functional failure, invalid metric, wrong target, missing hard gate, or repeatable runtime failure.
- MEDIUM: plausible failure or maintenance risk with bounded blast radius.
- LOW: clarity, polish, documentation, or minor robustness improvement.

Health score is:

`100 - (CRITICAL*20 + HIGH*10 + MEDIUM*5 + LOW*2)`, capped to the range 0-100.

## RNS Recommended Next Steps

Recommended next steps must use the RNS / GTO-compatible structure:

```text
1 (DOMAIN) - Brief domain description
  1a: Action -> Manual - context (file:line)
  1b: Action -> Use /skill - context

2 (DOMAIN) - Brief domain description
  2a: Action -> Manual - context

0 - Do ALL Recommended Next Steps
```

Requirements:

- Domain headers use `1 (DOMAIN) - description`.
- Sub-items use `1a:`, `1b:`, `2a:`, etc.
- Sub-items do not need severity tags; severity is implied by domain order.
- Do not include vague "consider" recommendations when the next action is knowable.
- Distinguish direct evidence from inference.

## "0" Directive Scope

In Claude Code, `0 - Do ALL Recommended Next Steps` is an execution directive inside the pre-mortem workflow.

Adapters for environments without that convention must not treat `0` as implicit permission to perform destructive, irreversible, credential, or external-service operations. Those adapters must follow their environment's confirmation and tool-use rules.
