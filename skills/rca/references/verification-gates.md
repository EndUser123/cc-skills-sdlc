# Investigation Verification Gates

## Gate 1: Pre-Investigation (Before Step 1)

### 1A. Observable Definition (CRITICAL)

**Before starting any investigation, you MUST define the expected observable behavior.**

**MANDATORY Checklist**:
- [ ] Expected observable defined (what user sees/hears/experiences)
- [ ] Non-equivalent proxies listed (what does NOT prove success)
- [ ] Exact success evidence specified (what would falsify "not working")

**Template**:
```markdown
### Observable Definition

**Expected Observable**: [What the user should see/hear/experience]

**Non-Equivalent Proxies** (what does NOT prove success):
- [Proxy 1] -> Why this doesn't prove the observable
- [Proxy 2] -> Why this doesn't prove the observable
- [Proxy 3] -> Why this doesn't prove the observable

**Exact Success Evidence**: [What would directly prove the feature works]
```

**Example from skill-guard bug**:
```markdown
### Observable Definition

**Expected Observable**: User sees Skill('gto') in tool use list

**Non-Equivalent Proxies**:
- "Breadcrumb indicator appears" -> NOT the same as Skill() invocation
- "Unit test passes" -> Proves format, not execution
- "Directive was injected" -> Tells AI what to do, not that it did it

**Exact Success Evidence**: Tool event with `name='Skill'` and `skill='gto'` in transcript
```

**Red Flag Phrases** (indicate missing observable definition):
- "The system should work"
- "Fix applied successfully"
- "Tests pass" (without showing user-visible outcome)
- "Directive was injected" (without verifying AI followed it)

**When you see these phrases**, STOP and ask:
- "What exactly should the user see when this works?"
- "What would prove this is NOT working?"

---

### 1B. Ambiguity Resolution (CONDITIONAL)

**IF** the user report is vague or contradictory, **THEN**:
- [ ] User report is clear and falsifiable
- [ ] OR: Clarification questions asked and answered
- [ ] OR: Most literal interpretation stated as assumption

**Ambiguity Triggers**:
- "it kinda works but not really"
- "sometimes Skill() runs but other times it doesn't"
- "there's something wrong with X"
- "it's not working right"

**Clarification Protocol**:
Ask 2-3 focused questions about observables, NOT solutions:
- "What exactly do you see when you run /gto?"
- "What output should appear when it works?"
- "Can you copy-paste the exact error or output?"

**If user cannot clarify**:
1. Proceed with most literal interpretation
2. State assumption explicitly: "Assuming you mean X because..."
3. Note: "If this assumption is wrong, please clarify"

---

## Gate 2: Evidence Completeness (Before Synthesis)

**Before forming hypotheses or declaring root cause, verify evidence completeness**:

**MANDATORY Checklist**:
- [ ] Mechanism evidence collected (code paths, implementation)
- [ ] State evidence collected (runtime state, logs, files)
- [ ] Outcome evidence collected (user observables, tool outputs)
- [ ] OR: Empty bucket documented with justification

**Triple-Collection Framework** (see references/action-graph-and-triple-collection.md):
- **Bucket 1: Mechanism** - How is it implemented?
- **Bucket 2: State** - What does runtime look like?
- **Bucket 3: Outcome** - What does user see?

**Empty Bucket Protocol**:
- If bucket genuinely empty: Document WHY + require 2x evidence from others
- Confidence penalty: 1 empty -> max 60%, 2 empty -> max 40%

---

## Gate 3: Pre-Response (Before Declaring "Fixed")

**Before stating "working", "fixed", "resolved", or contradicting user report**:

**MANDATORY Checklist**:
- [ ] I observed the real symptom (not just assumed)
- [ ] I observed the real success condition (not just proxies)
- [ ] I am proving behavior (not just proving mechanism)
- [ ] I can state what would falsify my claim

**Evidence Template**:
```markdown
### Investigation Evidence Summary

**1. Symptom Evidence**
- User quote: "[exact words]"
- Tool output showing symptom: [Bash/Skill result]
- Reproduced: [YES/NO]

**2. Success Condition Evidence**
- Expected behavior: [what should happen]
- Actual behavior: [what actually happened]
- Success verified: [YES/NO] - Tool invocation shown / workflow demonstrated
- Falsifying test: [what would prove this wrong]

**3. Proxy Check**
- Direct evidence: [tool transcript, screenshot, runtime state]
- Proxy signals to ignore: [breadcrumb, directive, unit test]
- Behavior proven (not proxy): [YES/NO]

**4. Verification Status**
- [ ] Q1: Real symptom observed
- [ ] Q2: Success condition verified
- [ ] Q3: Behavior not proxy
- [ ] Q4: Falsifying evidence stated
```

**If ANY checkbox fails**:
- State what's missing: "I haven't verified X yet"
- State next step: "Need to check Y to confirm"
- Leave status as "Investigating" or "Proposed fix"

---

## Gate 4: Convergence (Before Declaring Root Cause)

**MANDATORY before declaring root cause with >=85% confidence**:

**Convergence Checklist**:
- [ ] Confidence score >= 0.85 (calculated from base + multipliers)
- [ ] Evidence tier documented (Tier 0-4)
- [ ] Hypothesis #1 tested (confirmed or eliminated)
- [ ] Search completeness validated (all implementations found)
- [ ] Gap analysis performed (all symptoms explained)
- [ ] Fix verified (tested and working)
- [ ] External parity checked (docs/CHS/CKS cross-reference)

**STOP if ANY gate fails.** Do not declare root cause until all gates pass.

---

## Tiered Mandatory System

To prevent alert fatigue, gates use a tiered system:

**CRITICAL Gates** (Always enforced, no exceptions):
- Gate 1A: Observable Definition
- Gate 2: Evidence Completeness
- Gate 3: Pre-Response
- Gate 4: Convergence
- User Report Disproof Protocol

**CONDITIONAL Gates** (Enforced when triggered):
- Gate 1B: Ambiguity Resolution (triggered by vague/contradictory reports)

**BEST_PRACTICE Gates** (Recommended but not blocking):
- Internet research (Step 0.75)
- Pattern learning check (Step 1.4)
- Architecture review (fix optimality)

---

## Post-Mortem Template

**After RCA completion, create a post-mortem:**

```markdown
**Impact:** [who/what affected]
**Duration:** [investigation time]
**MTTR:** [Mean Time To Resolve]

**Root cause:** [technical explanation]

**Timeline:**
- [Time] - Incident detected
- [Time] - Root cause identified
- [Time] - Fix deployed
- [Time] - Verification complete

**Action items:**
- [ ] Add monitoring for [pattern]
- [ ] Update rca with [new pattern]
- [ ] Update [documentation] with lessons learned

**Follow-up:** [date for review]
```
