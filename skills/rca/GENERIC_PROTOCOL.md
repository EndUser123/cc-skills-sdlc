# Generic Debugging Protocol

**Status**: Adopted 2026-03-11
**Version**: 1.0.0
**Scope**: Universal debugging protocol for LLM-involved issues

---

## Overview

This protocol defines universal debugging principles applicable to any LLM + system combination. It is designed as a **generic-first** architecture: universal principles are defined independently, with domain-specific specializations as optional add-ons.

**Key principle**: The protocol operates on **observables** (what can be measured) rather than **proxies** (indirect signals like directives or breadcrumbs).

---

## Evidence Tier System

All claims about system behavior or root causes must be tagged with confidence levels based on evidence quality:

| Tier | Confidence | Evidence Requirement | Example |
|------|------------|---------------------|---------|
| **Tier 4** | 95% | Code review + runtime verification | Verified hook executes and produces expected output |
| **Tier 3** | 85% | Runtime state + logs | Hook enabled, state file shows execution, logs show output |
| **Tier 2** | 60% | Runtime state only | Hook enabled, state file exists (no log verification) |
| **Tier 1** | 40% | Static analysis | Code review shows hook should work |
| **Tier 0** | 20% | No evidence (speculation) | "This should work based on architecture" |

**Rule**: Maximum claim confidence cannot exceed tier ceiling.

**Disconfirmation**: Any negative evidence (e.g., stderr in hook output) automatically drops claim to Tier 0 regardless of other evidence.

---

## Universal Debugging Rules

These rules apply to **any** debugging scenario involving LLMs:

1. **Code matches runtime**: What the code says must match what actually runs. If code claims X but runtime shows Y, Y wins.
2. **Observables over proxies**: Trust actual measurements (tool events, log entries) over indirect signals (file presence, timestamps).
3. **Test your fix**: After diagnosis, verify the fix actually resolves the issue. No fix = incomplete diagnosis.
4. **Consider failure modes**: What could go wrong? Network timeouts, permission errors, malformed data.
5. **Circular dependencies**: Watch for situations where A requires B, but B requires A.
6. **Version skew**: Code vs config vs runtime - are they all the same version?
7. **Test isolation**: Does the test interfere with other tests? Shared state? Background processes?
8. **Platform differences**: Windows vs Linux vs macOS behavior can differ significantly.
9. **Cognitive load vs value**: Is a complex mechanism worth its complexity? If 5% confidence difference requires 50% more complexity, reconsider.
10. **Generic vs specialized**: Start with universal principles, add domain-specific details only where needed.

---

## Mechanism → State → Outcome Framework

All debugging follows this pattern:

1. **Mechanism**: What code or configuration should cause the behavior?
2. **State**: What is the current system state? (enabled/disabled, files present, config loaded)
3. **Outcome**: What actually happens? (success/failure, specific error, unexpected behavior)

**Debugging workflow**: Trace Mechanism → Verify State → Measure Outcome → Identify mismatch.

---

## Operationalization

### For Each Claim

1. **State confidence tier**: Which tier applies? (0-4)
2. **Tag claim explicitly**: `[Tier X]` prefix on claims
3. **Provide evidence**: Link to specific file:line, log output, or test result
4. **Disconfirmation check**: Look for negative evidence that could invalidate claim
5. **Document assumptions**: What are you assuming but not verifying?

### For Root Cause

1. **Map mechanism → state → outcome**: For each component
2. **Identify mismatches**: Where does expected differ from actual?
3. **Circular dependency check**: Are you assuming A to prove A?
4. **Consider proxies**: Are you measuring the thing, or a proxy for the thing?
5. **Test the diagnosis**: Verify that fixing the identified issue resolves symptoms

---

## Specialization Mechanism

This generic protocol can be specialized for specific domains by defining:

### Required Specialization Components

1. **Domain Observables**: What can be measured in this domain?
   - Examples: tool events, hook stderr, API responses, database queries
2. **State Artifacts**: Where is system state stored?
   - Examples: JSON files, database tables, environment variables
3. **Pipeline Stages**: What are the execution steps?
   - Examples: skill invocation → hook processing → response generation
4. **Failure Modes**: What can go wrong in this domain?
   - Examples: permission errors, timeouts, malformed input

### Specialization Template

## Specialization Template

When creating a domain-specific specialization, follow this structure:

### Required Header Metadata

```markdown
# [Domain] Specialization of Generic Debugging Protocol

**Status**: Adopted [DATE]
**Version**: [X.Y.Z]
**Domain**: [Clear domain description]
**Base Protocol**: GENERIC_PROTOCOL.md
```

### Required Sections

#### 1. Domain Observables (REQUIRED)

**Purpose**: List what can be measured in this domain
**Format**: Categorized by evidence tier (Tier 1-4)
**Structure**:
```markdown
## Domain Observables

What can be measured in the [domain] domain:

### [Observable Category] (Tier X-Y evidence)
- [Specific observable 1]: [what it measures]
- [Specific observable 2]: [what it measures]

### [Another Category] (Tier Z evidence)
- [Observable 3]: [what it measures]
```

**Example from hooks/skills**:
- Tool Events (Tier 3-4): Skill() invocations, Read/Write/Edit calls
- Hook Execution (Tier 3-4): Enabled/disabled state, process() execution
- Runtime State (Tier 2-3): State files, log files, environment variables
- Static Analysis (Tier 1): File existence, code review

**Validation**: ✓ Have at least 3 observable categories? ✓ Each observable maps to a tier?

---

#### 2. State Artifacts (REQUIRED)

**Purpose**: Document where system state is stored
**Format**: Structured list with location, format, content, usage
**Structure**:
```markdown
## State Artifacts

Where system state is stored:

### [Artifact Type Name]
- **Location**: [File path or directory]
- **Format**: [File format: JSON, JSONL, text, binary]
- **Content**: [What data is stored]
- **Usage**: [How it's used in debugging]
```

**Example from hooks/skills**:
- Hook State: Location `P:/.claude/hooks/state/`, Format JSON, Content enabled/executed_count/timestamp
- Skill Invocation Log: Location `P:/.claude/state/skill_invocations.jsonl`, Format JSONL, Content timestamp/skill_name/arguments

**Validation**: ✓ Each artifact has location? ✓ Each has format? ✓ Each has usage description?

---

#### 3. Pipeline Stages (REQUIRED)

**Purpose**: Document execution flow and debugging workflow
**Format**: Numbered stages with step-by-step flow
**Structure**:
```markdown
## Pipeline Stages

### [Flow Name 1]
1. **[Stage 1]**: [Description]
2. **[Stage 2]**: [Description]
...

### Debugging Flow
1. **[Step 1]**: [What to do]
2. **[Step 2]**: [What to do]
...
```

**Example from hooks/skills**:
- Skill Invocation Flow: Agent invokes → Skill loads → Tool calls → Hooks trigger → Returns output
- Debugging Flow: Observe symptom → Identify observables → Collect evidence → Map mechanism/state/outcome → Identify mismatch → Verify fix

**Validation**: ✓ At least 2 flows documented? ✓ Each flow has 3+ stages? ✓ Debugging flow included?

---

#### 4. Tier Mapping (REQUIRED)

**Purpose**: Define domain-specific evidence requirements for each tier
**Format**: Per-tier requirements with examples
**Structure**:
```markdown
## Tier Mapping (Domain-Specific)

### Tier 4: [Tier Name]
- **Requirements for [domain]**:
  - [Requirement 1]
  - [Requirement 2]
  - **Example**: "[Claim description]"
    - Evidence: [Evidence 1] (Tier X)
    - Evidence: [Evidence 2] (Tier Y)
```

**Example from hooks/skills**:
- Tier 4: Code review + runtime verification (code shows logic, state file shows execution, log shows behavior)
- Tier 3: Runtime state + logs (hook enabled, log file has entries)
- Tier 2: Runtime state only (hook enabled, no log verification)
- Tier 1: Static analysis (code review only, no runtime check)
- Tier 0: No evidence (speculation)

**Validation**: ✓ All 5 tiers (0-4) documented? ✓ Each tier has domain-specific requirements? ✓ Each tier has example?

---

#### 5. Common Failure Modes (REQUIRED)

**Purpose**: Document typical failures with diagnosis/verification
**Format**: Numbered list with symptoms, diagnosis, verification
**Structure**:
```markdown
## Common Failure Modes

### [N]. [Failure Mode Name]
**Symptoms**: [What user sees]
**Diagnosis**:
- [Check 1]
- [Check 2]
**Verification**: [How to confirm fix]
```

**Example from hooks/skills**:
1. Hook Not Executing: Check enabled, tool_matcher, hook type
2. Hook Producing Errors: Check stderr, exceptions, dependencies
3. Circular Dependency: Trace dependencies between phases

**Validation**: ✓ At least 5 failure modes? ✓ Each has symptoms? ✓ Each has diagnosis steps? ✓ Each has verification?

---

#### 6. Case Studies (OPTIONAL but RECOMMENDED)

**Purpose**: Document real examples with lessons learned
**Format**: Numbered cases with issue, mechanism, state, outcome, tier, lessons
**Structure**:
```markdown
## Case Studies

### Case [N]: [Case Title]
**Issue**: [What problem occurred]
**Mechanism**: [What code/config should cause behavior]
**State**: [What was the actual system state]
**Outcome**: [What actually happened]
**Tier**: [Tier achieved after fix]
**Lessons**: [What we learned]
```

**Example from hooks/skills**:
- Case 1: Skill Invocation Logger - Tier 4, direct observable better than proxy
- Case 2: Import Path Bug - Tier 4, Python needs parent in sys.path
- Case 3: Circular Dependency - Tier 4, generic-first resolves circularity

**Validation**: ✓ At least 2 case studies? ✓ Each has issue/mechanism/state/outcome? ✓ Each has lessons?

---

#### 7. Specialization Notes (REQUIRED)

**Purpose**: Document domain-specific differences and usage guidance
**Format**: Two subsections (Differences, When to Use)
**Structure**:
```markdown
## Specialization Notes

### Differences from Generic Protocol
- **[Difference 1]**: [Explanation]
  - [Detail]
- **[Difference 2]**: [Explanation]
  - [Detail]

### When to Use This Specialization
Use this specialization when debugging issues related to:
- [Trigger 1]
- [Trigger 2]

### When to Use Generic Protocol
Use generic protocol when:
- [Condition 1]
- [Condition 2]
```

**Example from hooks/skills**:
- Differences: Tier 3a/3b split removed, hook stderr = error behavior, import path requirements
- When to use specialization: Hook execution, skill failures, tool behavior, pytest failures
- When to use generic: Not hooks/skills specific, different LLM system, creating new specialization

**Validation**: ✓ At least 2 differences documented? ✓ Clear when to use specialization? ✓ Clear when to use generic?

---

#### 8. Maintenance (REQUIRED)

**Purpose**: Version tracking and related files
**Format**: Version history + related files list
**Structure**:
```markdown
## Maintenance

**Version history**:
- [DATE]: [Change description]

**Related files**:
- [File path 1]: [Purpose]
- [File path 2]: [Purpose]
```

**Validation**: ✓ Version history included? ✓ Related files documented?

---

### Specialization Validation Checklist

Before committing a new specialization, verify:

**Content Completeness**:
- [ ] All 7 required sections present (Observables, State Artifacts, Pipeline Stages, Tier Mapping, Failure Modes, Notes, Maintenance)
- [ ] Header metadata complete (Status, Version, Domain, Base Protocol)
- [ ] At least 3 observable categories
- [ ] At least 5 failure modes documented
- [ ] All 5 tiers (0-4) mapped with examples

**Quality Standards**:
- [ ] Each state artifact has location + format + usage
- [ ] Each failure mode has symptoms + diagnosis + verification
- [ ] Debugging flow included in Pipeline Stages
- [ ] At least 2 case studies (recommended) or 1 (minimum)

**Consistency with Generic Protocol**:
- [ ] Tier definitions match generic protocol (0-4 with same confidence ceilings)
- [ ] Universal rules referenced where applicable
- [ ] Specialization notes explain differences from generic

**Usability**:
- [ ] Clear "When to use this specialization" section
- [ ] At least 3 concrete trigger conditions listed
- [ ] Related files linked for cross-reference

**Canonical Example**: See `HOOKS_SKILLS_SPECIALIZATION.md` as reference implementation

---

## Usage

**For agents**: Follow the protocol when diagnosing issues. Tag claims with confidence tiers. Provide evidence for each claim.

**For reviewers**: Check that claims are tagged with appropriate tiers. Verify evidence quality. Watch for proxy mismatches.

**For implementers**: Create domain specializations using the template. Define observables, state artifacts, and pipeline stages specific to your domain.

---

## History

- 2026-03-11: Initial version created as generic-first architecture
- Derived from: hooks/skills debugging protocol (3-phase design)
- Refactored to: Remove circular dependency, enable immediate adoption
