# Output Format & Confidence Tags

## Confidence Tag Requirement (MANDATORY in v2.6)

**All hypothesis statements, conclusions, and claims MUST include confidence tags:**

**Format**: `(Tier [0-4], [0-100]%)`

### Tier Definitions

| Tier | Evidence Type | Max Confidence | Max Claim Allowed | Example Phrasing |
|------|---------------|----------------|-------------------|------------------|
| Tier 0 | Intuition, comments, docs, memory | 50% | "Possible direction" | "This might be related to X (Tier 0, 40%)" |
| Tier 1 | Code/config inspection | 75% | "Plausible cause" | "Code shows X likely causes Y (Tier 1, 70%)" |
| Tier 2 | Local/synthetic reproduction (unit tests) | 75% | "Working hypothesis" | "Local test confirms X behavior (Tier 2, 75%)" |
| Tier 3a | Runtime state only (files, env, intent JSON) | 80% | "Probable cause" | "State files show X condition (Tier 3a, 80%)" |
| Tier 3b | Runtime state + hook logs / tool-pipeline logs | 85% | "Strong evidence" | "Hook logs confirm X execution (Tier 3b, 85%)" |
| Tier 4 | End-to-end observed behavior | 95% | "Confirmed" | "Observed X working end-to-end (Tier 4, 95%)" |

**Rules**:
- No "root cause identified" below Tier 3a
- No "fixed/works" below Tier 4
- Confidence cannot exceed tier ceiling
- Makes overclaiming visually obvious
- Explicitly state Tier 3a vs 3b when using runtime evidence

---

## Required RCA Structure

**MANDATORY: Executed-Path-First Workflow**

1. **FIRST**: Show Executed Path (what code actually ran this turn)
2. **THEN**: Identify Root Cause (must name something in the Executed Path)
3. **DO NOT**: Name a function/file as root cause without first proving it appears in Executed Path

**Time-Scope Labels** (REQUIRED on all evidence citations):
- `[current-state]` -- Evidence from current runtime (files, logs, process state)
- `[transcript-time]` -- Evidence from chat history or prior turns
- `[inference]` -- Logical derivation from evidence (must be labeled as such)

### Hook Authority

**REQUIRED for any RCA involving hooks, skills, or enforcement behavior**

- **Registered hook authority:** `P:/.claude/settings.json`
- **Implementation tree:** `P:/.claude/hooks/`
- **Non-authoritative path:** `~/.claude/hooks`

If the investigation touches hook registration or skill enforcement, the report MUST state:

1. Which settings entry registered the hook
2. Which implementation file was actually inspected
3. Whether config and filesystem matched
4. If they differed, which one was authoritative and why

Do not conclude "no hook exists" or "skill-guard is absent" unless the registered settings entry is missing or points nowhere.

**Reachability Proof**: Before naming a function as root cause:
1. Grep for call-sites: `grep -r "funcName(" --include="*.py"`
2. Verify function has callers (not dead code with 0 callers)
3. Confirm call-site is reachable from Executed Path

**Anti-Lazy Conclusion Rule**:
- If you cannot complete `Executed Path`, `Competing Hypothesis`, `Falsifier`, and `First Divergence`, do not name a root cause yet.
- If your conclusion is only a symptom summary, keep investigating.
- If the root cause does not appear in the executed path, the diagnosis is not finished.

### Template

```markdown
## RCA: [One-line root cause summary]

**Confidence:** [Score]% (Tier [1-4])
**Evidence Tier:** [Highest tier used]

### Symptom

[Observable error/behavior - what the user saw, not your hypothesis]

### Evidence

[Cite >=1 current-turn tool observation: Read on X, Grep found Y, Bash showed Z]
[MUST include time-scope label: current-state, transcript-time, or inference]

### Observable Definition

**Expected Observable**
[What the user should directly see or experience]

**Non-Equivalent Proxies**
- [Proxy] -> Why this is not proof

**Exact Success Evidence**
[What would directly prove the feature works]

### Evidence Buckets

**Mechanism**
[How the code is wired]

**State**
[What runtime state/logs/files show]

**Outcome**
[What the user actually saw]

### Executed Path

[Functions/files that actually ran this turn, reachable via current-turn evidence]
[Must show call chain: entry point -> ... -> failure point]
[Dead code (0 callers) CANNOT be the root cause]

### Competing Hypothesis

[Competing explanation - must exist even if brief]

### Falsifier

[Evidence that refutes the Alternative Hypothesis]
[Must show WHY alternative is wrong, not just that it exists]

### First Divergence

[Earliest point where actual behavior diverged from expected behavior]

### RCA Think Pass

[Strongest likely diagnosis]
[Strongest competing explanation]
[Most pragmatic explanation]
[Smallest discriminating check]
[One refinement only]

### Root Cause

[File/symbol/path that appears in Executed Path above]
[Must have reachability proof: grep call-sites + confirm callers exist]

**Technical:** [What broke - file, line, mechanism] (Tier [0-4], [0-100]%)

**Systemic:** [Why it was possible - missing test, unclear interface, process gap] (Tier [0-4], [0-100]%)

**Why this is the root cause:** [Tie the cause back to executed path and divergence]

### Fix

[Specific code change - file edit, config change, etc.]
[Must be concrete action, not "investigate more" or "check logs"]

**Files:**
- [file]: [what changes]

**Reversibility:** [Score 1.0-2.0]

### Verification

- [ ] [How to verify fix works - specific test or command]
- [ ] [Regression check]
- [ ] [Confirm dead code was not incorrectly named as cause]
```

---

## Block Triggers

**Do not complete RCA without these:**
- No Executed Path shown -> block
- Root Cause names function not in Executed Path -> block
- Root Cause is dead code (0 callers) -> block
- No Alternative Hypothesis -> block
- No Falsifier (or doesn't refute alternative) -> block
- Evidence lacks time-scope label -> block
- Fix is vague ("test it", "verify") -> block

### Action Graph (include in output)

| Step | Action | Expected | Actual | Divergence? | Lesson |
|------|--------|----------|--------|-------------|--------|
| 1 | ... | ... | ... | ... | ... |
