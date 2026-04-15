# Plan: Gemini Inline ADR Critic for /arch

**Created**: 2026-04-15
**Status**: DRAFT — awaiting review
**Scope**: Invoke /ai-gemini's DESIGN adversarial path inline during the adr_critic_review workflow step

---

## Executive Summary

**What**: The `/arch` workflow includes an `adr_critic_review` step (`SKILL.md:28`). Currently this step is described but runs within Claude's context. Add an explicit Gemini 2.5 invocation (via `/ai-gemini` Section 9 CLI) that runs the DESIGN adversarial path against the ADR before the Claude-based critic completes its synthesis.

**Why**: `/arch` already lists `/ai-gemini` as a `follow_up_offer` (`SKILL.md:18`) — meaning it's suggested after the fact, not embedded in the workflow. Moving Gemini into the `adr_critic_review` step means the ADR gets challenged by a different model *before* it's handed to `/planning`, not after the user has already moved on. The DESIGN adversarial path in `/ai-gemini` (3 failure modes, weakest assumption, contract audit) maps directly to what ADR critique should do.

**Risk**: `/ai-gemini` CLI invocation requires the Gemini CLI (`gemini -y -o text -m gemini-2.5-flash`). If the CLI is unavailable or returns empty output, `adr_critic_review` must still complete using Claude alone. The plan must define a concrete fallback so the ADR is never stuck.

**Failure mode that would invalidate this plan**: If Gemini hallucinates non-existent file paths or invents ADR content, its findings are lower-confidence than Claude's and must be labeled `[GEMINI-INFERRED]`. The synthesis step must not accept Gemini findings as authoritative without cross-checking against the actual ADR text.

---

## Background

Current `/arch` workflow steps (`SKILL.md:19-31`):
```
preflight_checks → classify_intent → contract_sensitivity_classification
→ select_template → load_template → execute_template_analysis
→ contract_boundary_inventory → contract_boundary_closure
→ emit_contract_authority_packet → adr_closure_consistency_check
→ adr_critic_review → generate_architecture_review
```

`adr_critic_review` runs after the Contract Authority Packet is emitted — meaning Gemini can see the full ADR and packet when it runs. This is the right position: the packet is already machine-parseable, so Gemini can review structured artifacts, not just prose.

The Gemini DESIGN adversarial path (`/ai-gemini` SKILL.md Section 4):
```
1. How would this design fail under concurrent load?
2. What is the weakest assumption?
3. What contracts and schemas are preserved or broken?
```

These three questions are exactly what ADR critique needs.

---

## Architecture

### Integration Point

Inside `adr_critic_review`, before Claude synthesizes the critic output:

```
adr_critic_review:
  Step A: Run Gemini DESIGN adversarial path on the ADR + CAP  →  gemini_findings.md
  Step B: Claude reads ADR + CAP + gemini_findings.md and synthesizes critic output
  Step C: Emit combined critic output to generate_architecture_review

**[INFERRED] handling in Step B**: Any Gemini finding marked `[INFERRED]` must be cited in the synthesis as "model-inferred, not sourced from ADR" and flagged for human verification before acting on. Step B output must distinguish `[INFERRED]` findings from findings with ADR section citations — they are not equivalent confidence levels.
```

Step A uses the Gemini CLI (Section 9 of `/ai-gemini`):
```bash
gemini -y -o text -m gemini-2.5-flash \
  --include-directories "P:/" \
  -p "You are an adversarial architecture reviewer.

Read the ADR at: <adr_path>
Read the Contract Authority Packet at: <cap_path>

Apply the DESIGN adversarial review:
1. How would this design fail under concurrent load or at scale?
2. What is the single weakest assumption in this ADR?
3. What contracts or schemas are implied but not formally defined?

For each finding, cite the specific section of the ADR that supports or contradicts your finding.
Mark any claim not supported by the ADR as [INFERRED]."
```

Output written to a path confirmed in TASK-002. Note: `arch_decisions/` directory does NOT currently exist — TASK-002 must determine the correct output location (likely create `arch_decisions/` or use an existing subdir).

### Output Contract

Output path: `<path-tbd-in-task-002>` (confirmed in TASK-002 — not `arch_decisions/` in this architecture block).

### Kill Switch

Set `SDLC_MULTI_LLM=0` to skip the Gemini slot in `adr_critic_review`. When set, Step A is not run and Step B receives no Gemini findings — Claude-only critic synthesis proceeds. Checked before the Gemini CLI is invoked.

```markdown
## Gemini ADR Critic — <adr_slug>

**Model**: gemini-2.5-flash
**ADR reviewed**: <adr_path>
**CAP reviewed**: <cap_path>

### Finding 1: Concurrent load failure mode
[description] [source: adr:section or [INFERRED]]

### Finding 2: Weakest assumption
[description] [source: adr:section or [INFERRED]]

### Finding 3: Undefined contracts
[list of implied contracts not in CAP] [source: adr:section or [INFERRED]]

### Confidence
[HIGH if all 3 findings cite ADR source / MEDIUM if 1+ is [INFERRED] / LOW if all [INFERRED]]
```

### Fallback Behavior

If `gemini --version` check fails or output is empty after 3 retries:
- Log: `[WARNING: Gemini slot skipped — review coverage reduced]` (visible marker, not buried in logs)
- Proceed with Claude-only critic synthesis
- Emit `[WARNING: Gemini slot skipped]` in the `generate_architecture_review` output header, not just a footnote

---

## Tasks

### TASK-001: Verify Gemini CLI is available and filesystem access works
- Run Section 9.1 verification ritual from `/ai-gemini` SKILL.md:
  - `gemini --version` → expect v0.37.0+
  - `gemini -y -o text -p "Say hello"` → expect text output
  - `gemini -y -o text --include-directories "P:/" -p "Read P:/README.md and return filename"` → filesystem check
- **Output**: Verified or `[GEMINI-UNAVAILABLE]` with specific failure point

### TASK-002: Identify adr_critic_review current implementation and output path
- Search for any existing `adr_critic_review` implementation (Python or SKILL.md instructions)
- `arch_decisions/` does NOT exist (verified). Determine correct output location: check where arch currently writes ADRs/CAPs (search for `.cap.json`, `.adr.md`, `.contract-authority-packet.json` in the arch skill dir)
- Check what format the ADR and CAP are in (JSON, markdown, both?)
- **Output**: File:line for current adr_critic_review logic, ADR/CAP format confirmed, and chosen output path for gemini findings

### TASK-003: Write Gemini ADR critic prompt
- Finalize the prompt for Gemini (expand the draft above based on actual ADR format found in TASK-002)
- Confirm `--include-directories` scope is sufficient for ADR and CAP paths
- **Output**: Final prompt text in `P:/packages/sdlc/skills/arch/references/gemini-adr-critic-prompt.md`

### TASK-004: Update adr_critic_review in SKILL.md
- In `/arch` SKILL.md, expand the `adr_critic_review` workflow step with inline instructions
- Add: Gemini invocation (Step A), synthesis (Step B), fallback behavior
- **Output**: Updated SKILL.md with adr_critic_review expanded

### TASK-005: Remove /ai-gemini from follow_up_offer
- With Gemini now inline, `follow_up_offer: /ai-gemini` (`SKILL.md:18`) is redundant for ADR critique
- Decide: remove entirely, or keep as a general research follow-up option
- **Output**: Updated SKILL.md frontmatter (either removed or scoped to non-ADR use)

### TASK-006: Integration test
- Run `/arch` on a real or synthetic ADR
- Confirm Gemini findings file created in the path confirmed by TASK-002 (not `arch_decisions/` unless TASK-002 confirms that path)
- Confirm `generate_architecture_review` output cites Gemini findings
- **Pass criteria**: Gemini file exists, at least 1 Gemini finding appears in final arch review

---

## Verification

| Check | How | Pass |
|-------|-----|------|
| Gemini CLI available | Section 9.1 ritual | all 3 checks pass |
| Output written | check `arch_decisions/` after run | file exists, non-empty |
| [INFERRED] labeling | Gemini output contains claims | each claim labeled |
| Fallback | disconnect Gemini CLI, run /arch | Claude-only critic completes |
| No CAP regression | run `arch_validate.py` after | validation still passes |

---

## Decisions (resolved)

1. **Gemini output vs CAP**: Keep separate. CAP is a machine-authoritative structured artifact; Gemini findings are advisory input to the Claude critic synthesis. Mixing them would violate the schema-first authority rule in `/arch` SKILL.md.

2. **Flash vs Pro**: Flash. ADRs are typically 1-3 pages focused documents. The 3-question adversarial path is not a long-context reasoning task — Pro's advantage (deeper reasoning, longer context) does not apply. Flash avoids unnecessary latency on a short-document task.

3. **Add DeepSeek on ADRs too**: No. Gemini + Claude critic = 2 reviewers for a short artifact. A third model is over-engineering at this step. If a specific ADR is high-stakes, the user can invoke `/ai-oc-nvidia-ds-v32` manually after.

4. **`follow_up_offer: /ai-gemini`**: Keep it, add scope note: "for general research/design follow-up on non-ADR queries; Gemini is already inline for ADR critique."
