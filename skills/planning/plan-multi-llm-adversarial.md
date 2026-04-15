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
- `P:/packages/sdlc/skills/planning/references/adversarial-agent-prompts.md` — dispatch prompts for 5+1 agents
- `P:/packages/sdlc/skills/planning/SKILL.md:35` — `adversarial_review` workflow step

The 5 phase-1 agents are Claude subagents (e.g., `adversarial-compliance`). The critic is a meta-agent that reviews phase-1 findings. Both phases write findings to disk under `<findings_dir>` with idempotency checks.

---

## Architecture

### Slot Assignment

Add DeepSeek V3.2 as a **6th agent** running in parallel with the existing 5. All 5 current Claude agents are named and distinct — none are replaceable without losing coverage. The Claude critic (phase 2) remains unchanged — it reviews all findings regardless of which model produced them.

Verified agent list from `references/adversarial-agent-prompts.md`:
```
Phase 1 (parallel):
  [1] adversarial-compliance        (Claude — unchanged)
  [2] adversarial-logic             (Claude — unchanged)
  [3] adversarial-testing           (Claude — unchanged)
  [4] adversarial-security          (Claude — unchanged)
  [5] adversarial-failure-modes     (Claude — unchanged)
  [6] deepseek-v3.2-adversarial     (NEW — /ai-oc-nvidia-ds-v32 via Bash)

Phase 2 (sequential, after phase 1):
  [7] adversarial-critic            (Claude — unchanged, reviews all 6 findings)
```

**Rationale for adding as slot 6**: All 5 existing agents run in parallel — DeepSeek runs alongside them, critic waits for all 6.

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
# Kill switch: skip if SDLC_MULTI_LLM=0

# Idempotency check — skip if valid findings already exist
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

# Invoke DeepSeek via the agentic-cli wrapper (verified syntax from /ai-oc-nvidia-ds-v32 SKILL.md)
pwsh -File P:/scripts/agentic-cli.ps1 `
  -cli "opencode" `
  -command "run \"Review plan at <plan_path> for: (1) failure modes under concurrent load, (2) weakest assumption, (3) implied contracts not defined. Output as JSON matching schema at <findings_path>.\" --model nvidia/deepseek-ai/deepseek-v3.2 --format json" `
  -outputPath "<findings_path>"
```

Note: full model name is `nvidia/deepseek-ai/deepseek-v3.2`. No `--prompt` flag (prompt is positional). No `--include-dir` flag (OpenCode does not support it).

Fallback if OpenCode unavailable: skip slot 6, emit `[WARNING: DeepSeek slot skipped — review coverage reduced]` in the adversarial review output header, proceed with 5 Claude agents. Do NOT block plan verification.

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
- **Output**: Schema file at `P:/packages/sdlc/skills/planning/references/deepseek-adversarial-schema.json`

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

1. ~~Which of the 5 agents to drop~~ — resolved: all 5 are distinct, DeepSeek adds as slot 6.
2. Should GPT-5.4 via `/codex` also be added as slot 7 (critic gets 7 findings), or is 1 non-Claude model sufficient for now?
3. Latency budget: is the current adversarial phase blocking? If DeepSeek adds 30-60s, is that acceptable?
