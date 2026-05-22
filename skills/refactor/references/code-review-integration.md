# /refactor + /code-review Integration Design

## Executive Summary

Enhance `/refactor` to absorb `/code-review`'s capabilities by consolidating from 10 agents to 5 specialist agents, adding Health Score calculation, and introducing a synthesis phase. This addresses the timeout issues that caused `/refactor` to miss CRITICAL findings that `/code-review` caught.

## Problem Analysis

### Why `/code-review` Found Issues `/refactor` Missed

**Root Cause (Verified):** Agent timeout/skip due to staggered launches

- `/refactor` launches 10 agents, 30 seconds apart
- Agent #10 (`adversarial-io-validation`) runs at ~4.5 minutes after start
- With typical timeouts, agents 7-10 may be skipped
- `/code-review` uses 4 parallel agents, completing in ~2 minutes

**Evidence:**
- `/code-review`'s `adversarial-io-validation` agent explicitly searches for TOCTOU issues (verified from prompt at `P:/.claude/agents/adversarial-io-validation.md:49-50`)
- `/refactor` includes the same agent as #10 of 10
- The `/chs export` refactor run produced no artifacts for `adversarial-io-validation` findings

### Agent Overlap Analysis

| `/refactor` Agent | `/code-review` Equivalent | Overlap |
|-------------------|---------------------------|---------|
| `adversarial-bugs` | `adversarial-logic` | ✅ Logic bugs, conditionals |
| `adversarial-performance` (DRY) | `adversarial-quality` | ✅ Code quality, maintainability |
| `adversarial-performance` (perf) | `adversarial-performance` | ✅ Performance bottlenecks |
| `adversarial-quality` | `adversarial-quality` | ✅ Tech debt |
| `adversarial-security` | `adversarial-security` | ✅ Security, injection |
| `adversarial-io-validation` | `adversarial-logic` + `adversarial-security` | ⚠️ Partial overlap |
| `python-simplifier` | (none) | ❌ Python-specific |
| `/ai-pi-*` agents | (none) | ❌ Architecture/testing |
| `/ai-gemini` | (none) | ❌ Deep insight |

## Design: Enhanced `/refactor` Architecture

### Agent Consolidation (Option 2 Enhanced - Restored Missing Coverage)

**New 7-Agent Discovery Configuration:**

| Agent | Inherits From | Focus | Specialty Dimensions |
|-------|---------------|-------|---------------------|
| 1 | `adversarial-security` | Security/I/O | Auth, injection, data exposure, path traversal |
| 2 | `adversarial-logic` | Logic/Concurrency | Conditionals, operators, flow, TOCTOU, race conditions |
| 3 | `adversarial-performance` | Performance | Leaks, bottlenecks, N+1, algorithmic complexity |
| 4 | `adversarial-quality` | Code Quality | Tech debt, maintainability, conventions, type system |
| 5 | `adversarial-io-validation` | I/O Safety | File operations, external assumptions, path validation |
| 6 | `adversarial-testing` | Test Quality | Test coverage gaps, brittle tests, missing scenarios (RESTORED) |
| 7 | `python-simplifier` | Python Modernization | Python 3.12+ patterns, type hints, modern idioms (RESTORED) |

**Removed Agents:**
- `adversarial-bugs` → covered by `adversarial-logic`
- `adversarial-performance` (DRY) → covered by `adversarial-quality`
- `python-simplifier` → can be invoked manually via `/refactor <path> --python-simplify`
- `/ai-pi-*` agents → can be invoked manually for architecture/testing deep-dive
- `/ai-gemini` → removed to reduce timeout risk; semantic bugs caught by other agents

### Launch Protocol Changes

**Old:** 10 agents, 30 seconds apart → 4.5 minutes total (agent #10 at high timeout risk)
**New:** 7 agents, 30 seconds apart → 3 minutes total (all agents likely to complete)

**Benefits:**
- All 5 agents likely to complete before timeout
- Faster discovery phase
- Reduced context flooding
- Simpler agent set = more reliable

### Health Score Integration

Add Health Score calculation to PLAN phase output:

```python
def calculate_health_score(findings):
    """
    Calculate code health score from findings.
    Score = 100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2), capped at 0-100.
    """
    critical = sum(1 for f in findings if f.severity == 'CRITICAL')
    high = sum(1 for f in findings if f.severity == 'HIGH')
    medium = sum(1 for f in findings if f.severity == 'MEDIUM')
    low = sum(1 for f in findings if f.severity == 'LOW')
    
    score = 100 - (critical * 20 + high * 10 + medium * 5 + low * 2)
    return max(0, min(100, score))
```

**Interpretation:**
| Score | Meaning |
|-------|---------|
| 80-100 | Healthy — Low risk, minor improvements |
| 50-79 | Warning — Significant issues, address HIGH first |
| Below 50 | Critical — Systemic problems, do not deploy without fixes |

### Synthesis Phase

Add Phase 1.5 (between DISCOVER and DEDUPLICATE):

```
DISCOVER → SYNTHESIZE → DEDUPLICATE → EVIDENCE_VERIFY → PLAN → RED → ...
```

**Synthesis responsibilities:**
1. Consolidate findings from 5 agents
2. Calculate Health Score
3. Generate prioritized findings report
4. Identify P0/P1 CRITICAL and HIGH issues for EVIDENCE_VERIFY

### Workflow Changes

**Enhanced 16-Step Workflow:**

1. **PREFLIGHT** — Verify target, check git state
2. **DISCOVER** — 5-agent parallel analysis (30s stagger)
3. **SYNTHESIZE** — NEW: Consolidate findings + Health Score
4. **DEDUPLICATE** — Remove duplicate findings
5. **EVIDENCE_VERIFY** — Verify P0/P1 defects via targeted reads
6. **PLAN** — Create refactoring plan with Health Score
7-16. (unchanged)

## Implementation Plan

### Phase 1: Update Agent Configuration

**File:** `references/agent-configs.md`

Replace 10-agent configuration with 5-agent configuration.

```markdown
## 5-Agent Discovery Configuration

| Agent | Type | Focus | Specialty Dimensions |
|-------|------|-------|---------------------|
| 1 | `adversarial-security` | Security/I/O | Auth, injection, data exposure, path traversal |
| 2 | `adversarial-logic` | Logic/Concurrency | Conditionals, operators, flow, TOCTOU, race conditions |
| 3 | `adversarial-performance` | Performance | Leaks, bottlenecks, N+1, algorithmic complexity |
| 4 | `adversarial-quality` | Code Quality | Tech debt, maintainability, conventions, type system |
| 5 | `adversarial-io-validation` | I/O Safety | File operations, external assumptions, path validation |

### Agent Launch Protocol

- **Stagger launches**: 30 seconds apart (was 30s, unchanged)
- **Total discovery time**: ~2 minutes (was ~4.5 minutes)
- **Graceful degradation**: If any agent fails or times out, skip it and continue
```

### Phase 2: Add Synthesis Module

**File:** `scripts/synthesize_findings.py`

```python
"""Synthesize findings from specialist agents into consolidated report."""

import json
from pathlib import Path
from typing import List, Dict


def calculate_health_score(findings: List[Dict]) -> int:
    """Calculate code health score from findings."""
    critical = sum(1 for f in findings if f.get('severity') == 'CRITICAL')
    high = sum(1 for f in findings if f.get('severity') == 'HIGH')
    medium = sum(1 for f in findings if f.get('severity') == 'MEDIUM')
    low = sum(1 for f in findings if f.get('severity') == 'LOW')
    
    score = 100 - (critical * 20 + high * 10 + medium * 5 + low * 2)
    return max(0, min(100, score))


def consolidate_findings(findings_dir: Path) -> List[Dict]:
    """Load and deduplicate findings from all agent outputs."""
    findings = []
    for findings_file in findings_dir.glob("findings-*.json"):
        agent_findings = json.loads(findings_file.read_text())
        findings.extend(agent_findings)
    return findings


def synthesize_report(findings: List[Dict], session_dir: Path) -> Dict:
    """Generate synthesis report with Health Score."""
    health_score = calculate_health_score(findings)
    
    # Group by severity
    by_severity = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': []}
    for f in findings:
        severity = f.get('severity', 'LOW')
        if severity in by_severity:
            by_severity[severity].append(f)
    
    return {
        'health_score': health_score,
        'severity_counts': {k: len(v) for k, v in by_severity.items()},
        'findings_by_severity': by_severity,
    }
```

### Phase 3: Update SKILL.md

**File:** `SKILL.md`

Add synthesis phase to workflow documentation:

```markdown
## Workflow Summary

1. **Preflight & Discovery**: Identify hotspots with 5-agent parallel analysis.
2. **Synthesis**: Consolidate findings and calculate Health Score.
3. **Analysis**: Deduplicate findings and verify P0/P1 defects via targeted reads.
...
```

### Phase 4: Rollback Plan

**Feature flag:** Add `--legacy-agents` flag to use old 10-agent configuration.

**Implementation:**
- Keep `agent-configs.md.old` with original 10-agent config
- Add flag handling in `scripts/run_scan.py`
- Update SKILL.md with `--legacy-agents` documentation

## Testing Strategy

### Unit Tests

1. **Health Score Calculation**
   - Test score calculation with various severity combinations
   - Verify capping at 0-100 range
   - Test edge cases (all CRITICAL, all LOW, no findings)

2. **Synthesis Module**
   - Test findings consolidation from multiple agents
   - Test deduplication logic
   - Test severity grouping

### Integration Tests

1. **Discovery Phase**
   - Verify all 5 agents launch successfully
   - Verify agents complete within timeout
   - Verify findings are captured

2. **End-to-End**
   - Run `/refactor` on test codebase with known issues
   - Verify CRITICAL issues are now caught (TOCTOU, O(N²), etc.)
   - Verify Health Score is calculated and displayed

### Regression Tests

- Verify `/refactor` still works on existing test cases
- Verify characterization tests still pass
- Verify AST refactoring still works

## Migration Path

1. **Phase 1:** Update `agent-configs.md` (5 agents)
2. **Phase 2:** Add `synthesize_findings.py` module
3. **Phase 3:** Update SKILL.md workflow
4. **Phase 4:** Add unit tests for Health Score and synthesis
5. **Phase 5:** Run integration tests on `/chs export` target
6. **Phase 6:** Deploy with `--legacy-agents` rollback flag

## Success Criteria

1. ✅ All 5 agents complete before timeout (no skipped agents)
2. ✅ TOCTOU and I/O validation issues are caught (verified on `/chs export`)
3. ✅ Health Score is calculated and displayed in PLAN output
4. ✅ Discovery phase completes in < 3 minutes
5. ✅ All existing tests pass
6. ✅ Rollback flag (`--legacy-agents`) works

## References

- `/refactor` agent config: `references/agent-configs.md`
- `/code-review` protocol: `../code-review/__lib/adversarial_review_protocol.md`
- `/code-review` synthesis: `../code-review/phases/p2_synthesis.md`
- Analysis document: `P:/packages/search-research/.claude/.artifacts/refactor_code_review_integration_analysis.md`
