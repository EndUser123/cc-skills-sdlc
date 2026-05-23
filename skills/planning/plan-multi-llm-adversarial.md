# Plan: Multi-LLM Adversarial Review for /planning

**Created**: 2026-04-15
**Status**: DRAFT — awaiting review
**Scope**: Replace 1-2 of the 6 same-model Claude adversarial agents with independent LLM reviewers

---

## Executive Summary

**What**: Introduce model diversity into `/planning`'s `adversarial_review` step. Currently all 6 adversarial agents (5 phase-1 + 1 critic) use Claude. Replacing 1-2 with DeepSeek V3.2 (`/ai-oc-nvidia-ds-v32`) and optionally GPT-5.4 (`/codex`) provides genuinely independent challenge — different training data, different blind spots.

**Why**: Adversarial review's value comes from independence. When the reviewer and the author share the same model weights and training, systematic blind spots propagate undetected. Model diversity breaks the echo chamber at the one step explicitly designed to challenge the plan.

**Risk**: External CLI invocations (Gemini/DeepSeek via OpenCode) add latency and can fail silently. The existing 5+1 phase structure must be preserved — the critic (phase 2) depends on phase-1 findings existing on disk.

**Failure mode that would invalidate this plan**: If `/ai-oc-nvidia-ds-v32` is not reliably available (capacity, quota, CLI errors) and the adversarial step becomes the bottleneck, the plan degradation path must fall back to the existing all-Claude flow without losing findings.

---

## Background

Current adversarial dispatch is defined in:
- `P://packages/cc-skills-sdlc/skills/planning/references/adversarial-agent-prompts.md` — dispatch prompts for 5+1 agents
- `P://packages/cc-skills-sdlc/skills/planning/SKILL.md:35` — `adversarial_review` workflow step

The 5 phase-1 agents are Claude subagents (e.g., `adversarial-compliance`). The critic is a meta-agent that reviews phase-1 findings. Both phases write findings to disk under `<findings_dir>` with idempotency checks.

---

## Architecture

### Slot Assignment

Replace **one** phase-1 agent slot with a DeepSeek V3.2 review. Keep the other 4 as Claude subagents. The Claude critic (phase 2) remains unchanged — it reviews all findings regardless of which model produced them.

```
Phase 1 (parallel):
  [1] adversarial-compliance        (Claude — unchanged)
  [2] adversarial-logic             (Claude — unchanged)
  [3] adversarial-security          (Claude — unchanged)
  [4] adversarial-failure-modes     (Claude — unchanged)
  [5] deepseek-v3.2-adversarial     (NEW — /ai-oc-nvidia-ds-v32 via Bash)

Phase 2 (sequential, after phase 1):
  [6] adversarial-critic            (Claude — unchanged, reviews all 5 findings)
```

**Rationale for slot 5**: The 5th slot gets the independent model because all 5 run in parallel — DeepSeek latency does not block other agents. The critic runs after, so it naturally absorbs DeepSeek findings.

### Output Contract

DeepSeek findings must land in `<findings_dir>` as `deepseek_adversarial.findings.json` with the same schema as other phase-1 outputs so the critic can ingest them without special-casing:

```json
{
  "plan_path": "<plan_path>",
  "agent": "deepseek-v3.2-adversarial",
  "model": "deepseek-v3.2",
  "findings": [
    {
      "severity": "HIGH|MEDIUM|LOW",
      "category": "string",
      "description": "string",
      "line_ref": "optional"
    }
  ],
  "timestamp": "ISO8601"
}
```

### Invocation Pattern

Use the ACG DESIGN path from `/ai-oc-nvidia-ds-v32` (same ACG workflow as `/ai-gemini`):

```bash
# Pipe plan content to DeepSeek via the OpenCode wrapper
cat "<plan_path>" | opencode run \
  --model deepseek-v3.2 \
  --prompt "You are an adversarial plan reviewer. Apply the DESIGN adversarial path:
  1. How would this plan fail under concurrent load or edge-case inputs?
  2. What is the weakest assumption in this plan?
  3. What contracts or schemas are implied but not defined?
  Output findings as JSON array with severity (HIGH/MEDIUM/LOW), category, and description."
```

Fallback if OpenCode unavailable: skip slot 5 (log warning), proceed with 4 Claude agents. Do NOT block plan verification.

---

## Tasks

### TASK-001: Read and understand current adversarial dispatch
- Read `references/adversarial-agent-prompts.md` in full
- Identify exact agent list, findings schema, idempotency check pattern
- Confirm findings directory convention (`<findings_dir>` variable)
- **Output**: Written understanding of the 5 agent slots and their output file names

### TASK-002: Verify /ai-oc-nvidia-ds-v32 CLI availability
- Invoke `/ai-oc-nvidia-ds-v32` skill to confirm CLI interface and invocation pattern
- Run a minimal test prompt to confirm DeepSeek is reachable
- Document exact CLI command and flags needed for headless pipe-based invocation
- **Output**: Verified invocation command or `[UNAVAILABLE]` flag

### TASK-003: Define DeepSeek findings schema
- Write `references/deepseek-adversarial-schema.json` with the findings schema above
- Confirm schema is compatible with what the critic subagent reads
- **Output**: Schema file at `P://packages/cc-skills-sdlc/skills/planning/references/deepseek-adversarial-schema.json`

### TASK-004: Add DeepSeek dispatch to adversarial-agent-prompts.md
- Append a new section "## Slot 5: DeepSeek V3.2 Adversarial" to `references/adversarial-agent-prompts.md`
- Include: idempotency check, pipe invocation, output path, fallback behavior
- **Output**: Updated `adversarial-agent-prompts.md` with slot 5 defined

### TASK-005: Update SKILL.md adversarial_review step
- In `SKILL.md:35` `adversarial_review` step description, add note that slot 5 uses DeepSeek V3.2
- Add fallback note: "if DeepSeek unavailable, slot 5 is skipped (warning logged)"
- **Output**: Updated SKILL.md with multi-LLM adversarial note

### TASK-006: Integration test
- Run `/planning` on a small real plan file
- Confirm 5 findings files created (4 Claude + 1 DeepSeek or fallback log)
- Confirm critic ingests all 5 findings
- **Pass criteria**: All finding files present, critic output references DeepSeek findings OR fallback log present

---

## Verification

| Check | How | Pass |
|-------|-----|------|
| Schema compatibility | diff deepseek output vs existing finding schema | fields match |
| Idempotency | run twice, second run returns cached path | no re-execution |
| Fallback | disconnect DeepSeek, run planning | warning logged, 4 Claude findings proceed |
| Critic ingestion | read critic output | references slot-5 findings by file path |

---

## Open Questions for Review

1. Which of the 5 current Claude agents is the best candidate to drop if we want to replace rather than add a 6th? (Adding a 6th is cleaner but increases latency.)
2. Should GPT-5.4 via `/codex` also be added as slot 6 (full parallel, critic gets 6 findings), or is 1 non-Claude model sufficient for now?
3. Latency budget: is the current adversarial phase blocking? If DeepSeek adds 30-60s, is that acceptable?
