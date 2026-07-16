---
name: risks
description: "Fast pessimistic pass on the most recent un-actioned proposal — risks, grounded mitigations, and a meta-critique of the findings themselves. Use when you want a risks + actionable next-steps read in under a minute; escalate to /red-team for a trust verdict or multi-perspective audit."
argument-hint: "[optional focus domain, e.g., state, concurrency, windows-io]"
allowed-tools: []
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
findings themselves.

**Positioning vs siblings** (each does a different job — pick the right one):
`/skeptic` validates AI output; `/review` produces file:line findings; `/improve`
improves a concrete artifact; `/red-team` adjudicates trust with multi-agent
specialist dispatch. `/risks` is the fast **pre-commitment** pessimistic read —
single-pass, no dispatch, structured risks + a meta-critique, in roughly
30–90 seconds.

This skill is independent of, but compatible with, the proposal-critique-gate
Stop hook (any `/risks` output that recommends an action is still checked by
that gate for a self-critique) and with `/red-team`. `/risks` may recommend a
follow-up skill, but it never invokes or auto-routes to one; the user decides
whether to continue.

## Lookback rule

Risk-pass on the most recent **un-actioned** proposal in context.

**"Un-actioned" = proposed in prose this session, but not yet written or
committed.** If the most recent thing the user raised is already implemented
or already shipped, do not silently relabel it as an un-actioned proposal. If
the user explicitly asks to assess the implementation, assess the implemented
artifact and label it as such; otherwise say so in the first line and ask what
to assess. If several un-actioned candidates exist, assess the most recent one.

**State what you're assessing in the first line** — `Assessing: <one-line
summary>`. Include `state: un-actioned proposal` or `state: implemented
artifact` when relevant. If that's not what the user meant, stop and ask. If
no target exists, ask what to assess.

If `$0` is provided, weight that domain in every section.

## Always-consider lenses

Fire these two lenses regardless of `$0`. They catch the failure modes users
forget to ask about.

| Lens | What it catches |
|---|---|
| **Reversibility** | What's the blast radius if this ships broken? Cheap to undo vs. entrenched? |
| **Operational safety** | Does this touch hook wiring, plugin mutation, file deletion, permissions, state files, or cross-terminal scope? |

If a proposal touches none of a lens's surfaces, mark that lens **N/A** and
move on — don't manufacture risks to fill it. Add lenses the user explicitly
requested via `$0` (e.g., `state`, `concurrency`, `windows-io`, `security`).

## Anti-patterns to avoid

(The other failure modes — restating the proposal as a risk, recommending
without grounding, bare inventories — are already enforced by the
proposal-critique-gate and Stop unverified-stance hooks. These two are the
ones the hooks *cannot* catch because they're internal to this pass.)

- **Don't invent the synthesis.** The Bottom Line is grounded by the Risks + Findings Review sections beneath it. If they don't support it, the Bottom Line isn't earned — rewrite it, don't back-fill weak risks to match it.
- **Don't re-derive the proposal.** Assess it. The user already wrote it.

## Output structure

Write the sections in order **except Bottom Line** — draft Bottom Line *after*
Findings Review, then place it first in the output. The verdict is earned by
the analysis beneath it, not the other way around.

Each section is required; an empty section means the pass failed.

### Bottom Line

One sentence. The single highest-leverage move — "ship X + Y together; skip
Z" or "this is sound, no blockers found" or "escalate to `/red-team` because
trust boundary." No preamble. Scannable in one second. (Written last, placed
first — see Output structure.)

### Risks

Markdown table. List every real risk. "Why it bites" names the failure
mechanism, not the symptom.

| # | Risk | Why it bites |
|---|------|--------------|

**Mechanism rule (not a count gate):** cut any row whose "Why it bites"
cannot name a concrete failure mechanism; add a row whenever a named mechanism
exists, regardless of count. Rule-of-thumb only: if you've listed seven,
pressure-test the weakest two; if you've listed fewer than three on a
non-trivial proposal, push harder on the always-consider lenses. These numbers
are heuristics, not authority — no corpus backs them.

### Mitigations

Numbered list, one-to-one with the Risks above. Inline code/instructions by
default — use a fenced code block only when the mitigation is genuinely a
multi-line snippet. If the right answer is architectural, say so; don't force
a narrow code patch when the correct fix is a design change.

### Findings Review

**Critically review the Risks and Mitigations above.** High-leverage when
present; best-effort if skipped — if you skip it, note the skip in Bottom Line
so the user knows the meta-critique didn't run.

- Which risks are real vs. theater? Mark the theater ones for removal.
- Which mitigations actually address the failure mechanism vs. just look
  reassuring? Mark the weak ones.
- Across the real risks, what's the single highest-leverage move? Often it's
  not the first row of the table.
- Did enumerating risks surface a **meta-risk** — e.g., "the proposed fix is
  itself the failure mode," or "we're mitigating the symptom while the root
  cause persists"? Name it here.

### Boundary Classification

Before writing the Escalation Recommendation, classify each surface below as
`YES`, `NO`, or `UNKNOWN`, and give one evidence-backed reason. `UNKNOWN` is
not equivalent to `NO`.

| Surface | Classification | Evidence / reason |
|---|---|---|
| Shared artifact with multiple producers or consumers | | |
| Hook, gate, plugin, workflow, routing, or runtime behavior | | |
| Persisted state, concurrency, crash recovery, or cross-terminal scope | | |
| Producer/consumer or cross-component contract | | |
| Security, permissions, prompt injection, or trust boundary | | |
| Irreversible action or high blast radius | | |

Treat a shared registry, manifest, event stream, cache, or state file with
multiple readers as a shared artifact and a cross-component contract unless
repo evidence proves otherwise. Do not infer consumer safety merely because a
serialization format permits unknown fields; assess the consumers' actual
field access and behavior.

### Falsification

**Design the verification the user would run** for the highest-leverage risk
only: the specific input, state, race, or environment condition that would
bypass the mitigation, and how you'd prove the fix broke. This is verification
*design* —
running it is the user's responsibility (this skill has no tools and runs
nothing).

### Escalation Recommendation

This section is mandatory and must appear in every pass. Choose exactly one:

`Decision: RUN /red-team` | `Decision: NO /red-team NEEDED` |
`Decision: UNCERTAIN — RUN /red-team`

Recommend `RUN /red-team` when at least one concrete trigger applies:

- security, authentication, secrets, permissions, or prompt-injection boundary;
- hook, gate, workflow, routing, plugin, or runtime behavior where trust,
  bypass, or promotion semantics are at issue;
- persisted state, concurrency, crash recovery, or cross-terminal scope;
- producer/consumer or other cross-component contract;
- irreversible or high-blast-radius behavior;
- a material finding whose resolution needs a `PROCEED`, `REVISE`, or `BLOCK`
  trust verdict; or
- the pass cannot determine whether one of these conditions applies.

Recommend `NO /red-team NEEDED` only for a bounded, local, reversible change
with no shared state, trust boundary, routing behavior, or cross-component
contract. A `YES` or `UNKNOWN` in any Boundary Classification row blocks this
decision unless a different follow-up skill fully owns the concern; in that
case use `NO /red-team NEEDED` and name that skill in `Follow-up:` with a
concrete reason.

If another skill is the better follow-up, name it instead of `/red-team`:
`/claude-audit` for hook/runtime wiring, `/skill-audit` for capability or
consolidation claims, and `/review` for routine file:line code review.

Include all three fields beneath the decision:

- `Reason:` one sentence tied to the proposal;
- `Triggers:` the concrete triggers found, or `none`;
- `Checks not performed:` the relevant skipped checks;
- `Follow-up:` `/red-team`, `/claude-audit`, `/skill-audit`, `/review`, or
  `none` (skill name only);
- `Operational next step:` a concrete implementation or validation action, or
  `none`.

Use `Decision: NO /red-team NEEDED` when another follow-up is sufficient, and
record that skill in `Follow-up:`. Do not force every escalation through
`/red-team`.

This is a recommendation only. Do not invoke another skill, claim that an
escalation occurred, or treat the recommendation as a verdict.

### Evidence discipline

- Separate observed facts, inferences, and hypotheses. Label them when they
  affect the decision.
- Do not claim that a change is deployed, accepted, tested, backward-compatible,
  or working without naming the evidence that establishes it.
- Do not label a risk `theater` merely because a default avoids a crash or a
  parser ignores unknown fields. A risk is theater only when the stated
  failure mechanism is disproved by relevant producer/consumer evidence;
  otherwise retain it as real or unresolved.
- Every `theater` dismissal must name the disproving evidence in Findings
  Review. Unsupported dismissals are findings, not conclusions.

### Knowledge / Validation Coverage

If a plan, design, or implementation claim is being assessed, inspect its
compact Knowledge / Validation section and Change Record when present. Report:

- `Used:` sources and checks with evidence;
- `Not used:` named sources or checks explicitly marked `no`;
- `Unverified:` claimed sources, checks, or changelog entries without
  supporting artifacts; and
- `Material gap:` whether the missing provenance changes the risk or decision.

Do not infer source use from a changelog mention alone. If the artifact claims
research, testing, deployment, acceptance, or validation but has no ledger or
dated Change Record, treat that as an evidence gap and include it in the
escalation decision when material.

### Skipped (report honestly; do not auto-route)

- End-to-end trace of adjacent modules or remote state coupling
- Adversarial multi-perspective verification (this is single-pass)
- Deep failure-mode pre-mortem with web research
- Trust verdict on a security boundary

Use the skipped checks to justify the Escalation Recommendation. Do not make
the presence of a skipped check an automatic escalation by itself: explain
whether it is material to this proposal. If material, recommend the
appropriate follow-up and still deliver the bounded `/risks` result.

## Worked example (illustrative — the structure, not the domain, is the template)

**Bottom Line**: Ship M1 (the hook) + M3 (single-source to CLAUDE.md
Recommendation Rule). Skip M4 (vague reversibility threshold) — fold the
exemption list into M3 instead of a separate rule.

**Risks** (excerpt):

| # | Risk | Why it bites |
|---|------|--------------|
| 1 | Author-as-verifier recurs despite the rule — prose at the review layer doesn't constrain model output, only the surface looks compliant | Same C2 substitution the fix is meant to close: legitimate-feeling prose substitutes for the deliverable property |
| 2 | "Verifier line" decays into boilerplate — model writes the right string with an invented corpus | Same shape as STATUS: TESTED_IN_ENV labels the Stop hook has been pushing back on |

**Mitigations** (excerpt):

1. Convert the rule from prose-into-prompt to artifact-check-on-output: extend the Stop aggregator to require a `verifier:` line with three non-empty fields (model, corpus, threshold) on matches of "validated", "wire it", "no residuals", "verified". Start WARN-only; promote to BLOCK only after measuring real non-zero discrimination on a held-out corpus (no fixed N — gate-discrimination requires measured TP/FP, not a magic count).
2. Rotate the verifier model — the same model cannot be reused across N consecutive sessions for the same author.

**Findings Review**: The "convert to artifact-check" mitigation (M1) collapses R1, R2, R4, R6 at the structural level. M2 (verifier rotation) is cheap and addresses R3. The narrative-form rule is itself the failure mode — shipping prose without the hook is exactly the trap the rule is meant to close.

**Falsification** (R1): Author writes "This validates the mechanism" with a `verifier:` field filled with "self" or an empty corpus. If >10% of self-claims pass the gate, the hook is theater.

**Skipped**: cross-session metric design for verifier reuse — needs a place to record per-session verifier identity. Escalate if reusing the same verifier becomes a recurring pattern.

---

## Escalation

`/risks` surfaces risks and recommends the next review; `/red-team` adjudicates
trust when the user chooses to run it. Never write "route," "run," or "escalate
to" as though the follow-up already happened. Say `recommend RUN /red-team`
or `recommend NO /red-team NEEDED` instead.
