# Plan: Skill Enhancement Integration - /gto, /reflect, /pre-mortem

**Status**: Phase 1-3 Complete (REQUIREMENTS, PRE-FLIGHT, EXPLORE done)
**Current Phase**: Phase 4 PLAN
**Route**: Auto route (subagents for non-trivial local work)
**Execution Model**: Subagents (3 independent tasks, ~9 hours total)

## Overview

Implement three high-ROI skill enhancements by borrowing proven capabilities from well-developed source skills (/r, /t) and integrating them into target skills (/gto, /reflect, /pre-mortem).

**Three Enhancements**:
1. **/gto + Risk Scoring** (3 hours): Add deterministic pre-mortem checks from /r skill to Gap Task Opportunities analyzer
2. **/reflect + CKS Schema** (4 hours): Replace unstructured YAML with /r's structured finding types (PATTERN, REFACTOR, DEBT, DOC, OPT)
3. **/pre-mortem + Objective Risk Formula** (2 hours): Replace subjective L×I scoring with /t's deterministic tier×size×kind formula

## Architecture

### Module Structure

```
skills/
├── gap-task-opportunities/     # Enhancement #1 target
│   ├── SKILL.md                # Update workflow steps
│   └── session_analyzer.py     # Add risk scoring module
├── reflect/                    # Enhancement #2 target
│   ├── SKILL.md                # Update output format
│   └── scripts/
│       └── reflect_hook.py     # Add CKS schema mapping
└── pre-mortem/                 # Enhancement #3 target
    ├── SKILL.md                # Update risk formula
    └── scripts/
        └── risk_calculator.py  # Add objective scoring
```

### Key Components

**Enhancement #1: /gto Risk Scoring**
- **Input**: TODO items from session scan
- **Processing**: Apply /r's deterministic pre-mortem checks (inversion analysis, rollback readiness, state integrity)
- **Output**: Enhanced TODO findings with risk_score, rollback_complexity, state_impact fields
- **Integration Point**: After step 4 in /gto workflow, before severity classification

**Enhancement #2: /reflect CKS Schema**
- **Input**: Unstructured YAML findings (category, severity, context, lesson, application)
- **Processing**: Map categories to /r's finding types (PATTERN, REFACTOR, DEBT, DOC, OPT)
- **Output**: Structured findings with CKS-compliant metadata
- **Integration Point**: `P:\__csf\src\core\retrospective_common.py:319-349` (store_to_cks function)

**Enhancement #3: /pre-mortem Objective Risk**
- **Input**: Subjective L×I scores (1-9 range, threshold ≥6)
- **Processing**: Apply tier×size×kind formula: `risk = (tier_weight × 0.5) + (size_weight × 0.3) + (kind_weight × 0.2)`
- **Output**: Decimal scores (0.0-1.0 range, threshold ≥0.7)
- **Integration Point**: Lines 122-154 in /pre-mortem SKILL.md (risk prioritization output)

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENHANCEMENT #1: /gto Risk Scoring            │
└─────────────────────────────────────────────────────────────────┘

Session Files → /gto Step 4 (scan) → TODO Items
                                          ↓
                          Deterministic Pre-Mortem Checks (/r)
                          - Inversion analysis
                          - Rollback readiness
                          - State integrity
                                          ↓
                          Enhanced TODO Findings
                          - risk_score (0.0-1.0)
                          - rollback_complexity (low/medium/high)
                          - state_impact (none/partial/full)
                                          ↓
                          Severity Classification (Critical/High/Medium/Low)

┌─────────────────────────────────────────────────────────────────┐
│                  ENHANCEMENT #2: /reflect CKS Schema            │
└─────────────────────────────────────────────────────────────────┘

Transcript Analysis → Unstructured Finding → Category Mapping
                                                      ↓
                                      /r Finding Types (PATTERN/REFACTOR/DEBT/DOC/OPT)
                                                      ↓
                                      Structured CKS Metadata
                                      - finding_type
                                      - severity_weight
                                      - category_confidence
                                                      ↓
                                      store_to_cks() (retrospective_common.py)

┌─────────────────────────────────────────────────────────────────┐
│              ENHANCEMENT #3: /pre-mortem Objective Risk         │
└─────────────────────────────────────────────────────────────────┘

Risk Scenario → Tier × Size × Kind → Objective Formula
                                                   ↓
                                   risk = (tier × 0.5) + (size × 0.3) + (kind × 0.2)
                                                   ↓
                                   Decimal Score (0.0-1.0)
                                                   ↓
                                   Threshold Check (≥0.7 = HIGH)
```

## Error Handling

**Enhancement #1: /gto Risk Scoring**
- **Error**: Missing tier/size/kind metadata
  - **Recovery**: Default to LOW risk (0.3), log warning, continue analysis
- **Error**: Invalid risk score (outside 0.0-1.0 range)
  - **Recovery**: Clamp to valid range, log error, flag for manual review

**Enhancement #2: /reflect CKS Schema**
- **Error**: Unknown category (no mapping to finding types)
  - **Recovery**: Default to PATTERN type, log warning, suggest category update
- **Error**: CKS store failure (missing required fields)
  - **Recovery**: Fall back to unstructured YAML, log error, continue with degraded mode

**Enhancement #3: /pre-mortem Objective Risk**
- **Error**: Missing tier/size/kind weights
  - **Recovery**: Use conservative defaults (tier=0.7, size=0.5, kind=0.5), log warning
- **Error**: Formula calculation error (division by zero, overflow)
  - **Recovery**: Return MEDIUM risk (0.5), log error, flag for manual review

## Test Strategy

### Happy Path Tests

**Enhancement #1: /gto Risk Scoring**
- Test: TODO item passes all three pre-mortem checks → risk_score 0.2 (LOW)
- Test: TODO item fails inversion analysis → risk_score 0.8 (HIGH)
- Test: TODO item fails rollback readiness → rollback_complexity HIGH
- Test: Risk score correctly influences severity classification

**Enhancement #2: /reflect CKS Schema**
- Test: "optimization" category → OPT finding type
- Test: "forgotten TODO" category → PATTERN finding type
- Test: "code quality issue" category → REFACTOR finding type
- Test: Structured metadata successfully stores to CKS

**Enhancement #3: /pre-mortem Objective Risk**
- Test: Tier CRITICAL × Size LARGE × Kind COMPLEX → risk 0.85 (HIGH)
- Test: Tier LOW × Size SMALL × Kind SIMPLE → risk 0.25 (LOW)
- Test: Decimal score 0.7 triggers HIGH threshold (was L×I=6)
- Test: Output format shows decimal scores, not 1-9 integers

### Edge Case Tests

**Enhancement #1: /gto Risk Scoring**
- Test: TODO item with missing metadata → defaults to LOW risk
- Test: Risk score exactly at threshold (0.7) → classified as HIGH
- Test: Multiple TODO items with mixed risk levels → correct prioritization

**Enhancement #2: /reflect CKS Schema**
- Test: Unknown category → defaults to PATTERN type
- Test: Empty finding → graceful handling, no crash
- Test: CKS store unavailable → falls back to unstructured YAML

**Enhancement #3: /pre-mortem Objective Risk**
- Test: Missing tier → uses conservative default (0.7)
- Test: Size or kind not specified → calculates with available weights only
- Test: Formula produces score > 1.0 → clamped to 1.0
- Test: Formula produces score < 0.0 → clamped to 0.0

### Integration Tests

**Test 1: /gto with risk scoring produces actionable TODO prioritization**
- Input: Session with 10 TODO items (3 HIGH risk, 4 MEDIUM, 3 LOW)
- Expected: Severity classification reflects risk scores
- Verification: HIGH risk items appear first in output

**Test 2: /reflect with CKS schema integrates with existing CKS infrastructure**
- Input: Transcript with 5 findings (mixed categories)
- Expected: All findings stored with correct finding_type metadata
- Verification: CKS query returns findings by type (e.g., all PATTERN findings)

**Test 3: /pre-mortem with objective formula produces consistent results**
- Input: Same risk scenario analyzed twice
- Expected: Identical risk scores (0.0-1.0 decimal)
- Verification: No L×I subjective variation between runs

### Regression Tests

- **/gto**: Existing TODO analysis still works, no output format breakage
- **/reflect**: Existing transcript analysis still produces findings, unstructured fallback works
- **/pre-mortem**: Existing risk assessment still identifies scenarios, only scoring format changed

## Standards Compliance

### Python Standards (/code-python)
- **Toolchain**: Python 3.14+, pytest for testing
- **Type Hints**: All functions use type annotations
- **Error Handling**: Explicit try-catch blocks with logging
- **Code Quality**: Follow PEP 8, use descriptive names, DRY principle

### Documentation Standards
- **SKILL.md Updates**: Document new capabilities, update workflow steps
- **Inline Comments**: Explain non-obvious logic (e.g., risk formula weights)
- **Changelog**: Add entry for each enhancement with version number

### CKS Integration Standards
- **Schema Compliance**: Use /r's finding type constants (PATTERN, REFACTOR, DEBT, DOC, OPT)
- **Metadata Requirements**: Include finding_type, severity_weight, category_confidence
- **Error Handling**: Graceful fallback to unstructured format if CKS unavailable

## Ramifications

### Breaking Changes

**Enhancement #1: /gto Risk Scoring**
- **Output Format**: New fields added (risk_score, rollback_complexity, state_impact)
- **Compatibility**: Backward compatible - existing fields preserved, new fields optional
- **Migration**: No migration needed - new fields are additive only

**Enhancement #2: /reflect CKS Schema**
- **Output Format**: Finding structure changes from unstructured to schema-based
- **Compatibility**: Backward compatible - unstructured fallback for missing categories
- **Migration**: Existing transcripts unaffected - only new analyses use CKS schema

**Enhancement #3: /pre-mortem Objective Risk**
- **Output Format**: Risk scores change from 1-9 integers to 0.0-1.0 decimals
- **Threshold**: HIGH risk threshold changes from ≥6 to ≥0.7
- **Compatibility**: NOT backward compatible - output format changes
- **Migration**: Update documentation, adjust user expectations for decimal scores

### Dependencies

**New Dependencies**: None (all borrow from existing /r and /t skills)

**Updated Dependencies**:
- /gto now depends on /r's pre-mortem check definitions
- /reflect now depends on /r's finding type constants
- /pre-mortem now depends on /t's risk formula weights

### Documentation Updates Required

1. **/gto SKILL.md**: Add step 4.5 for risk scoring, document new output fields
2. **/reflect SKILL.md**: Update output format section with CKS schema examples
3. **/pre-mortem SKILL.md**: Replace L×I scoring with tier×size×kind formula, update threshold

## Modernization Considerations

**Note**: This section is automatically generated during EXPLORE phase for Python projects. It identifies opportunities to modernize dependencies and patterns.

### Detected Divergences

**P0 (Critical)** - Security vulnerabilities, breaking API changes:
- *(No P0 issues detected)*

**P1 (High)** - Major performance improvements, deprecated features:
- *(No P1 issues detected)*

**P2 (Low)** - Minor improvements, cosmetic changes:
- *(No P2 issues detected)*

### Recommendation

**Status**: No modernization needed

**Rationale**: This project uses current best practices with no detected divergences from modern patterns.

### Your Choice

**Options**:
- [ ] Continue with current dependencies (recommended)
- [ ] Manually review specific libraries (if concerns noted above)

**Opt-Out**: To skip modernization detection for this project, check:
- `- [x] Skip modernization detection for this project`

*Note: Priorities are RECOMMENDATIONS, not blocks. Always-on detection helps identify opportunities but never prevents implementation.*

---

## Pre-Mortem Analysis (6-Month Failure Mode Analysis)

### Failure Mode #1: False Positive Risk Inflation (Enhancement #1)

**Scenario**: "It's 6 months from now and /gto is flagging everything as HIGH risk. Teams ignore it because it's too noisy."

**Root Cause**: Over-sensitive risk scoring, thresholds too low, check logic too strict

**Preventive Actions**:
- **Test**: Verify risk score distribution (expect: 20% HIGH, 50% MEDIUM, 30% LOW)
- **Guardrail**: Log risk score distribution during analysis, alert if >40% HIGH
- **Validation**: Manual review of 100 random TODO items, calibrate thresholds

**TRACE Scenario**: Verify risk calculation logic produces expected distribution

### Failure Mode #2: CKS Category Mapping Gaps (Enhancement #2)

**Scenario**: "It's 6 months from now and /reflect is defaulting 50% of findings to PATTERN type because category mapping is incomplete."

**Root Cause**: Insufficient category coverage, missing mappings, evolving categories

**Preventive Actions**:
- **Test**: Cover all common categories (optimization, quality, debt, documentation, patterns)
- **Guardrail**: Log unknown categories, alert if >10% default to PATTERN
- **Validation**: Review category mapping quarterly, add new categories from actual usage

**TRACE Scenario**: Verify category mapping covers expected finding types

### Failure Mode #3: Objective Formula Misalignment (Enhancement #3)

**Scenario**: "It's 6 months from now and users complain that the objective formula produces counter-intuitive results. A 'simple file rename' scores higher risk than a 'database migration'."

**Root Cause**: Incorrect weight distribution, missing context, formula not matching real-world risk

**Preventive Actions**:
- **Test**: Verify formula produces expected results for known scenarios (file rename = LOW, DB migration = HIGH)
- **Guardrail**: Add manual override option for edge cases, document rationale
- **Validation**: Compare formula results against human risk assessment for 50 scenarios

**TRACE Scenario**: Verify formula calculation produces expected risk ordering

## Observability Planning

### Metrics to Track

**Enhancement #1: /gto Risk Scoring**
- **Metric**: Risk score distribution (LOW/MEDIUM/HIGH percentage)
- **Alert**: If HIGH > 40% → possible false positive inflation
- **Diagnosis**: Check risk calculation logic, review thresholds, examine TODO item sample

**Enhancement #2: /reflect CKS Schema**
- **Metric**: Category mapping hit rate (known categories vs. PATTERN defaults)
- **Alert**: If PATTERN default > 10% → missing category mappings
- **Diagnosis**: Review unknown category logs, update mapping, add new categories

**Enhancement #3: /pre-mortem Objective Risk**
- **Metric**: Formula result distribution (LOW/MEDIUM/HIGH percentage)
- **Alert**: If distribution shifts significantly → formula drift
- **Diagnosis**: Check weight constants, verify calculation logic, compare against historical data

### Logs to Capture

- **Risk calculation details**: Input TODO metadata, applied checks, final score
- **Category mapping decisions**: Input category, matched type, confidence score
- **Formula computation**: Tier/size/kind inputs, weight values, calculation steps

### Where to Look During Diagnosis

1. **Logs**: Check skill execution logs for calculation details and error messages
2. **Output**: Review actual TODO findings / CKS entries / risk scores
3. **Tests**: Run regression tests to verify expected behavior
4. **Manual TRACE**: Use /trace on modified code to verify logic correctness

## Task Breakdown

### Enhancement #1: /gto + Risk Scoring (3 hours)

#### Task 1.1: Create risk_scoring.py module [2 hours]
- [ ] Define `RiskScore` dataclass (score, rollback_complexity, state_impact)
- [ ] Implement `deterministic_pre_mortem_checks()` function:
  - [ ] Inversion analysis: "What if we inverted the core assumption?"
  - [ ] Rollback readiness: "Can we revert this change cleanly?"
  - [ ] State integrity: "Is partial state possible?"
- [ ] Implement `calculate_risk_score()` function (combines three checks into 0.0-1.0 score)
- [ ] Add error handling (missing metadata → default LOW, invalid score → clamp)
- [ ] Write unit tests (happy path, edge cases, error handling)

**Evidence Required**:
- RED: 5 failing tests (happy path + 3 edge cases + 1 error case)
- GREEN: All 5 tests pass with correct risk calculations
- REFACTOR: Tests still pass after code cleanup (extract constants, add logging)
- VERIFY: Independent verifier confirms spec compliance + code quality + test coverage ≥80%

#### Task 1.2: Integrate risk scoring into /gto workflow [1 hour]
- [ ] Update `/gto SKILL.md`: Add step 4.5 after "Scan session files only"
- [ ] Call `calculate_risk_score()` for each TODO item
- [ ] Add risk-based fields to TODO output format
- [ ] Adjust severity classification to consider risk_score
- [ ] Write integration tests (verify TODO list reflects risk scores)

**Evidence Required**:
- RED: 3 failing integration tests (HIGH/MEDIUM/LOW risk scenarios)
- GREEN: All 3 tests pass with correct severity classification
- REFACTOR: Tests still pass after code cleanup (extract severity logic, add comments)
- VERIFY: Independent verifier confirms spec compliance + backward compatibility + test coverage ≥80%

### Enhancement #2: /reflect + CKS Schema (4 hours)

#### Task 2.1: Create CKS schema mapping [2 hours]
- [ ] Define `FINDING_TYPE_MAP` dictionary (category → finding_type mapping)
- [ ] Implement `classify_finding_type()` function (maps categories to PATTERN/REFACTOR/DEBT/DOC/OPT)
- [ ] Define `CKSMetadata` dataclass (finding_type, severity_weight, category_confidence)
- [ ] Add error handling (unknown category → default PATTERN, log warning)
- [ ] Write unit tests (happy path, edge cases, error handling)

**Evidence Required**:
- RED: 6 failing tests (5 finding types + 1 unknown category edge case)
- GREEN: All 6 tests pass with correct type classification
- REFACTOR: Tests still pass after code cleanup (extract mappings, add validation)
- VERIFY: Independent verifier confirms spec compliance + code quality + test coverage ≥80%

#### Task 2.2: Integrate CKS schema into store_to_cks() [1 hour]
- [ ] Update `store_to_cks()` in `retrospective_common.py:319-349`
- [ ] Call `classify_finding_type()` before storing to CKS
- [ ] Add CKS metadata fields to finding structure
- [ ] Add fallback to unstructured YAML if CKS store fails
- [ ] Write integration tests (verify CKS metadata is stored correctly)

**Evidence Required**:
- RED: 4 failing integration tests (5 findings × mixed categories)
- GREEN: All 4 tests pass with correct CKS metadata
- REFACTOR: Tests still pass after code cleanup (extract store logic, add error handling)
- VERIFY: Independent verifier confirms CKS integration + fallback behavior + test coverage ≥80%

#### Task 2.3: Update /reflect SKILL.md documentation [1 hour]
- [ ] Update output format section with CKS schema examples
- [ ] Document 5 finding types (PATTERN, REFACTOR, DEBT, DOC, OPT)
- [ ] Add troubleshooting section for category mapping issues
- [ ] Update workflow diagram with CKS integration step
- [ ] Write documentation tests (verify examples are accurate)

**Evidence Required**:
- RED: 3 failing documentation tests (examples produce described output)
- GREEN: All 3 tests pass with documented behavior
- REFACTOR: Tests still pass after documentation cleanup (clarify examples, add diagrams)
- VERIFY: Independent verifier confirms documentation accuracy + completeness + clarity

### Enhancement #3: /pre-mortem + Objective Risk Formula (2 hours)

#### Task 3.1: Create risk_calculator.py module [1.5 hours]
- [ ] Define `Tier`, `Size`, `Kind` enums with weight values
- [ ] Implement `calculate_objective_risk()` function:
  - [ ] Formula: `risk = (tier_weight × 0.5) + (size_weight × 0.3) + (kind_weight × 0.2)`
  - [ ] Clamp result to 0.0-1.0 range
- [ ] Implement `map_threshold()` function (≥0.7 = HIGH, ≥0.4 = MEDIUM, <0.4 = LOW)
- [ ] Add error handling (missing metadata → conservative defaults, clamp overflow)
- [ ] Write unit tests (happy path, edge cases, error handling)

**Evidence Required**:
- RED: 6 failing tests (3 tier/size/kind combinations + 2 edge cases + 1 error case)
- GREEN: All 6 tests pass with correct risk calculations
- REFACTOR: Tests still pass after code cleanup (extract weights, add logging)
- VERIFY: Independent verifier confirms spec compliance + code quality + test coverage ≥80%

#### Task 3.2: Update /pre-mortem SKILL.md with objective formula [0.5 hours]
- [ ] Replace L×I scoring section with tier×size×kind formula
- [ ] Update output format to show decimal scores (0.0-1.0) instead of 1-9 integers
- [ ] Update threshold from ≥6 to ≥0.7 for HIGH risk
- [ ] Add example calculations (LOW/MEDIUM/HIGH scenarios)
- [ ] Write integration tests (verify output format matches specification)

**Evidence Required**:
- RED: 3 failing integration tests (LOW/MEDIUM/HIGH risk scenarios)
- GREEN: All 3 tests pass with correct decimal scores and thresholds
- REFACTOR: Tests still pass after documentation cleanup (clarify examples, add diagrams)
- VERIFY: Independent verifier confirms output format compliance + threshold accuracy + test coverage ≥80%

## Success Criteria

- [ ] All 9 tasks complete (3 per enhancement)
- [ ] All RED/GREEN/REFACTOR/VERIFY evidence captured
- [ ] All tests pass (unit + integration + regression)
- [ ] TRACE phase completes without blocking issues
- [ ] Documentation updated (SKILL.md files reflect new capabilities)
- [ ] No regressions in existing skill functionality

## Execution Model

**Route**: Auto route (subagents for non-trivial local work)
**Model**: Subagents (default for sequential implementation)
**Task List**: Not required (local work, single terminal)

**Rationale**:
- Scope: 9 tasks across 3 independent enhancements
- Files: ~6-8 files modified (3 new modules + 3 SKILL.md updates)
- Risk: Medium (well-defined integrations, fallback strategies documented)
- Timeline: ~9 hours total

**Execution Order** (parallelizable):
1. Enhancement #1: Task 1.1 → Task 1.2 (3 hours)
2. Enhancement #2: Task 2.1 → Task 2.2 → Task 2.3 (4 hours)
3. Enhancement #3: Task 3.1 → Task 3.2 (2 hours)

**Note**: Enhancements are independent - can execute in any order or in parallel.
