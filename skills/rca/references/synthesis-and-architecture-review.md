# Synthesis Checkpoint & Architecture Review

## User Report Disproof Protocol (CRITICAL GATE)

**When user reports a failure/missing feature, their observable is ground truth.**

**MANDATORY RULE**: Never contradict a user's report without direct counter-evidence that **directly disproves** their observable.

**What this means**:
- User says: "Skill() was not invoked" -> GROUND TRUTH until proven otherwise
- User says: "I see error X" -> GROUND TRUTH until proven otherwise
- User says: "Feature Y doesn't work" -> GROUND TRUTH until proven otherwise

**Disproof Evidence Requirements**:
To contradict a user's report, you need ONE of:
1. **Direct observation**: "I ran /gto and saw Skill('gto') in the tool use list"
2. **Tool transcript**: "Tool use transcript shows: Skill(skill='gto')"
3. **Screenshot/video**: User-visible evidence showing the feature working
4. **Runtime proof**: Hook logs showing the tool was actually invoked

**Insufficient evidence** (DOES NOT disprove user report):
- "Unit test passes" -> Proves format, not execution
- "Code looks correct" -> Proves mechanism, not outcome
- "Directive was injected" -> Tells AI what to do, not that it did it
- "Breadcrumb indicator appears" -> Proves auxiliary indicator, not main feature

### WRONG Pattern

```
User: "there's no sign that Skill() was used"
Investigator: "Actually, the system is working. Here's what's happening:
              test_skill_invocation_indicator.py shows the breadcrumb..."

VIOLATION: Contradicted user without direct observable proof
Unit test != Skill() invocation evidence
Breadcrumb indicator != Skill() tool execution
```

### CORRECT Pattern

```
User: "there's no sign that Skill() was used"
Investigator: "You're right. I don't see Skill('gto') in the tool use list.
              Let me investigate why the Skill() tool wasn't invoked."

ACCEPTED user report as ground truth
ACKNOWLEDGED missing observable
FOCUSED on root cause investigation
```

### How to disprove (if you ACTUALLY have evidence):

```
User: "Skill() was not invoked"
Investigator: "I need to verify this. Let me check the tool transcript.

              [Checks transcript]

              Actually, I see Skill('gto') was called at line 42 of the transcript.
              Here's the evidence: [paste tool use entry]

              Can you clarify what you're seeing that suggests it wasn't invoked?"

DIRECT EVIDENCE: Tool transcript entry
SPECIFIC: Line number and tool name
RESPECTFUL: Asks for clarification, doesn't dismiss
```

### Enforcement Gate Checklist

Before stating "working", "fixed", "already implemented", or contradicting a user report:

- [ ] I have **directly observed** the user-visible behavior
- [ ] I have **tool transcript / log / screenshot** proving the claim
- [ ] My evidence is **Tier 3 or higher** (runtime state or user observable)
- [ ] I am **not relying on unit tests** to prove production behavior
- [ ] I am **not relying on code inspection** alone to prove execution
- [ ] If user reports missing feature, I have **attempted to reproduce** first

**If ANY checkbox fails**:
- State: "I haven't verified X yet"
- Do NOT claim "working" or "fixed"
- State next step: "Need to check Y to confirm"

---

## Synthesis Checkpoint

> **Stop and Analyze Before Continuing**
>
> After **3-5 relevant findings** or when findings **converge**:
> 1. List findings with sources
> 2. Build causal chain: A -> B -> Root Cause
> 3. State conclusion with confidence
> 4. Propose fix or remaining investigation

---

## Architecture Review for Fix Optimality (v2.8)

**Evaluates proposed fixes against architectural principles to prevent "fixes that cause more problems."**

### When to Trigger

**MANDATORY** during Synthesis Checkpoint step 4 ("Propose fix or remaining investigation"):
- Before finalizing any fix recommendation
- After root cause is identified with >=85% confidence
- Before declaring "RCA Complete"

### Architecture Review Checklist

| Dimension | Question | If Concern Found |
|-----------|----------|------------------|
| **Correctness** | Does this fix address root cause or symptom? | Re-examine causal chain |
| **Completeness** | Are all affected paths fixed? | Check for partial fixes |
| **Side Effects** | What new problems could this introduce? | Document risks |
| **Maintainability** | Does this follow existing patterns? | Check conventions |
| **Reversibility** | Can this be undone if wrong? | Add rollback plan |
| **Testability** | Can we verify this works? | Add verification steps |

### Red Flags: Fix Will Cause More Problems

| Red Flag | Example | Better Approach |
|----------|---------|-----------------|
| **Suppresses errors** | `try: ... except: pass` | Fix root cause, don't hide |
| **Adds workarounds** | "Add timeout to avoid hang" | Trace and fix blocker |
| **Disables features** | "Comment out broken code" | Fix implementation |
| **Bypasses validation** | "Add --force flag" | Fix validation logic |
| **Increases complexity** | "Add wrapper function" | Simplify underlying code |
| **Breaks patterns** | "Special case for X" | Find general solution |

### Output Format

```markdown
### Architecture Review

**Correctness:** [Addresses root cause / symptom]

**Side Effects:**
- [Potential issue 1]
- [Potential issue 2]

**Maintainability:** [Follows existing pattern / breaks pattern]

**Reversibility:** Score [1.0-2.0] (can rollback via [method])

**Alternative Approaches Considered:**
- Option A: [description] - Rejected because [reason]
- Option B: [description] - Rejected because [reason]
- **Selected: Current approach** - Best balance of [criteria]
```

### Enforcement

**Before declaring RCA complete**, verify:
- [ ] Architecture review completed (if fix recommended)
- [ ] No red flags in fix proposal
- [ ] Side effects documented and acceptable
- [ ] Alternative approaches were considered
- [ ] Fix is reversible or has rollback plan

**If fix fails architecture review**:
- State "Fix needs refinement" in RCA output
- Return to investigation or propose alternative
- Do NOT declare "RCA Complete" until fix is sound

### Integration with /arch Skill

**For complex fixes or architectural changes**, invoke `/arch` for comprehensive analysis:

```
When fix involves:
- Structural code changes (new modules, refactoring)
- Interface changes (API modifications, hook signatures)
- System boundaries (cross-component interactions)
- Performance implications (caching, async, threading)

Invoke /arch with:
"Review this proposed fix for [file]: [change description]

Evaluate:
1. Architectural alignment with existing patterns
2. Potential side effects or new problems
3. Whether this is the optimal solution
4. Alternative approaches with better trade-offs"
```
