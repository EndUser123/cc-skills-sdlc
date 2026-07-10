---
name: risks
description: "Fast pessimistic pass on the most recent un-actioned proposal — risks, grounded mitigations, and a meta-critique of the findings themselves. Use when you want a risks + actionable next-steps read in under a minute; escalate to /red-team for a trust verdict or multi-perspective audit."
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

A single-pass risks-and-mitigations read with a built-in critique of the
findings themselves. Faster than `/red-team` (no specialist dispatch, no
multi-agent critic). Use `/risks` when you want "what will bite us, how do
we stop it, and what's the highest-leverage move" in roughly 30–90 seconds.

This skill complements, not replaces, `/red-team` and the proposal-critique-gate
Stop hook. `/risks` structures the pass; the hook enforces that a pass happens;
`/red-team` adjudicates trust when stakes justify multi-perspective cost.

## Lookback rule

Risk-pass on the most recent un-actioned proposal in context — a design, plan,
implementation approach, or code change that has **not yet been written or
committed**. If several candidates exist, assess the most recent un-actioned
one.

**State what you're assessing in the first line** — `Assessing: <one-line
summary>`. If that's not what the user meant, stop and ask. If no un-actioned
proposal exists, ask what to assess.

If `$0` is provided, weight that domain in every section.

## Always-consider lenses

Fire these two lenses regardless of `$0`. They're your highest-frequency
failure modes and shouldn't depend on the user remembering to ask.

| Lens | What it catches |
|---|---|
| **Reversibility** | What's the blast radius if this ships broken? Cheap to undo vs. entrenched? |
| **Operational safety** | Does this touch hook wiring, plugin mutation, file deletion, permissions, state files, or cross-terminal scope? |

Add lenses the user explicitly requested via `$0` (e.g., `state`, `concurrency`,
`windows-io`, `security`).

## Anti-patterns to avoid

- **Don't restate the proposal as a risk.** "This changes the auth flow" is not a risk; "the new auth flow races with the existing refresh on logout" is.
- **Don't enumerate speculative risks without a failure mechanism.** If you can't name why it bites, cut the row.
- **Don't recommend without grounding.** A mitigation you can't connect to a specific risk isn't a mitigation — it's a wish.
- **Don't invent the synthesis.** The Action section is grounded by the Risks + Findings Review sections. If they don't support it, the Action isn't earned.
- **Don't produce a bare inventory with no Action.** "Here are 6 risks, mitigate each" with no judgment of which to act on first is a dodge, not a pass.
- **Don't re-derive the proposal.** Assess it. The user already wrote it.

## Output structure

In this order. Each section is required; an empty section means the pass failed.

### Bottom Line

One sentence. The single highest-leverage move — "ship X + Y together; skip
Z" or "this is sound, no blockers found" or "escalate to `/red-team` because
trust boundary." No preamble. Scannable in one second.

### Risks

Markdown table. **No row cap** — list every real risk, even if it's seven
rows. "Why it bites" names the failure mechanism, not the symptom.

| # | Risk | Why it bites |
|---|------|--------------|

Calibration: **≥7 risks usually means you're speculating** — cut the weakest
two. **<3 risks on a non-trivial proposal usually means you're sandbagging** —
push harder on the always-consider lenses.

### Mitigations

Numbered list, one-to-one with the Risks above. Inline code/instructions by
default — use a fenced code block only when the mitigation is genuinely a
multi-line snippet. If the right answer is architectural, say so; don't force
a narrow code patch when the correct fix is a design change.

### Findings Review

**Critically review the Risks and Mitigations above.** This is the most
valuable section — do not skip it.

- Which risks are real vs. theater? Mark the theater ones for removal.
- Which mitigations actually address the failure mechanism vs. just look
  reassuring? Mark the weak ones.
- Across the real risks, what's the single highest-leverage move? Often it's
  not the first row of the table.
- Did enumerating risks surface a **meta-risk** — e.g., "the proposed fix is
  itself the failure mode," or "we're mitigating the symptom while the root
  cause persists"? Name it here.

### Falsification

For the **top risk** only: the specific input, state, race, or environment
condition that would bypass the mitigation. How do we prove the fix broke?

### Skipped (escalate to `/red-team` if any of these matter)

- End-to-end trace of adjacent modules or remote state coupling
- Adversarial multi-perspective verification (this is single-pass)
- Deep failure-mode pre-mortem with web research
- Trust verdict on a security boundary

## Worked example (target shape)

**Bottom Line**: Ship M1 (the hook) + M3 (single-source to CLAUDE.md
Recommendation Rule). Skip M4 (vague reversibility threshold) — fold the
exemption list into M3 instead of a separate rule.

**Risks** (excerpt):

| # | Risk | Why it bites |
|---|------|--------------|
| 1 | Author-as-verifier recurs despite the rule — prose at the review layer doesn't constrain model output, only the surface looks compliant | Same C2 substitution the fix is meant to close: legitimate-feeling prose substitutes for the deliverable property |
| 2 | "Verifier line" decays into boilerplate — model writes the right string with an invented corpus | Same shape as STATUS: TESTED_IN_ENV labels the Stop hook has been pushing back on |

**Mitigations** (excerpt):

1. Convert the rule from prose-into-prompt to artifact-check-on-output: extend the Stop aggregator to require a `verifier:` line with three non-empty fields (model, corpus, threshold) on matches of "validated", "wire it", "no residuals", "verified". WARN first; promote to BLOCK after ≥3 non-discrimination cases measured per the gate-discrimination rule.
2. Rotate the verifier model — the same model cannot be reused across N consecutive sessions for the same author.

**Findings Review**: The "convert to artifact-check" mitigation (M1) collapses R1, R2, R4, R6 at the structural level. M2 (verifier rotation) is cheap and addresses R3. The narrative-form rule is itself the failure mode — shipping prose without the hook is exactly the trap the rule is meant to close.

**Falsification** (R1): Author writes "This validates the mechanism" with a `verifier:` field filled with "self" or an empty corpus. If >10% of self-claims pass the gate, the hook is theater.

**Skipped**: cross-session metric design for verifier reuse — needs a place to record per-session verifier identity. Escalate if reusing the same verifier becomes a recurring pattern.

---

## Escalation

If the proposal crosses a trust boundary (auth, secrets, security surface)
**or** any single finding would warrant a PROCEED/REVISE/BLOCK verdict, run
`/red-team` instead. `/risks` surfaces risks; `/red-team` adjudicates them.
