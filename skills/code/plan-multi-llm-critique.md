# Plan: Multi-LLM Code Critique for /code

**Created**: 2026-04-15
**Status**: DRAFT — awaiting review
**Scope**: Add an independent LLM reviewer to the AUDIT phase `critique_agent_review` step

---

## Executive Summary

**What**: The `/code` AUDIT phase (Phase 8) currently runs `pr-review-toolkit:code-reviewer` for code quality review (`audit-phase-details.md:30`). Add a second review pass using DeepSeek V3.2 (`/ai-oc-nvidia-ds-v32`) that runs in parallel with the existing Claude reviewer. The two reviews are then synthesized.

**Why**: A code reviewer that didn't write the code catches more issues. When Claude writes the code (Phase 6 TDD) and Claude reviews it (Phase 8 AUDIT), systematic blind spots go undetected. DeepSeek V3.2 has different training data and tends to surface different code smell categories — particularly around control flow assumptions and error handling patterns.

**Risk**: Adds a second external CLI call in the AUDIT phase. If DeepSeek is unavailable, the primary `pr-review-toolkit:code-reviewer` must still complete. This is additive, not a replacement.

**Failure mode that would invalidate this plan**: If DeepSeek's output format is too unstructured for the existing AUDIT synthesis step, findings could be ignored silently. The plan must define a concrete output schema and a named consumer for DeepSeek findings.

---

## Background

Current AUDIT phase is defined in:
- `P:/packages/sdlc/skills/code/references/audit-phase-details.md` — full audit instructions
- `P:/packages/sdlc/skills/code/SKILL.md:54` — `critique_agent_review` as `kind: verification`

Step 7.1 in `audit-phase-details.md` dispatches `pr-review-toolkit:code-reviewer` via Agent tool. This is the integration point.

---

## Architecture

### Integration Point

Add DeepSeek review as Step 7.1b in parallel with Step 7.1, and add Step 7.2 as a **new** synthesis step. Verified: `audit-phase-details.md` ends at line 103 with no synthesis step — it must be added.

```
Step 7.1  (existing): Agent(pr-review-toolkit:code-reviewer)       → findings_claude.md
Step 7.1b (new):      DeepSeek V3.2 via /ai-oc-nvidia-ds-v32      → findings_deepseek.json
Step 7.2  (NEW):      Read both findings files, emit combined summary
```

Both 7.1 and 7.1b run in parallel — neither depends on the other's output. Step 7.2 (new) waits for both.

### Output Contract

DeepSeek findings written to `<audit_dir>/findings_deepseek.json` (JSON, consistent with Plan 1 schema):

```json
{
  "reviewer": "deepseek-v3.2",
  "files_reviewed": ["<list>"],
  "confidence_threshold": 80,
  "findings": [
    {
      "severity": "HIGH|MEDIUM|LOW",
      "file": "<file>",
      "line": "<n>",
      "issue": "<description>",
      "recommendation": "<fix>"
    }
  ],
  "summary": "<1-2 sentence summary>"
}
```

### Invocation Pattern

```bash
# Kill switch: skip if SDLC_MULTI_LLM=0

# Diff against branch point (not HEAD~1 — feature spans multiple commits)
$DIFF=$(git diff $(git merge-base HEAD origin/main) HEAD)

# Idempotency check — skip if valid findings already exist
python -c "
import sys, json, time, os
fpath = r'<audit_dir>/findings_deepseek.json'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('reviewer') == 'deepseek-v3.2' and age < 86400:
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

# Invoke DeepSeek via agentic-cli wrapper (verified syntax from /ai-oc-nvidia-ds-v32 SKILL.md)
pwsh -File P:/scripts/agentic-cli.ps1 `
  -cli "opencode" `
  -command "run \"Review this diff for: (1) logic errors, (2) error handling gaps, (3) state mutation bugs, (4) security issues. Report findings with severity HIGH/MEDIUM/LOW, >= 80% confidence only. Output as JSON to <audit_dir>/findings_deepseek.json. Diff: $DIFF\" --model nvidia/deepseek-ai/deepseek-v3.2 --format json" `
  -outputPath "<audit_dir>/findings_deepseek.json"
```

Note: full model name is `nvidia/deepseek-ai/deepseek-v3.2`. No `--prompt` flag.

Fallback: if DeepSeek unavailable, emit `[WARNING: DeepSeek slot skipped — review coverage reduced]` in the AUDIT output header and continue with Claude-only review. DONE phase is not blocked.

---

## Tasks

### TASK-001: Identify exact audit phase integration point
- Read `references/audit-phase-details.md` in full
- Identify exact Step 7.1 invocation syntax and output path
- Confirm whether `findings_dir` variable is available in audit context
- **Output**: Exact file:line where Step 7.1b should be inserted

### TASK-002: Verify /ai-oc-nvidia-ds-v32 supports diff-based review
- Invoke skill and test pipe-based diff review with a sample diff
- Confirm output quality is sufficient for code review (not just summarization)
- **Output**: Verified sample output or `[INSUFFICIENT_QUALITY]` flag

### TASK-003: Define output schema for DeepSeek findings
- Write output template for `findings_deepseek.json` (JSON schema, consistent with Plan 1)
- Confirm the existing synthesis step can consume JSON findings from multiple sources
- **Output**: Schema file at `P:/packages/sdlc/skills/code/references/deepseek-critique-schema.json`

### TASK-004: Add Step 7.1b to audit-phase-details.md
- Insert new section "## Step 7.1b: DeepSeek V3.2 Independent Review" after Step 7.1
- Include: parallel execution note, invocation command, output path, fallback behavior
- **Output**: Updated `audit-phase-details.md`

### TASK-005: Update SKILL.md critique_agent_review step
- Add note to `SKILL.md:54` that `critique_agent_review` now includes a multi-LLM pass
- **Output**: Updated SKILL.md

### TASK-006: Integration test
- Run `/code` on a small feature, check AUDIT phase output
- Confirm `findings_deepseek.json` is created (or fallback log present)
- Confirm synthesis output references both Claude and DeepSeek findings
- **Pass criteria**: Both finding files exist, synthesis cites both

---

## Verification

| Check | How | Pass |
|-------|-----|------|
| Parallel execution | timing check — 7.1 and 7.1b finish together | no serial wait |
| Fallback | disconnect DeepSeek, run audit | warning logged, Claude review proceeds |
| Synthesis coverage | read synthesis output | references deepseek findings explicitly |
| No blocking | DeepSeek slow/hanging | Claude review completes, DONE not blocked |

---

## Open Questions for Review

1. Should the synthesis step be explicit (a third Agent call that reads both files) or implicit (Claude reads both files and summarizes in-context)?
2. Is `git diff HEAD~1` the right diff scope, or should we diff against the plan's target branch?
3. Should Kimi K2.5 (`/ai-oc-kimi`) be added as a third reviewer for maximum diversity, or is two models sufficient?
