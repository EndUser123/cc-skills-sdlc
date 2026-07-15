# Improvement Governance Real-Data Validation Report

**Generated:** 2026-07-15T04:27:35Z
**Schema:** hypothesis-evaluation-report.v1
**Elapsed:** 0.02s

## 1. Dataset

- Runs analyzed: **3**
- Outcome categories: `{'accept-with-concerns': 1, 'accept': 1, 'redo': 1}`
- Evidence available: `{'has_run_record': 0, 'has_discovery_evidence': 0, 'has_completion_review': 0, 'has_falsification': 0}`
- Repositories: `none`

### Evidence Availability

- Run records: 0/3
- Discovery evidence: 0/3
- Completion reviews: 0/3
- Falsification results: 0/3

## 2. Generated Hypotheses

Total: **3**
Distinct runs: **3**

### By Type
- `positive_first_pass_validation`: 2
- `possible_discovery_gap`: 1

### Hypothesis Inventory

**1. positive_first_pass_validation**
   - Statement: Run completed successfully with no evidence issues — positive outcome without discovery correlation
   - Confidence: 0.4
   - Supporting: ['lifecycle_status=completed', 'no_verdict_issues']
   - Counter: []
   - Source runs: ['example-accept-with-concerns', 'example-accept']
   - Impact: 0.2, Evidence quality: 0.4
   - _Usefulness: interesting_but_low_value
   - _Actionability: requires_more_investigation

**2. positive_first_pass_validation**
   - Statement: Run completed successfully with no evidence issues — positive outcome without discovery correlation
   - Confidence: 0.4
   - Supporting: ['lifecycle_status=completed', 'no_verdict_issues']
   - Counter: []
   - Source runs: ['example-accept']
   - Impact: 0.2, Evidence quality: 0.4
   - _Usefulness: interesting_but_low_value
   - _Actionability: requires_more_investigation

**3. possible_discovery_gap**
   - Statement: No findings produced and no prior evidence was retrieved — possible discovery scope gap
   - Confidence: 0.7
   - Supporting: ['finding_count=0', 'evidence_retrieved=false', 'qa_verdict=redo']
   - Counter: ['finding count may be valid if no issues exist']
   - Source runs: ['example-redo']
   - Impact: 0.6, Evidence quality: 0.4
   - _Usefulness: valuable
   - _Actionability: actionable

## 3. Quality Metrics

### Signal Quality
- Valuable: 1 (33.3%)
- Interesting: 2
- Noise: 0 (0.0%)
- Actionable: 1 (33.3%)

### Pattern Quality
- Hypotheses per run: 1.0
- Dedup ratio: 0.67
- Recurring surface groups: 2

### Review Burden
- Expected per 10 runs: ~10.0 hypotheses
- Estimated review time: ~0.1 min

## 4. Failure Modes Tested
- `generic_hypothesis`: ✅
- `false_causality_alternatives_preserved`: ✅
- `not_all_redos_become_discovery_gap`: ✅

## 5. Human Review Worksheet

| # | Type | Statement | Usefulness | Actionability |
|---|------|-----------|------------|--------------|
| 1 | positive_first_pass_ | Run completed successfully with no evidence issues — positiv | interesting_but_low_value | requires_more_investigation |
| 2 | positive_first_pass_ | Run completed successfully with no evidence issues — positiv | interesting_but_low_value | requires_more_investigation |
| 3 | possible_discovery_g | No findings produced and no prior evidence was retrieved — p | valuable | actionable |

## 6. Legend

- **usefulness**: valuable / interesting but low value / noise / already known / insufficient evidence
- **actionability**: actionable / requires more investigation / not actionable
