# Agent Configuration Details

## 12-Agent Discovery Configuration (Comprehensive Multi-File Analysis)

Each agent scores findings on the 10-dimension analysis rubric (see SKILL.md), weighting by its specialty.

**NOTE:** Comprehensive configuration covering all code quality dimensions: security, logic, performance, quality, I/O, testing, Python modernization, cross-file analysis, duplicates, async concurrency, and business logic correctness. Agents run in parallel for efficient discovery.

### Agent Assignments

All 12 are dedicated `refactor-discovery-*` agent files (in `cc-skills-sdlc/agents/`), fail-closed: `tools: Read, Grep, Glob, Write` — **no Bash, no Edit**. A discovery agent that cannot mutate cannot silently change the code under review (#1120: the `tools:` field is hard enforcement, not advisory). They are distinct from the shared `adversarial-*` family (which carries `Bash` and serves `/red-team` / `/code-review`); `/refactor` dispatches the fail-closed variants.

**Dispatch contract:** every agent's system prompt points at `references/discovery-agent-contract.md`, which encodes the three non-negotiable invariants — multi-terminal isolation, stale-data immunity, and cross-directory scope. The orchestrator binds the absolute findings path into each dispatch prompt; agents never resolve scoping keys themselves.

| # | Agent file | Focus | Specialty Dimensions |
|---|-----------|-------|---------------------|
| 1 | `refactor-discovery-security` | Security | Auth, injection, data exposure, path traversal, trust boundaries |
| 2 | `refactor-discovery-logic` | Logic | Conditionals, operators, flow, precedence, copy-paste var errors |
| 3 | `refactor-discovery-performance` | Performance | Leaks, bottlenecks, N+1, TOCTOU, unbounded growth |
| 4 | `refactor-discovery-quality` | Code Quality | Tech debt, maintainability, redundant state, dead code, type gaps |
| 5 | `refactor-discovery-io` | I/O Safety | File ops, external assumptions, path validation, encoding, platform paths |
| 6 | `refactor-discovery-testing` | Test Quality | Coverage gaps around changed code, brittle tests, wrong-reason passes |
| 7 | `refactor-discovery-modernize` | Python Modernization | Deprecated stdlib/API, type hints, modern idioms (match, generics) |
| 8 | `refactor-discovery-taint` | Cross-File Security | Taint source→sink across modules, sanitization-context mismatches |
| 9 | `refactor-discovery-circular` | Architecture | Circular imports, layering violations, abstraction leaks (transitive cycles) |
| 10 | `refactor-discovery-duplicates` | Code Duplication | DRY violations — same/near-same logic copied across files |
| 11 | `refactor-discovery-async` | Async/Concurrency | Shared mutable state, missing await, module-level mutable state, races |
| 12 | `refactor-discovery-domain` | Business Logic | Requirements alignment, domain invariants, edge cases, mental execution |

**Cross-directory mandate (constraint 3):** agents 8–11 are cross-file by definition, but EVERY agent traces symbols across the whole repo/module, not just the target path — `Grep` with no path restriction is the default. Duplication, circular imports, taint, and shared-state defects live at file/layer boundaries the target path alone never reveals.

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

- Artifacts dir: `P:/.claude/.artifacts/{session_id}/refactor/{target_slug}/`
- Findings path: `{artifacts_dir}/findings-{agent-name}.json`
- **Scoping key: `session_id`** (the full runtime session UUID from `$CLAUDE_SESSION_ID` or the transcript filename stem) — **NOT** `terminal_id` / `$WT_SESSION`. Those are shared across concurrent Claude sessions inside one Windows Terminal, so two `/refactor` runs in the same terminal would collide and corrupt each other's findings. The orchestrator resolves `session_id` once and binds the absolute findings path into every agent dispatch; agents never resolve scoping keys themselves (see `discovery-agent-contract.md`).

### Findings Reuse

If `{artifacts_dir}/findings-*.json` files exist from a prior `--dry-run` **in the same session**, skip DISCOVER and go directly to DEDUPLICATE unless `--rediscover` is specified. Cross-session reuse is forbidden — a different session's findings are stale data (constraint 2); re-discover fresh every run so every finding cites `file:line` evidence read this run.

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
