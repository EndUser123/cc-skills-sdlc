# Phase 3: Synthesized Refined Critique

Produce a refined version of the critique incorporating specialist findings + meta-critique.

## Input

Read these files:

**Original Work:** `cat "P:/{session_dir}/work.md"`
**Phase 1 Specialist Findings:** `cat "P:/{session_dir}/p1_findings.md"`
**Phase 2 Meta-Critique:** `cat "P:/{session_dir}/p2.md"`

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

## Logical Gaps & Inconsistencies
[Sorted by severity: CRITICAL, HIGH, MEDIUM, LOW]
1.1. [HIGH] issue description (source: specialist-name, file:line)
1.2. [MEDIUM] issue description

## Hidden Assumptions & Fragile Dependencies
2.1. [MEDIUM] issue description (source: specialist-name)

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
