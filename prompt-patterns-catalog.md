# Prompt Patterns Catalog

Sourced from:
- `C:\Users\brsth\Downloads\We are working in claude code on windows 11, with (2).md` (windows-11 transcript)
- `C:\Users\brsth\Downloads\You are reviewing an architecture decision record.md` (ADR transcript)

Each card: **name → source → exact text/reference → applicable phase → reusability → known gaps it closes.**

---

## P1 — [FACT]/[INFERENCE]/[RECOMMENDATION] Evidence Contract

**Source:** both transcripts (windows-11 lines 339–465, ADR throughout)

**What it is:** Structured output format requiring every verification finding to be tagged:

```
[FACT]  <observable event or data — file path, line number, command output>
[INFERENCE]  <what the fact implies — causal chain, alignment, or deviation>
[RECOMMENDATION]  <what to do about it — action, fix, or next step>
```

**Why it matters:** Evidence-tier tracing makes review findings auditable — every claim traces to a specific tool run or file. Without it, findings float as unsupported opinions.

**Applies to:**
- `verify-task.py` — per-command result blocks (already implemented)
- `review-passes.py` — per-finding output
- Gap detection output

**Reusability:** HIGH — domain-agnostic; any skill that produces findings should use it.

**Falsification condition:** This would be wrong if the format is applied mechanically without actual evidence behind each `[FACT]` tag (label inflation). Mitigated by requiring file paths or command output in each fact.

**Closes gap:** Unstructured verification output makes findings un-auditable. P1 adds traceability.

---

## P2 — Adversarial Break-Case Enumeration

**Source:** windows-11 transcript (lines 5849–5871)

**What it is:** Five explicit cases the reviewer must check for in the scope pass:

| Case | Description |
|------|-------------|
| `pure-plan-only` | Plan-mode output with no concrete deliverable |
| `fake-plan-analytical` | Wrapped analytical content posing as plan output |
| `marker-camouflage` | Rationale markers used without actual reasoning |
| `rationalale-camouflage` | Explanatory language hiding a no-op or stub |
| `minimal-malformed-plan` | Plan token present but content is trivial or incomplete |

**Applies to:** `review-passes.py` — scope pass (already implemented for `depth=full`)

**Reusability:** HIGH — pattern is domain-agnostic; any LLM output review pass should check these.

**Falsification condition:** This would be wrong if the checklist is treated as a rubber stamp — all unchecked. Mitigated by requiring checkbox status in pass output.

**Closes gap:** `review-passes.py` scope pass had no explicit anti-patterns to check against. P2 makes the scope pass adversarial rather than merely checklist-based.

---

## P3 — Gap → Opportunity 6-Dimension Scan

**Source:** ADR transcript (lines 401–512)

**What it is:** Six dimensions for scanning a spec/design for missed value:

1. **Hook lifecycle usage** — PreToolUse, Stop, UserPromptSubmit
2. **User experience & control** — bypass modes, enhancement levels
3. **Learning & adaptation** — data-driven improvement, feedback loops
4. **Safety & policy** — lightweight guardrails
5. **Composability & reuse** — API generalizability
6. **Framework & tooling** — library standardization

**Applies to:** `verify-task.py` — pre-verification scope drift check (already implemented), could also seed a standalone gap-discovery step before STEP 3.

**Reusability:** HIGH — generalizes to any architecture document, ADR, or skill spec.

**Falsification condition:** This would be wrong if every spec scores high on all 6 dimensions (everything looks like an opportunity). Mitigated by requiring explicit "does not apply" reasoning per dimension.

**Closes gap:** Verification commands only check what was specified, not what was underspecified. P3 catches spec gaps before they become implementation gaps.

---

## P4 — Evidence Requirement Framing

**Source:** both transcripts — windows-11 lines 2605–2694, ADR forensic review

**What it is:** Per-finding citation requirement:

```
For each finding:
  Where:    file path(s), function/class names, key code snippets
  What:     what it does in practice
  How:      how it aligns or misaligns with the spec
  Surprises: unexpected deviations
```

**Applies to:** `review-passes.py` — findings sections for all 7 passes. Could be added as a required format section.

**Reusability:** HIGH — domain-agnostic; any code review or gap analysis.

**Falsification condition:** This would be wrong if findings cite non-specific locations ("the function in that file"). Mitigated by requiring exact function names or line numbers.

**Closes gap:** Review findings are often vague ("looks complicated", "could be simplified"). P4 makes every finding cite specific evidence.

---

## P5 — Forensic Architecture Review Matrix

**Source:** ADR transcript (lines 523–600)

**What it is:** ADR-vs-reality comparison table:

| Design Element | ADR Intent | Observed Implementation | Status | Notes |
|---|---|---|---|---|
| ... | ... | ... | match/partial/mismatch/missing | ... |

Statuses: `match` = implemented as specified; `partial` = differs but related; `mismatch` = contradicts ADR; `missing` = not implemented.

**Applies to:** `pr-artifacts.py` — could generate a forensic diff artifact alongside PR body. Could also be a standalone pass in `review-passes.py` when `task_type=design` or `task_type=planning`.

**Reusability:** MEDIUM — most valuable for design/planning tasks; lower value for simple impl or refactor.

**Falsification condition:** This would be wrong if the matrix is treated as box-ticking. Mitigated by requiring one evidence quote per cell.

**Closes gap:** PR artifacts currently show what changed, not whether the change matches intent. P5 adds an ADR-level alignment check.

---

## P6 — Success Criteria Checklist (Priority-Ordered)

**Source:** windows-11 transcript (lines 5077–5189)

**What it is:** Explicit numbered list of must-do items before asking any questions. Defines failure conditions per item.

**Applies to:** SKILL.md — could be added to verification step to make criteria explicit per task contract.

**Reusability:** MEDIUM — primarily useful for complex implementation tasks with multiple interdependent steps.

---

## P7 — Root Cause Tracing (F1–Fn + Inference Chain)

**Source:** windows-11 transcript (lines 2605–2694)

**What it is:** Numbered factual findings (F1, F2...) each with code-level evidence (file path, line number), followed by a causal inference section.

**Applies to:** `review-passes.py` — correctness pass. Could seed a structured RCA format for failed verification.

**Reusability:** HIGH — domain-agnostic; any diagnostic or debugging workflow.

---

## P8 — External LLM Judge (5-Axis JSON Output)

**Source:** windows-11 transcript (lines 7530–7599)

**What it is:** Structured evaluation prompt with 5 axes:
1. mixed-substance violations
2. unsupported causal/diagnostic claims
3. ask-user-before-investigate laziness
4. structural contract adherence
5. validator adequacy

Output schema:
```json
{
  "agreement": "full|partial|none",
  "severity": "critical|warning|info",
  "recommended_action": "...",
  "detected_failure_modes": [...],
  "notes": "..."
}
```

**Applies to:** `review-passes.py` — could seed a "reviewer agent" sub-pass for low-confidence verdicts. Already referenced in go-pi STEP 2.5.

**Reusability:** MEDIUM — requires external LLM access; not always available.

---

## Quick Reference: Pattern → Skill Phase Mapping

| Pattern | verify-task | review-passes | pr-artifacts | SKILL.md prose |
|---------|-------------|---------------|--------------|---------------|
| P1 [FACT]/[INF]/[REC] | ✅ | ✅ | — | — |
| P2 Adversarial break-cases | — | ✅ (scope) | — | — |
| P3 Gap 6-dimension scan | ✅ (scope drift) | ✅ | — | — |
| P4 Evidence requirement | — | ✅ | — | — |
| P5 ADR matrix | — | ✅ (design) | ✅ | — |
| P6 Success criteria checklist | — | — | — | ✅ |
| P7 RCA trace | — | ✅ (correctness) | — | — |
| P8 External judge | — | ✅ | — | — |