# Agent Configuration Details

## 12-Agent Discovery Configuration (Comprehensive Multi-File Analysis)

Each agent scores findings on the 10-dimension analysis rubric (see SKILL.md), weighting by its specialty.

**NOTE:** Comprehensive configuration covering all code quality dimensions: security, logic, performance, quality, I/O, testing, Python modernization, cross-file analysis, duplicates, async concurrency, and business logic correctness. Agents run in parallel for efficient discovery.

### Agent Assignments

| Agent | Type | Focus | Specialty Dimensions |
|-------|------|-------|---------------------|
| 1 | `adversarial-security` | Security/I/O | Auth, injection, data exposure, path traversal |
| 2 | `adversarial-logic` | Logic/Concurrency | Conditionals, operators, flow, TOCTOU, race conditions |
| 3 | `adversarial-performance` | Performance | Leaks, bottlenecks, N+1, algorithmic complexity |
| 4 | `adversarial-quality` | Code Quality | Tech debt, maintainability, conventions, type system |
| 5 | `adversarial-io-validation` | I/O Safety | File operations, external assumptions, path validation |
| 6 | `adversarial-testing` | Test Quality | Test coverage gaps, brittle tests, missing scenarios |
| 7 | `python-simplifier` | Python Modernization | Python 3.14+ patterns, type hints, modern idioms |
| 8 | `taint-propagation` | Cross-File Security | Taint analysis for path traversal, input sanitization across modules |
| 9 | `circular-dependency` | Architecture | Circular import detection, layering violations, abstraction leaks |
| 10 | `duplicate-detection` | Code Duplication | AST-based duplicate function/class detection across files |
| 11 | `async-concurrency` | Async Safety | Shared state mutation in async, module-level mutable state |
| 12 | `domain-correctness` | Business Logic | Requirements alignment, domain rules, edge cases, mental execution |

### What Changed (Comprehensive Integration)

**Integrated from specialized review skills:**
- `meta-review` → Split into `taint-propagation` and `circular-dependency` agents
- `python-backend-reviewer` → Split into `duplicate-detection` and `async-concurrency` agents  
- `code-reviewer-business-logic` → Integrated as `domain-correctness` agent

**New capabilities from `/code-review`:**
- Health Score calculation: `100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`
- Synthesis phase between DISCOVER and DEDUPLICATE
- Prioritized findings report with severity grouping

### Agent Launch Protocol

- **Parallel launches**: All 12 agents run concurrently for efficient discovery
- **Total discovery time**: ~3 minutes (parallel execution)
- **Output format**: Each agent writes findings via `Write` tool (not `Bash`) to avoid shell quoting issues
- **Verification requirement**: Each agent MUST read the actual file at the reported line before including findings. Confirmed code = VERIFIED (confidence 95+); description-only inference = UNVERIFIED
- **Minimum finding quality**: Every finding requires non-empty `description`, `file`, `line`, and `confidence`. Discard findings with empty descriptions or confidence below threshold
- **Graceful degradation**: If any agent fails or times out, skip it and continue with remaining agents

## Output Paths

- Artifacts dir: `P://.claude/.artifacts/{terminal_id}/refactor/`
- Output path: `{artifacts_dir}/{target}/refactor/findings-{agent-name}.json`
- terminal_id resolution: `CLAUDE_TERMINAL_ID` → `WT_SESSION` → `ConEmuServerPID` → `console_unknown`

### Findings Reuse

If `{artifacts_dir}/{target}/refactor/findings-*.json` files exist from a prior `--dry-run`, skip DISCOVER and go directly to DEDUPLICATE unless `--rediscover` is specified.

## Context7 Integration

When synergy-type=modernize (deprecated API updates), invoke `/context7` before recommending replacements.

### Query Expansion Pattern

- Bad: "replace deprecated requests"
- Good: "current best practice for replacing deprecated requests.Session() in Python with httpx async"
- Mode: `code_only` (familiar replacements); `full` (unfamiliar library)
- Pin version if specific version mentioned

### Query Examples

| Deprecated | Query Expansion |
|------------|----------------|
| `requests` | "replace requests.Session() with httpx async client Python" |
| `pd.DataFrame.append` | "pandas DataFrame append deprecation replacement merge/concat" |
| `datetime.utcnow()` | "Python datetime timezone-aware replacement for utcnow()" |
| `mock.patch.object` | "unittest.mock patch.object vs patch for method replacement" |

## Health Score Integration

After DISCOVER phase, the synthesis module calculates:

```python
Health Score = 100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)
Score is capped at 0-100 range
```

**Interpretation:**
| Score | Meaning |
|-------|---------|
| 80-100 | Healthy — Low risk, minor improvements |
| 50-79 | Warning — Significant issues, address HIGH first |
| Below 50 | Critical — Systemic problems, do not deploy without fixes |

The Health Score is displayed in the PLAN phase output.

## Manual Invoke Options

For specialized deep-dives, invoke these agents manually:

```bash
# Architectural analysis (coupling, cohesion, domain integrity)
/refactor <path> --architecture

# Skip test analysis for non-Python code
/refactor <path> --no-testing
```
