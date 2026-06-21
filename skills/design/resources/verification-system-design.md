# Universal Claim Verification System - Design Document

## Overview

A verification framework that requires evidence for all claims (delete, yagni, performance, security, correctness) before proposals can proceed. Consists of:
1. `/verify` skill - claim classification and verification
2. Claim verifiers - per-category verification logic
3. Evidence store - artifact registry for benchmarks, metrics
4. Optional PreToolUse gate - auto-verify findings

## Current State

**Existing verification (partial):**
- Stop hooks verify deletion claims via `os.scandir()` (Stop_deletion_verification_guard.py)
- Verification engine validates citations against tool events (verification/engine.py)
- Benchmark system runs model comparisons (ai-api/benchmark_suite.py)

**Missing verification:**
- ponytail-audit findings (delete/yagni/stdlib/native/shrink claims)
- Performance claims in ADRs (no benchmark citation)
- Architecture complexity claims (no metrics)
- Model comparison claims from memory (no file citation)

## Component Design

### 1. Claim Classifier

```python
# skills/verify/__lib/claim_classifier.py
@dataclass
class Claim:
    text: str
    claim_type: Literal["delete", "yagni", "stdlib", "native", "performance", "security", "correctness"]
    artifact: str  # What the claim is about (e.g., "SELF_VERIFIED")
    evidence_required: str  # What evidence type is needed
    evidence_path: str | None  # If provided in claim
```

**Classification rules:**
| Pattern | Claim type | Evidence required |
|---------|-----------|-------------------|
| "delete", "unused", "dead code" | delete | grep shows 0 usage |
| "yagni", "only one consumer", "unnecessary abstraction" | yagni | grep shows ≤1 consumer |
| "stdlib", "standard library ships" | stdlib | Name stdlib function |
| "native", "platform already does" | native | Name platform feature |
| "faster", "speedup", "2-5x", "performance" | performance | Benchmark file path |
| "model X outperforms Y", "better at domain" | model_comparison | `.data/ai-api/benchmarks/` or `domain-model-weights.json` |
| "prevents race condition", "thread-safe" | security | Lock order proof |
| "handles all edge cases" | correctness | Test coverage report |

### 2. Verifier Interface

```python
# skills/verify/__lib/verifiers/base.py
from abc import ABC, abstractmethod

class Verifier(ABC):
    @abstractmethod
    def verify(self, claim: Claim, context: dict) -> tuple[bool, str]:
        """Return (passed, reason)."""
        pass
```

**Concrete verifiers:**
- `DeleteVerifier` - grep for usage, exclude definition lines
- `YagniVerifier` - grep for instantiations, count consumers
- `StdlibVerifier` - verify stdlib function exists
- `NativeVerifier` - verify platform feature exists
- `PerformanceVerifier` - read benchmark file, verify claim matches data
- `ModelComparisonVerifier` - read `.data/ai-api/benchmarks/` or `domain-model-weights.json`
- `SecurityVerifier` - check for lock order or proof patterns

### 3. Evidence Store Schema

```json
{
  "evidence_registry": {
    "benchmarks": {
      "artifact_type": "file",
      "allowed_paths": [".data/ai-api/benchmarks/", ".data/benchmarks/"],
      "required_format": "json",
      "versioned": true
    },
    "complexity_metrics": {
      "artifact_type": "file",
      "allowed_paths": [".data/metrics/complexity/"],
      "required_format": "json",
      "versioned": true
    },
    "test_coverage": {
      "artifact_type": "file",
      "allowed_paths": [".data/pytest-coverage/"],
      "required_format": "json",
      "versioned": false
    }
  }
}
```

### 4. /verify Skill Contract

**Input:**
```markdown
## Proposal: [title]

[proposal text with claims]

## Evidence

[evidence sections or empty]
```

**Output:**
```markdown
## Verification Report

### Claims
| Claim | Type | Status | Evidence |
|-------|------|--------|----------|
| [claim text] | [type] | PASS/FAIL | [evidence or reason] |

### Summary
Passed: N, Failed: M, Blocked: [list of blocking failures]

### Required Action
[What to do to fix failures]
```

### 5. PreToolUse Gate (Optional)

**Trigger patterns:**
- ponytail-audit output format
- Design skill proposals without evidence section
- ADRs with performance claims without citations

**Gate logic:**
```python
def PreToolUse_verify_gate(data):
    if is_proposal(data) and has_claims(data) and not has_evidence(data):
        claim_text = extract_claims(data)
        result = invoke_verify_skill(claim_text)
        if result["failed"] > 0:
            block_with_evidence(result)
```

## Data Flow

```
┌─────────────┐
│ ponytail    │
│ audit       │
└──────┬──────┘
       │ findings (delete/yagni/...)
       ▼
┌─────────────┐    Verify      ┌────────────────┐
│ /verify     │──────────────►│ Claim Classifier│
│ skill       │                └────────┬───────┘
└─────────────┘                         │
                                        │
                              ┌─────────▼─────────┐
                              │  Verifier Router  │
                              └─────────┬─────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                │                       │                       │
        ┌───────▼───────┐      ┌──────▼──────┐      ┌───────▼──────┐
        │ DeleteVerifier│      │YagniVerifier│      │PerfVerifier  │
        └───────┬───────┘      └──────┬──────┘      └───────┬──────┘
                │                      │                      │
                │                      │                      │
        ┌───────▼───────┐      ┌──────▼──────┐      ┌───────▼──────┐
        │ grep tool     │      │ grep tool    │      │ read benchmark│
        └───────┬───────┘      └──────┬──────┘      └───────┬──────┘
                │                      │                      │
                └──────────────────────┼──────────────────────┘
                                       │
                              ┌────────▼─────────┐
                              │ Verification    │
                              │ Report          │
                              └──────────────────┘
```

## Integration Points

### ponytail-audit Enhancement

**Before (current output):**
```
delete VerificationStatus.SELF_VERIFIED. [path]
yagni IntentClass class with only static attributes. [path]
```

**After (enhanced output):**
```
delete VerificationStatus.SELF_VERIFIED. replacement: [evidence: grep SELF_VERIFIED --count=10 path] [path]
yagni IntentClass class with only static attributes. replacement: [evidence: grep "class IntentClass" --count=1 path] [path]
```

### design skill Enhancement

**Before (current flow):**
1. Audit-First Protocol
2. Template routing
3. Emit proposal

**After (enhanced flow):**
1. Audit-First Protocol
2. Claim extraction → evidence requirements
3. Check if evidence provided
4. **If missing evidence:** invoke `/verify` before proposal emission
5. Template routing (only if verification passes)
6. Emit proposal with evidence citations

### ADR Template Enhancement

**New required section:**

```markdown
## Verification Evidence

[for each non-trivial claim:]

**Claim:** [claim text]
**Evidence Type:** [benchmark/file/metric/test]
**Evidence Path:** [relative path to artifact]
**Verification Command:** [how to verify, e.g., "python scripts/verify_claim_X.py"]
```

## Testability Contract

### Critical-Path Behaviors

| Behavior | Module Path | Verification Method | Tier |
|----------|-------------|---------------------|------|
| Claim classification | `skills/verify/__lib/claim_classifier.py` | Test with known claim patterns | critical |
| Delete verification | `skills/verify/__lib/verifiers/delete_verifier.py` | Mock grep, verify count logic | critical |
| Performance verification | `skills/verify/__lib/verifiers/performance_verifier.py` | Mock benchmark read, verify claim parsing | critical |
| Evidence path validation | `skills/verify/__lib/evidence_store.py` | Test allowlist, reject invalid paths | critical |

### Quality Gates

All critical-tier behaviors must achieve:
- ≥80% mutation coverage (mutmut)
- ≥95% line coverage (pytest-cov)

## Consequences

### Happy Path
- All claims in proposals have required evidence
- Automatic verification catches missing evidence before proposals proceed
- ponytail-audit findings are self-verifying
- ADRs include evidence citations for all non-trivial claims

### Failure Modes
- False positive: valid claim blocked due to evidence parsing error → Mitigation: manual override flag
- False negative: invalid claim passes due to weak verification → Mitigation: tighten verifier rules
- Performance impact on large finding sets → Mitigation: async verification, batch processing

### Rollback Criteria
If verification blocks >20% of valid proposals without user intervention, revert to advisory mode.

## Implementation Plan

### Phase 1: Core verify skill (2-3 days)
1. Create `/verify` skill structure
2. Implement claim classifier
3. Implement base verifier interface
4. Implement DeleteVerifier and YagniVerifier
5. Test with ponytail-audit output

### Phase 2: Evidence integration (2-3 days)
1. Create evidence store schema
2. Implement PerformanceVerifier with benchmark reading
3. Implement ModelComparisonVerifier
4. Test with ai-api benchmarks

### Phase 3: Integrations (2-3 days)
1. Enhance ponytail-audit output format
2. Modify design skill to invoke `/verify`
3. Add ADR evidence section to template
4. Test end-to-end flows

### Phase 4: Optional PreToolUse gate (1-2 days)
1. Design gate trigger patterns
2. Implement gate with verify skill invocation
3. Test with various proposal formats
4. Measure false positive rate

## Open Questions

1. **Should verification be blocking or advisory?** (Configurable per claim type)
2. **How to handle new claim types?** (Extensible verifier registration)
3. **Where to store verified findings?** (Evidence store vs in-memory)
4. **Should verification artifacts be versioned?** (For audit trail)

## Dependencies

- Existing: `verification/engine.py` (can reuse verdict patterns)
- Existing: `evidence_store.py` (can reuse tool event loading)
- New: evidence store schema
- New: verify skill structure