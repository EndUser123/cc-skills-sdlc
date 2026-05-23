# Phase 2: Cross-Agent Meta-Critique

## Your Job

Critique the Phase 1 specialist findings — not the original work. Focus on:
1. Contradictions between specialists
2. Calibration — are severity ratings consistent across agents?
3. Blind spots — what did no specialist catch?
4. Precision vs recall failures

## Input

Read these files:
- **Original Work:** `cat "P://{session_dir}/work.md"`
- **Phase 1 Findings:** `cat "P://{session_dir}/p1_findings.md"`
- **Specialist JSON outputs (session-scoped — dynamic glob):**
  - `cat "P://{session_dir}/specialists/*.json"` — read all specialist JSON files from the session's specialists subdirectory

## Analysis Steps

### Step 1: Pre-Condition Check — Correct Session Verification

**Kill criterion (COMP-003 + COMP-005):** Before reading any specialist JSONs, verify this is the **current session's** outputs — not a prior session's stale files.

**A. Session identity check — must pass both:**
1. `P://{session_dir}/p1_findings.md` must exist (Phase 1 always writes this last; its presence proves the session completed)
2. `P://{session_dir}/work.md` must exist and contain the work being reviewed (re-read it and verify it matches the original target)

**B. Specialist files check:**
- Use a file glob on `P://{session_dir}/specialists/*.json`
- If **zero specialist files exist**: Write a calibration failure note to `P://{session_dir}/p2.md` and exit Phase 2 early

**Why both checks:** A prior session may have stale `specialists/*.json` files even after the current session has its own directory. Checking p1_findings.md existence alone is insufficient — a prior session's directory could persist after the current session creates a new directory. The combination of p1_findings.md + work.md content verification proves session identity.

**Do NOT silently proceed with empty or cross-session input. This is a hard kill criterion.**

### Step 2: Check for Contradictions

Look across specialist findings for claims that contradict each other:
- One specialist says X is safe, another says X is risky
- Severity ratings that conflict for similar issues
- Recommendations that conflict

### Step 3: Calibrate Severity

Check if severity is consistent:
- A CRITICAL in one domain vs a LOW in another for equivalent issues = calibration failure
- Flag items where one specialist downplayed an issue another flagged as serious

### Step 4: Find Blind Spots

What did none of the specialists catch?
- Look at the work type: what issues are common for this type but absent?
- Are there systemic patterns the specialists collectively missed?
- Did Phase 1 omit logic review for a target that required it?
- Did Phase 1 omit static test coverage or non-static validation coverage?

### Step 4b: Non-Static Validation Coverage

Check whether Phase 1 distinguished:

- problems found by static review;
- problems only visible through tests, plugin validation, runtime probes, traces, smoke checks, or live runs;
- non-static probes that were recommended but not run because they need permission.

If the critique claims runtime confidence from static-only evidence, flag it as a calibration failure.

### Step 4c: Missing Lens Fail Condition

Check Phase 1 against `references/review-lenses.md`. If Phase 1 omitted any lens that could change the stop/go decision, treat the review as incomplete unless Phase 1 gave a concrete reason the lens was safe to skip.

Any omitted mandatory lens that could change the stop/go decision is a stop/go blocker. Do not downgrade it to an advisory note unless the Phase 1 findings include concrete evidence that the lens is irrelevant for the target.

Common fail conditions:
- logic/data-flow lens omitted for behavior changes
- state-machine/concurrency lens omitted for lifecycle or cache changes
- static test lens omitted for package, prompt, or script changes
- non-static validation lens omitted for plugin, runtime, browser, CLI, or live-run claims
- observability/tracing lens omitted for throughput, benchmark, or production-readiness claims

### Step 5: Distinguish Recall vs Precision

**P1 #7 Precision/Recall distinction:** Separately analyze:
- **Recall failures (missed issues):** What did Phase 1 miss that should have been caught? Look at common issue types for this work type that no specialist flagged.
- **Precision failures (over-criticism):** What did Phase 1 flag that is actually fine, or inflated in severity beyond what the evidence supports?

Flag both types explicitly.

## Output Schema

Write your meta-critique to `P://{session_dir}/p2.md`:

```
## Cross-Agent Contradictions
1. [contradiction] — Specialist A says X, Specialist B says Y
...

## Severity Calibration Issues
1. [issue] — rated differently by different specialists without justification
...

## Missed Blind Spots
1. [what was missed] — why it matters
...

## Non-Static Validation Coverage
1. [gap] — what runtime/live/plugin behavior remains unproven
...

## Missing Lens Fail Condition
1. [lens] — missing/waived/acceptable and why
...

## Precision Failures
1. [finding from Phase 1] — [why it's too vague/generic/weak]
...

## Improvements to the Phase 1 Findings
1. [specific improvement]
2. [specific improvement]
...
```

## Constraints

- Focus on the quality of the Phase 1 analysis, not re-reviewing the work
- Be specific — cite the finding and why it fails
- Do not be pedantic — flag real failures, not nitpicks
