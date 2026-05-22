# Agent Configuration Details

## 7-Agent Discovery Configuration (Enhanced with /code-review + Missing Coverage)

Each agent scores findings on the 10-dimension analysis rubric (see SKILL.md), weighting by its specialty.

**NOTE:** This enhanced configuration consolidates the original 10 agents into 7 focused specialists, absorbing capabilities from `/code-review` while restoring critical missing coverage (testing and Python modernization). Discovery completes in ~3 minutes.

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

### What Changed (Migration from 10 agents)

**Removed agents and rationale:**
- `adversarial-bugs` → absorbed by `adversarial-logic` (same coverage)
- `adversarial-performance` (DRY) → absorbed by `adversarial-quality` (code quality)
- `/ai-pi-zai-glm51` (architecture) → manual invoke for deep architectural analysis
- `/ai-pi-mm-m27` (testing) → replaced by `adversarial-testing` (better test focus)
- `/ai-gemini` (deep insight) → absorbed by `adversarial-logic` and `adversarial-quality`

**Restored agents (added back):**
- `adversarial-testing` → Test coverage gaps, brittle tests, missing edge cases
- `python-simplifier` → Python 3.12+ modernization, type hints, modern idioms

**New capabilities from `/code-review`:**
- Health Score calculation: `100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`
- Synthesis phase between DISCOVER and DEDUPLICATE
- Prioritized findings report with severity grouping

### Agent Launch Protocol

- **Stagger launches**: 30 seconds apart to avoid context flooding
- **Total discovery time**: ~3 minutes (was ~4.5 minutes with 10 agents)
- **Output format**: Each agent writes findings via `Write` tool (not `Bash`) to avoid shell quoting issues
- **Verification requirement**: Each agent MUST read the actual file at the reported line before including findings. Confirmed code = VERIFIED (confidence 95+); description-only inference = UNVERIFIED
- **Minimum finding quality**: Every finding requires non-empty `description`, `file`, `line`, and `confidence`. Discard findings with empty descriptions or confidence below threshold
- **Graceful degradation**: If any agent fails or times out, skip it and continue with remaining agents

### Rollback Option

To use the legacy 10-agent configuration:
```bash
/refactor <path> --legacy-agents
```

This uses `agent-configs.md.old` and skips the synthesis phase.

## Output Paths

- Artifacts dir: `P:\\\\.claude/.artifacts/{terminal_id}/refactor/`
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
