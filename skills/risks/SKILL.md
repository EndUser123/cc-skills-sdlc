---
name: risks
description: "Fast pessimistic pass on the most recent un-actioned proposal — risks, mitigations, and the explicit boundary of what this pass did not check. Use when you want a quick risks-and-mitigations read without the full /red-team multi-agent review."
argument-hint: "[optional focus domain, e.g., state, concurrency, windows-io]"
allowed-tools: []
disable-model-invocation: true
triggers:
  - /risks
aliases:
  - /risks
enforcement: advisory
depends_on_skills: []
workflow_steps: []
suggest:
  - /red-team
  - /review
---

# /risks — Fast Pessimistic Risk Pass

A single-pass risks-and-mitigations read on the current proposal. Lighter and
faster than `/red-team` (which runs planner → specialists → critic with
multi-agent dispatch). Use `/risks` when you want a quick "what will bite us,
and how do we stop it" in under a minute; escalate to `/red-team` for an
adversarial trust verdict or a deep multi-perspective audit.

Risk-pass on the most recent proposal in context — a design, plan,
implementation approach, or code change that has **not yet been written or
committed**. If several candidates exist, assess the most recent un-actioned
one. **State what you're assessing in the first line** —
`Assessing: <one-line summary>`. If that's not what the user meant, stop and
ask what to assess. If no un-actioned proposal exists, ask what to assess.

If an argument (`$0`) is provided, weight that domain.

## Output

### Risks

No row cap — list every real risk, even if it's seven rows. "Why it bites"
names the **failure mechanism**, not the symptom.

| # | Risk | Why it bites |
|---|------|--------------|

### Mitigations

Numbered list, one-to-one with the risks above. Default to inline
code/instructions — use a fenced code block only when the mitigation is
genuinely a multi-line snippet. If the right answer is architectural, say so;
do not force a narrow code patch when the correct fix is a design change.

### Falsification

For the top risk only: the specific input, state, race, or environment
condition that would bypass the mitigation. How do we prove the fix broke?

### Skipped (escalate to `/red-team` if any of these matter)

- End-to-end trace of adjacent modules or remote state coupling
- Adversarial multi-perspective verification (this is single-pass)
- Deep failure-mode pre-mortem with web research

## When to escalate

This pass is one perspective, no specialist dispatch, no web research. If a
risk crosses into a trust boundary, security surface, or needs a PROCEED /
REVISE / BLOCK verdict, run `/red-team` instead. `/risks` surfaces risks;
`/red-team` adjudicates them.
