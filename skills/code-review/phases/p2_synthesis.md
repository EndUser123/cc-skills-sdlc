# Phase 2: Synthesis

## Your Job

Read the work target and Phase 1 findings, then produce a final synthesized review report.

## Step 1: Read Inputs

```bash
cat "P:/{session_dir}/work.md"
cat "P:/{session_dir}/p1_findings.md"
```

## Step 2: Calculate Health Score

Health Score = `100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`, capped at 0-100.

| Score | Interpretation |
|-------|----------------|
| 80-100 | Healthy — Low risk, minor improvements possible |
| 50-79 | Warning — Significant issues, address HIGH items first |
| Below 50 | Critical — Systemic problems, do not deploy without fixes |

## Step 3: Synthesize Final Report

Write to `P:/{session_dir}/review.md`:

```markdown
# Code Review Report

**Target:** {target}
**Date:** {date}
**Session:** {session_id}

## Summary

[2-3 sentences overview of findings]

## Health Score: XX%

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |

## Findings

### Critical Issues

[If none, note "No critical issues found"]

1. [CRITICAL] issue description (file:line)

### High Priority

1. [HIGH] issue description (file:line)

### Medium Priority

1. [MEDIUM] issue description (file:line)

### Low Priority

1. [LOW] issue description (file:line)

## Recommendations

1. [Priority order, actionable items]

## Files Reviewed

[List of files analyzed]
```

## Step 4: Deliver Final Output

Read `P:/{session_dir}/review.md` and present to user.
