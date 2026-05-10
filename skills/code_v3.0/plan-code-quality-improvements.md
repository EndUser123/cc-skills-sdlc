# Plan: /code Quality Improvements - Pattern Validation

**Status**: Ready for TDD
**Route**: Fast route (standard implementation, ≤2 files, local work)
**Execution Model**: Standard implementation

## Overview

Complete the quality enforcement improvements by implementing the pattern validation script and tests. Documentation is already integrated into SKILL.md.

**Three tasks**:

## Architecture

**Module structure**:
```
P:\\\\\\.claude/skills/code/
├── scripts/
│   ├── pattern_validation.py      # CREATE - Validates detector patterns
│   └── verify_plan_compliance.py   # EXISTS - Complete
├── tests/
│   ├── test_pattern_validation.py    # CREATE - Test pattern validation
│   └── test_verify_plan_compliance.py # CREATE - Test plan compliance
└── templates/
    └── pattern_validation.md        # EXISTS - Template
```

## Data Flow

```
PLAN Phase
  ↓
Step 4.6: Pattern Validation (uses template)
  ↓
TDD Phase
  ├─ Task 1: Create pattern_validation.py
  ├─ Task 2: Create test_pattern_validation.py
  └─ Task 3: Create test_verify_plan_compliance.py
  ↓
TEST Phase
  ├─ pytest tests/test_pattern_validation.py
  └─ pytest tests/test_verify_plan_compliance.py
  ↓
AUDIT Phase
  └─ ruff check scripts/
  ↓
DONE Phase
  └─ Pre-Done Checklist (all checkboxes pass)
```

## Error Handling

- Script validation: Check regex patterns before use
- Missing files: Graceful degradation with clear error messages
- Test failures: Clear error reporting with expected vs actual

## Test Strategy

### Task 1: pattern_validation.py
- **Happy path**: Valid pattern passes all checks
- **Sad path**: Invalid regex detected, context conflict detected
- **Edge cases**: Empty pattern, None input, malformed files

### Task 2: test_pattern_validation.py
- Test PatternIssue class creation
- Test validate_detector_patterns function
- Test with real patterns from unverified_stance_detector.py

### Task 3: test_verify_plan_compliance.py
- Test extract_planned_tests parsing
- Test extract_implemented_tests counting
- Test compliance checking logic

## Standards Compliance

**Python standards** (/code-python):
- Type hints for all functions
- Docstrings for all modules and functions
- pytest for testing
- ruff for linting

**Universal principles** (/code-standards):
- DRY: Reuse validation logic
- SoC: Separate validation from implementation
- Testing: 100% coverage for validation scripts

## Ramifications

**Impact on existing code**:
- No changes to existing /code workflow
- Adds new validation capability
- Tests directory gains 2 new test files

**Backwards compatibility**:
- Fully compatible
- New scripts are optional tools
- SKILL.md already updated to reference them

## Pre-Mortem

**Failure Mode 1**: pattern_validation.py has bugs in regex validation
- **Prevention**: Test with real patterns from unverified_stance_detector.py
- **Test**: Include adversarial pattern examples in tests

**Failure Mode 2**: Tests fail due to path issues
- **Prevention**: Use Path objects consistently, normalize paths in tests
- **Test**: Run tests on both Windows and Unix-style paths

**Failure Mode 3**: Pattern validation too strict/lenient
- **Prevention**: Make validation advisory-only in some modes
- **Test**: Include flags for strict vs advisory mode

## Observability

**What to measure**:
- Do detector authors use the template?
- Does pattern validation catch false positives?
- How often does verify_plan_compliance fail?

**Alert thresholds**:
- Zero uses in 1 month: Template/script not discoverable
- High failure rate on validation: Validation too strict

**Diagnosis locations**:
- Template usage: grep for "pattern_validation.md" in hooks/
- Script effectiveness: Test fail logs
- Documentation: SKILL.md Step 4.6

## Implementation Tasks

### Task 1: Create scripts/pattern_validation.py

**Acceptance criteria**:
- PatternIssue NamedTuple defined
- validate_detector_patterns() function works
- Checks for context keyword conflicts
- Checks for over-matching (common words)
- Validates regex syntax
- Returns list of PatternIssue objects

**Test evidence**: Tests pass for:
- Valid patterns with no issues
- Invalid regex patterns detected
- Context keyword conflicts caught
- Common word over-matching caught

### Task 2: Create tests/test_pattern_validation.py

**Acceptance criteria**:
- test_pattern_issue_creation
- test_validate_no_issues
- test_validate_regex_error
- test_validate_context_conflict
- test_validate_overmatching
- 100% coverage for pattern_validation.py

**Test evidence**: All tests pass, coverage ≥80%

### Task 3: Create tests/test_verify_plan_compliance.py

**Acceptance criteria**:
- test_extract_planned_tests_from_strategy
- test_extract_planned_tests_from_bullets
- test_extract_implemented_tests_counting
- test_compliance_pass_match
- test_compliance_fail_mismatch
- test_compliance_no_plan
- test_compliance_no_test_file

**Test evidence**: All tests pass, coverage ≥80%

---

**Pre-mortem complete** → Proceed to TDD Phase
