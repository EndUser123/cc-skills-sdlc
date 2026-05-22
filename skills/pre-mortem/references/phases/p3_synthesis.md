# Phase 3: Synthesized Refined Critique

Produce a refined version of the critique incorporating specialist findings + meta-critique.

## Input

Read these files:

**Original Work:** `cat "P:\\\\\\{session_dir}/work.md"`
**Phase 1 Specialist Findings:** `cat "P:\\\\\\{session_dir}/p1_findings.md"`
**Phase 2 Meta-Critique:** `cat "P:\\\\\\{session_dir}/p2.md"`

## Verification Step (MANDATORY) — P1 #5

**Methodology:** Before writing any findings, re-read the original source files and verify every claim in Phase 1/2 outputs against what the work actually says or does. Specifically:

- If a finding claims the work does X but it actually does Y, correct the finding
- If a finding claims the work doesn't do Z but it does, remove or downgrade that finding
- If a finding references a file but the relevant behavior is in a different file, update the citation
- Do not accept Phase 1/2 output as ground truth

**Spot-check rule:** Pick 3 file:line citations from Phase 1/2 output and verify they exist at the claimed location. If a citation is wrong, treat all citations from that specialist as suspect.

## Output Schema

Render markdown properly — use headings, bold, italic, etc. Do NOT show raw syntax like `**bold**`.

Return the refined critique in this structure:

```
## Intent Summary
[2-3 sentences: what this work is trying to achieve]

## Health Score: XX%
[Brief assessment — Healthy ≥80%, Warning 50-79%, Critical <50%]

## Project Profile Applied
[profile path from Phase 1 or none found]

## Missing Profile Sections
[Missing profile sections from Phase 1 and whether each affects the stop/go decision.]

## Logical Gaps & Inconsistencies
[Sorted by severity: CRITICAL, HIGH, MEDIUM, LOW]
1.1. [HIGH] issue description (source: specialist-name, file:line)
1.2. [MEDIUM] issue description

## Hidden Assumptions & Fragile Dependencies
2.1. [MEDIUM] issue description (source: specialist-name)

## Investigation Coverage
[State what was checked statically, what was observed through non-static validation, and what live/plugin/runtime probes are still recommended.]

## Static Test Coverage
[State which static tests/checks cover the findings, which are missing, and which risks cannot be proven statically.]

## Review Lens Coverage
[List review lenses applied, skipped/deferred lenses, and whether any skipped lens could change the stop/go decision.]

If a mandatory lens from `references/review-lenses.md` was skipped and could change the stop/go decision, mark it as a blocking finding and set Stop/Go Decision to `NO-GO UNTIL FIXED`.

## Finding Synthesis
[Cluster duplicate findings by shared failure mode before listing recommendations. For each HIGH or CRITICAL finding, include Evidence Strength, Falsifier, and Wrong-Order Risk.]

Evidence Strength: Observed | Inferred | Unverified | Requires live validation

Falsifier: [the smallest check, trace, test, or live probe that would disprove the finding]

Wrong-Order Risk: [what breaks or becomes misleading if the recommendation is executed before prerequisite fixes or probes]

## Live Probe Plan
[Exact command/action, expected signal, permission status, mutation risk, cleanup requirement, and whether the probe preserves comparison validity.]

## Historical Regression Check
[Sources checked, similar prior failures found, what differs now, regression tests/probes required, and residual risk.]

## Stop/Go Decision
Decision: GO | GO WITH WATCHPOINTS | STATIC ONLY - LIVE VALIDATION REQUIRED | NO-GO UNTIL FIXED

Reason: [short rationale]

Blocking findings: [items that prevent GO]

Watchpoints: [items allowed only with active monitoring]

Required before GO: [minimal checks or fixes needed]

## Missing Obvious Actions / Best Practices
3.1. [HIGH] issue description (source: specialist-name)

## Risks and Edge Cases
4.1. [MEDIUM] issue description (source: specialist-name)

## Concrete Recommendations
5.1. [MEDIUM] specific change (source: specialist-name)

## Open Questions / Unknowns
6.1. [LOW] uncertainty (source: specialist-name)

## Recommended Next Steps

Organize by domain using the 7 sections as domains. Severity is implied by domain order (domain 1 = most critical). Within each domain, sort sub-items by severity: CRITICAL > HIGH > MEDIUM > LOW.

Do NOT format these as RNS — output them as plain structured text. RNS format is applied by the `/rns` skill as a separate transformation step.

**Output as plain structured text:**
- Domain name and brief description
- Numbered sub-items with action, method, and context
- No specific format requirements — RNS consumes this regardless of formatting
