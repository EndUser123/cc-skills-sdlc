---
name: uci
description: "Unified Code Inspection with intelligent auto-detection. Override with --lite or --full flags."
---
# Unified Code Inspection (`/uci`)

## Purpose

Unified code inspection with **intelligent auto-detection** for code review and quality analysis. Automatically selects the appropriate review depth based on context signals.

**Note**: `/review` and `/adversarial-review` were consolidated into this skill on 2026-03-16. Use `/uci` directly.

## Quick Start

```bash
# Automatic mode detection (recommended)
/uci

# Force fast review (3 agents)
/uci --lite

# Force complete review (11+ agents)
/uci --full

# Review specific scope
/uci --scope=main...HEAD
```

## How Mode Detection Works

`/uci` automatically selects the appropriate mode based on:

| Signal | Impact | Example |
|--------|--------|---------|
| **Risk indicators** | High weight | `src/auth.py` → deep mode |
| **File count** | Medium weight | 15 files → standard mode |
| **Line count** | Medium weight | 2000+ lines → deep mode |
| **File types** | Low weight | `.md` only → triage mode |
| **Change type** | Medium weight | bug fix → standard mode |

## Mode Overview

| Mode | Agents | Duration | When Auto-Selected |
|------|--------|----------|-------------------|
| **triage** | 3 | 5-10 min | Small doc changes, 1-2 files, low risk |
| **standard** | 4 | 10-15 min | Typical code changes, 3-10 files |
| **deep** | 8 | 20-30 min | Security code, large changes, bug fixes |
| **comprehensive** | 11+ | 30-45 min | Auth/payments, 50+ files, infrastructure |

## Agent Registry

### Core Agents (triage mode)
- **logic**: Logical errors, edge cases, incorrect reasoning
- **tests**: Missing test scenarios, coverage gaps
- **security**: Data leaks, access control, injection vectors

### Extended Agents (standard/deep modes)
- **performance**: N+1 patterns, bottlenecks, async issues, TOCTOU race conditions
- **conventions**: Code style violations, pattern consistency
- **quality**: Maintainability risks, technical debt
- **compliance**: Spec/schema validation
- **qa**: Test coverage gaps, missing scenarios
- **state-machine**: State-transition bugs, TOCTOU issues, invalid states (deep mode only)

### Comprehensive Agents (comprehensive mode only)
- **simplification**: Cognitive load, premature abstractions, change atomicity
- **rca**: Root cause analysis with multi-agent reasoning
- **failure-modes**: Domain-aware anti-patterns with web research
- **deployment-safety**: Migration concerns, observability, rollback safety
- **python-modernization**: Python 3.12+ idioms, type hints, modern patterns
- **test-quality-roi**: ROI-focused coverage analysis
- **invariants**: ID collision, referential integrity, uniqueness constraints (NEW)
- **io-validation**: Path validation, file existence checks, external service assumptions (NEW)

### Blind Spot Detection (All Modes, ON BY DEFAULT)
- **cross-session coverage**: Detects categories with risk signals that haven't been checked recently
- **risk pattern scanning**: Scans code for security, performance, logic, compliance patterns
- **confidence-based reporting**: Only reports HIGH/MEDIUM findings when confidence >= 0.4 and signal_count >= 2
- **automated recommendations**: Suggests specific /uci --include= categories to run

### Per-Agent Triggers (ADDITIVE, All Modes)
Agents can fire additively on top of mode selection when their specific code patterns are detected. This means `adversarial-state-machine` can run in triage mode if the code contains `match`/`case` patterns, without requiring deep/comprehensive mode.

| Agent | Triggers When |
|------|---------------|
| `adversarial-state-machine` | `match`/`case`, `state=`, `transition_to`, `handle_*`, `process_*` patterns in path or code |
| `adversarial-io-validation` | `open(`, `path.join`, `.exists(`, `.mkdir(`, `shutil`, `read_text`, `write_text` |
| `adversarial-invariants` | `unique`, `uuid`, `constraint`, `atomic`, `transaction`, `dedupe`, `ON CONFLICT` |
| `adversarial-compliance` | `pydantic`, `BaseModel`, `@validator`, `schema`, `validate(`, `OpenAPI` |
| `python-modernization` | `.py` files with `Optional[`, `List[`, `@dataclass`, `match:` patterns |

Confidence thresholds prevent noise: 1 match = 30% (LOW), 2 matches = 60% (MEDIUM), 3+ = 70-100% (HIGH). Only triggers at >= 50% confidence.

## Key Features

### Impact/Effort Matrix
Every finding includes:
- **Impact**: HIGH (crashes, data loss) / MED ( degraded UX) / LOW (style)
- **Effort**: HIGH (days) / MED (hours) / LOW (minutes)

### Three-Tier Verdict
- **Ready to Merge**: No blockers/high, tests pass
- **Needs Attention**: Medium issues worth addressing
- **Needs Work**: Blockers/high or failing tests

### Scope Detection Priority
1. User-specified scope
2. Feature branch → `git diff main...HEAD`
3. Staged changes → `git diff --staged`
4. Latest commit → `git show HEAD`

### Pre-Existing Issue Detection
Distinguishes between:
- **MUST FIX BEFORE MERGE**: Issues in your diff
- **PRE-EXISTING ISSUES**: Problems that existed before your changes

### Evidence-Based Findings
- All findings must include `file:line` location
- At least one other agent must confirm same location
- No hallucinations: line numbers prevent fake findings

## Output Format

Supports `markdown` (default), `json`, and `summary` via `--format` flag. Markdown includes verdict, findings with impact/effort, and cross-agent validation. See `references/output-format-examples.md` for full examples.

## Architecture

See `references/designitecture.md` for the full system diagram including mode detection, context signals, and shared core layer.

## Intelligent Sequential Trigger

Conditionally triggers sequential agent execution when justified by code characteristics (state-heavy, concurrency, security-critical code). Default is quality-first mode: triggers sequential when it improves detection. 600% overhead acceptable for catching more bugs.

See `references/sequential-trigger.md` for two-phase evaluation, triggering conditions, and cost-constrained mode.

**Implementation**: `__lib/sequential_trigger.py`

## Workflow

See `references/workflow-details.md` for detailed steps:

1. **Scope Detection** - Auto-detect: user scope > feature branch > staged > latest commit
2. **Mode Detection** - Analyze signals, select triage/standard/deep/comprehensive
3. **Agent Selection** - Mode determines agent set

---

## PHASE GATE: Generation vs. Validation Separation

**STOP — Before any findings are reported:**

Steps 1-3 above are **generation** (discovery, selection, dispatch). Step 4 (agent execution) is also **generation**. Step 5 (finding aggregation) is **validation**.

**Do NOT mix generation with validation:**
- Agent execution outputs are evidence, not verdicts
- Aggregated findings become verdicts only after cross-agent validation
- Before aggregation: "Agent X found issue Y" (observation)
- After aggregation: "Issue Y is confirmed by 2+ agents" (verdict)

---

4. **Agent Execution** - Agents run in parallel with circuit breaker
5. **Finding Aggregation** - Cross-agent validation, impact/effort, pre-existing detection

---

**PHASE GATE: Stop before Output Generation**

```
STOP — Before any claims appear in output:

Aggregated findings require a SEPARATE validation step:
  1. Was the finding confirmed by multiple agents?
  2. Is the confidence threshold met (>= 0.4 for MEDIUM, >= 0.7 for HIGH)?
  3. Is this a pre-existing issue (existed before changes) or new issue?
  4. Is this a MUST FIX or a NICE TO HAVE?

Only after questions 1-4 are answered does the finding become a verdict.
```

---

6. **Output Generation** - markdown/json/summary

---

## Evidence-First Principles

Additional modes: `--assessment` (analyze only), `--dry-run` (preview agents/scope)

## Memory Integration

UCI integrates with CKS for cross-session learning: retrieve past findings before review, store high-confidence findings after. See `references/memory-integration.md` for metadata schema (AgentConsensus, CrossFileMetadata, ReviewMetadata), storeable findings thresholds, and learning loop.

**Module**: `lib/memory_integration.py` | **Tests**: `tests/test_enhanced_metadata.py`

## Dependencies

- Internal: Constitutional filter, consensus detection, memory integration (CKS)
- Internal: `/simplify` skill patterns for simplification agent (comprehensive mode)
- Internal: Adversarial agents (logic, tests, security, performance, quality, compliance, qa, rca, failure-modes)

## Reference Files

| File | Contents |
|------|----------|
| `references/designitecture.md` | System diagram, mode detection, shared core layer |
| `references/sequential-trigger.md` | Two-phase evaluation, triggering conditions |
| `references/workflow-details.md` | Step-by-step workflow, circuit breaker |
| `references/memory-integration.md` | CKS metadata schema, learning loop |
| `references/output-format-examples.md` | Markdown/JSON output examples |

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
