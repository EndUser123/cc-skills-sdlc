# Pattern Validation Template

**Purpose**: Prevent false positive bugs by validating detection patterns against adversarial examples BEFORE implementation.

**When to use**: REQUIRED for all detector modules with word-set or regex-based detection patterns.

**Related bug**: Bare "has" pattern in unverified_stance_detector.py triggered false positives on "This file has a bug".

---

## Template Structure

For each detection pattern in your module, complete ALL sections below:

### Pattern: [pattern_name]

**Category**: [e.g., FACTUAL_INDICATORS, SYCOPHANTIC_DOUBT, EMPTY_HEDGE]

**Pattern string or regex**:
```
[e.g., "has", "let me verify", r'\b\d+[kmb]\b']
```

---

### 1. Positive Examples (SHOULD trigger detection)

**Requirement**: Minimum 3 examples that MUST trigger detection.

| Example | Expected Match | Why This Should Trigger |
|---------|---------------|------------------------|
| "PyTorch has 100k stars on GitHub" | ✓ "has" | Factual claim with quantity |
| "React has 200k GitHub stars" | ✓ "has" | Adoption metric with number |
| "This library has millions of users" | ✓ "has" | Scale indicator with quantity |

**Validation**:
- [ ] All positive examples trigger detection
- [ ] Matched substring is correct
- [ ] No false negatives

---

### 2. Negative Examples (should NOT trigger detection)

**Requirement**: Minimum 3 examples that MUST NOT trigger detection.

| Example | Should Match? | Why This Should NOT Trigger |
|---------|--------------|-----------------------------|
| "This file has a bug" | ✗ NOT factual claim | "has" used in general statement, no quantity |
| "The code has a syntax error" | ✗ NOT factual claim | Error description, not adoption metric |
| "This approach has merit" | ✗ NOT factual claim | Opinion, not measurable claim |

**Validation**:
- [ ] All negative examples do NOT trigger detection
- [ ] No false positives
- [ ] Pattern is scoped to factual claims only

---

### 3. Edge Cases

**Requirement**: Test boundary conditions and malformed inputs.

| Input | Expected Behavior | Why This Matters |
|-------|------------------|------------------|
| "Has" at start: "Has 100k stars" | ✓ Should trigger | Word position independence |
| "Has" in question: "How many stars has it?" | ✗ Should NOT trigger (questions excluded) | Question handling logic |
| Empty string: "" | ✗ Should NOT trigger | No crash, graceful degradation |
| Whitespace only: "   " | ✗ Should NOT trigger | No crash, graceful degradation |
| Multiple "has": "Has X has Y" | ✓ Should trigger once | Duplicate handling |

**Validation**:
- [ ] All edge cases handled correctly
- [ ] No crashes on malformed inputs
- [ ] Graceful degradation documented

---

### 4. Pattern Soundness Analysis

**Question 1: Could this pattern match non-factual statements?**

**Answer**: [YES/NO and explain]

**If YES**: How will you prevent false positives?
- [ ] Word context check (e.g., require numbers nearby)
- [ ] Phrase-level matching (e.g., "used by" not just "used")
- [ ] Exclusion list (e.g., skip if question mark present)
- [ ] Other: _________________

**Question 2: What assumptions does this pattern make?**

**Answer**: [List assumptions]

Examples:
- "Assumes 'has' with numbers indicates factual claim"
- "Assumes 'let me verify' is hedge only when not followed by tool usage"
- "Assumes transcripts contain 'role' and 'content' keys"

**Question 3: How would an adversarial user trigger false positives?**

**Answer**: [Describe attack vectors]

Examples:
- "User says 'This has been reviewed' to trigger detection without factual claim"
- "User phrases statement as question to bypass detection"
- "User uses slang/idioms that match pattern but aren't factual"

**Mitigation**: [How will you prevent these attacks?]

---

### 5. Integration Tests

**Requirement**: Verify pattern works correctly in full detector flow.

| Scenario | Input | Expected Output | Actual Output |
|----------|-------|-----------------|---------------|
| Happy path | Valid factual claim with pattern | Detection triggered | ✓ PASS / ✗ FAIL |
| Sad path | Non-factual claim with pattern word | No detection | ✓ PASS / ✗ FAIL |
| Edge case | Empty user message | No crash, returns None | ✓ PASS / ✗ FAIL |
| Integration | Pattern + tool usage verification | Detection blocked if tools used | ✓ PASS / ✗ FAIL |

**Validation**:
- [ ] All integration tests pass
- [ ] Pattern works correctly with other detector logic
- [ ] No interaction bugs

---

### 6. Documentation

**Update plan.md Test Strategy section with**:
- [ ] Pattern description
- [ ] Positive test cases
- [ ] Negative test cases
- [ ] Edge case coverage
- [ ] Integration test scenarios

**Update module docstring with**:
- [ ] Pattern rationale
- [ ] Known limitations
- [ ] False positive mitigation strategies
- [ ] Examples of correct usage

---

## Approval

**Developer**: [Your name]

**Date**: [YYYY-MM-DD]

**Ready for implementation?**: [ ] YES [ ] NO

**If NO, what blockers remain?**:
- [ ] Pattern needs refinement
- [ ] More test cases needed
- [ ] Edge cases not handled
- [ ] Other: _________________

**Reviewer approval**: [ ] APPROVED [ ] NEEDS REVISION

---

## Usage Instructions

1. **Copy this template** for each detection pattern in your module
2. **Complete ALL sections** before writing any implementation code
3. **Review with peer or using adversarial testing** before approving
4. **Attach completed template to plan.md** as Appendix A
5. **Implement pattern** using template as specification
6. **Verify against template** during TRACE phase (Phase 8)

**Remember**: A few hours of pattern validation prevents weeks of false positive debugging!

---

**Version**: 1.0  
**Related bugs**: unverified_stance_detector.py Bug #1 (bare "has" false positive)  
**Created**: 2026-03-04  
**Owner**: /code skill Phase 4 (PLAN)
