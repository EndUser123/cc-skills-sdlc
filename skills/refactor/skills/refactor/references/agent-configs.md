# Agent Configuration Details

## 8-Agent Discovery Configuration

Each agent scores findings on the 8-dimension analysis rubric (see SKILL.md), weighting by its specialty.

### Agent Assignments

| Agent | Type | Focus | Specialty Dimensions |
|-------|------|-------|---------------------|
| 1 | `adversarial-compliance` | Bugs/Logic | Immutability (race conditions, error handling, TOCTOU) |
| 2 | `adversarial-performance` | DRY/Simplicity | Object Calisthenics (duplication, extraction, concurrency) |
| 3 | `adversarial-performance` (tuned `--focus performance`) | Performance | Performance (leaks, bottlenecks, N+1, algorithmic) |
| 4 | `adversarial-quality` | Conventions | Naming, Type System (type hints, patterns, maintainability) |
| 5 | `python-simplifier` | Python 2025 | Simplicity (async patterns, modern standards) |
| 6 | `/ai-pi-zai-glm51` | Architecture | Coupling/Cohesion, Domain Integrity |
| 7 | `/ai-pi-mm-m27` | Testing | Coverage gaps, missing scenarios, brittle tests |
| 8 | `/ai-gemini` | Deep insight | Semantic bugs, idiom violations |

### Agent Launch Protocol

- **Stagger launches**: 30 seconds apart to avoid context flooding
- **Output format**: Each agent writes findings via `Write` tool (not `Bash`) to avoid shell quoting issues
- **Verification requirement**: Each agent MUST read the actual file at the reported line before including findings. Confirmed code = VERIFIED (confidence 95+); description-only inference = UNVERIFIED
- **Minimum finding quality**: Every finding requires non-empty `description`, `file`, `line`, and `confidence`. Discard findings with empty descriptions or confidence=0
- **Graceful degradation**: If any agent fails or times out, skip it and continue with remaining agents

### Output Paths

- Artifacts dir: `P:/.claude/.artifacts/{terminal_id}/refactor/`
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
