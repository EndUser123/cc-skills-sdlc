# Hypothesis Scoring & Ranking System (v2.4)

## Scoring Formula

Hypothesis Score = Reproducibility(0.3) x Recency(0.2) x Impact(0.5)

| Factor | Weight | Scoring Criteria |
|--------|--------|-----------------|
| **Reproducibility** | 0.3 | 1.0 = Can reproduce, 0.5 = Sometimes, 0.1 = Cannot reproduce |
| **Recency** | 0.2 | 1.0 = Changed today, 0.5 = This week, 0.1 = Old code |
| **Impact** | 0.5 | 1.0 = Explains ALL symptoms, 0.5 = Some, 0.1 = Weak |

## Hypothesis Ranking Template

**REQUIRED FORMAT**: Each hypothesis MUST include confidence tag `(Tier N, X%)`

| # | Hypothesis | Score | Confidence | Status |
|---|------------|-------|------------|--------|
| 1 | Missing rate limiting on stdout writes | 0.85 | (Tier 2, 75%) | TESTING |
| 2 | Rich Progress rate too high | 0.65 | (Tier 1, 50%) | Eliminated |

**Confidence Tag Format**: `(Tier [0-4], [0-100]%)`
- Tier 0: Intuition/docs only
- Tier 1: Code inspection
- Tier 2: Local reproduction/unit tests
- Tier 3a: Runtime state only (files, env, intent JSON)
- Tier 3b: Runtime state + hook logs / tool-pipeline logs
- Tier 4: End-to-end observed behavior

## Disconfirmation Step Format (REQUIRED in v2.6)

**For EVERY hypothesis, you MUST explicitly state how you tested it:**

**Template**:
```markdown
#### Hypothesis [N]: [Hypothesis text]

**Disconfirming Evidence**: "If this hypothesis were false, I would see: [specific observable]"
**Disconfirmation Check**: "I checked: [what you actually checked] and found: [result]"
**Result**: [SUPPORTED / REFUTED / INCONCLUSIVE]
```

**Example**:
```markdown
#### Hypothesis 1: Skill enforcer is injecting SKILL.md into prompt

**Disconfirming Evidence**: "If skill enforcer were NOT injecting, I would see: no SKILL.md content in prompt context"
**Disconfirmation Check**: "I checked: UserPromptSubmit hook logs and found: SKILL.md injection occurred at 14:32:15 with 2453 characters"
**Result**: SUPPORTED
```

**Purpose**: Prevents lock-in on plausible-sounding but unverified hypotheses

## Pattern: Workaround Detection (RED FLAG)

**When considering fixes involving timeouts, skips, or wrapper functions:**

### RED FLAGS (require trace evidence before proceeding):

| Pattern | Why It's Suspicious | Required Evidence |
|---------|-------------------|-------------------|
| Reducing timeouts | Hides problem, doesn't fix it | Trace showing WHERE it blocks and WHY timeout occurs |
| Adding "skip" logic | Avoids root cause | Evidence of why skip is safe vs fixing underlying issue |
| Timeout wrappers | Band-aid over blocking operation | Trace of actual blocker and explanation of why wrapper is appropriate |
| Disabling code paths | Breaks features | Documentation check: Is this intentional behavior or a bug? |

### MANDATORY Workflow for Timeout/Skip Hypotheses:

1. **Trace first** (Step 1.6): Identify exact blocking call with debug logging
2. **Check feature preservation**: Search docs before disabling behavior
   ```bash
   grep -r "backfill|api|metadata" ARCHITECTURE.md PRD.md
   ```
3. **Explain workaround necessity**: If you still propose timeout/skip, document:
   - Why root cause cannot be fixed (technical limitation, external dependency)
   - What features are preserved vs broken
   - Why workaround is safer than alternative

### Auto-Reject Patterns (STOP and retrace):

- "Reduce timeout from 30s to 10s" without trace of WHERE it blocks
- "Skip X if condition Y" without checking if X is a documented feature
- "Add timeout wrapper around function Z" without reading function Z's code

### Correct Pattern (from this session):

**Wrong** (workaround without trace):
- Symptom: "Hangs at channel processing"
- Proposal: "Reduce API timeout from 30s to 10s"
- Problem: Doesn't fix root cause, just fails faster

**Correct** (trace -> root cause -> fix):
- Symptom: "Hangs at channel processing"
- Trace: Added logging, found hang in `_discover_via_ytdlp()`
- Investigation: Database lookup returns `None` for channels with 0 videos
- Root cause: `db_count > 0` check rejects valid channels
- Fix: Remove check, return channel metadata regardless of video count
- Result: No hang, preserves feature, fixes root cause
