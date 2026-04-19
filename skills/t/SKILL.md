---
name: t
description: Context-aware adaptive testing with ToT enhancement - code flow tracing, incremental testing, advanced analytics, and branching test scenario exploration
version: "2.4.0"
status: stable
category: testing
triggers:
  - /t
  - /t <file>
  - /t --force-full
aliases:
  - /t
  - /t <target>
metadata:
  version: "2.4.0"
  compatibility: "claude-code"

suggest:
  - /test
  - /tdd
  - /verify
  - /qa

do_not:
  - summarize this skill instead of executing it
  - run full test suite for trivial changes (use incremental mode)
  - skip health check validation before testing
  - ignore solo-dev constraints when suggesting tests
---

## Code Editing Patterns

For Python code editing patterns and anti-patterns:
- **Authority**: /p Neural Cache
- **Example**: `/search "ThreadPoolExecutor KeyboardInterrupt immediate cleanup"`
- **Example**: `/search "string manipulation AST LibCST code editing"`

Reflect automatically propagates code editing learnings to /p. Query CKS for patterns.


# /t - Context-Aware Adaptive Testing

## Purpose

Adaptive testing command that automatically determines test scope and strictness based on:
- **Code flow analysis**: Trace dependencies via codemap to identify affected modules
- **Risk scoring**: Deterministic formula (tier x size x kind) to prioritize critical changes
- **Incremental scope**: Run only affected tests (400+ seconds saved on average)
- **Advanced analytics**: Caching, flaky detection, coverage trends, profiling, failure grouping

**When to use:**
- Working on a feature/bugfix -> `/t` (auto-detects from conversation, runs only affected tests)
- Quick change in utils/ -> `/t` (incremental scope, 400+ seconds saved)
- Core router logic change -> `/t` (high risk, runs all test types with full suite)
- Full refactor -> `/t --force-full` or `/test`
- Check test health over time -> `/t` (coverage trends, flaky tests, profiling)

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **No external dependencies**: All testing is local, privacy-preserving
- **Evidence-based**: Test results provide actual execution evidence
- **Windows-only**: Uses msvcrt.locking() for file locking (no Unix domain sockets)
- **TDD mandatory**: All code changes follow RED -> GREEN -> REFACTOR

### Technical Context

> See `references/python-regex.md` for Python regex best practices when writing test patterns.

- **Codemap reuse**: Leverages `P:\__csf\src\commands\cb\enhance_command.py::create_codemap()` for dependency analysis
- **Health check integration**: Reuses `P:\.claude\skills\test_health_check.py` utilities
- **Multi-terminal safe**: File-based locking with PID validation for concurrent sessions
- **Test types**: Functional, unit, regression, integration, intelligent

### Architecture Alignment
- Independent skill from `/test` (shares infrastructure, distinct behavior)
- Outputs `.test_gaps.json` for `/tdd` integration
- Integrates with `/verify` for pytest result sharing

### Test Selection Contract

Choose the smallest sufficient test mix for the change:

- **Unit tests** for pure logic, deterministic transforms, and local contracts.
- **Regression tests** for exact bug paths, restored behavior, and fixes that must not recur.
- **Integration tests** for boundaries, state, persistence, hooks, cross-module flows, or I/O that unit tests can mock away.
- **Smoke proofs** for hooks, routers, and resumable workflows where a mock could fake success.
- **Snapshot tests** for rendered output, generated docs, hook-injected text, and skill bodies; unit tests for the logic that produces that output.
- If the change is mostly local logic, start at unit level and only escalate when a boundary exists.
- If the change touches a boundary or state, do not stop at unit tests.
- If you are comparing plans, say which layer proves what and what a lower layer would miss.

## Modes

`/t` operates in 5 different modes:

| Mode | Description | When to Use |
|------|-------------|-------------|
| **smart** (default) | Intelligent multi-phase workflow: Discovery -> Plan -> Execute -> Verify | First time testing, exploring unknown codebase, want full analysis |
| **discovery** | Test coverage analysis and gap detection (from `/test`) | "What tests exist? What's missing?" |
| **execution** | Adaptive testing with risk scoring and analytics | Quick test run with incremental scope |
| **bisect** | Regression hunting via git bisect (from `/test-bisect`) | "When did this break?" Find bad commit |
| **comprehensive** | Run all testing modes | Full analysis across all dimensions |

## Your Workflow

### Smart Mode (Default - Multi-Phase Orchestration)

**When invoked without arguments, `/t` runs smart orchestration:**

**Phase 1: Discovery - What tests exist? What's missing?**
- Scan codebase for test files
- Classify tests by type (Unit, Integration, Edge Case, Error Path, Regression)
- Calculate coverage percentage
- Detect health issues and solo-dev violations
- Identify coverage gaps

**Phase 1.5: Test Quality Analysis**
- Run comprehensive test quality review using pr-test-analyzer
- Evaluates test coverage completeness and identifies untested code paths
- Checks test quality (assertions, fixtures, mocking)
- Reports coverage gaps with confidence scores (80+ threshold)

**Phase 2: Planning - Risk-Based Test Strategy**
- Analyze discovery results
- Determine testing strategy:
  - **Low coverage (<50%)** -> `comprehensive` - run full test suite
  - **Medium coverage (50-80%)** -> `targeted` - focus on affected modules
  - **Good coverage (>80%)** -> `incremental` - run affected tests only
- If no tests found -> HALT and recommend `/tdd` or manual test creation

**Phase 3: Execute - Running Tests**
- Execute tests according to plan
- If no target specified -> run all discovered tests
- If target specified -> run incremental scope for affected modules
- Track profiling, flaky tests, coverage trends
- Group failures by root cause

**Phase 4: Verify - Results Analysis**
- Generate comprehensive director report
- Surface coverage gaps and actionable next steps
- Provide AI-ready orders for test creation

**Phase 4.5: Code Quality Review**
- Run comprehensive code quality review using code-reviewer
- Reviews code for readability, maintainability, and project conventions
- Identifies code smells and anti-patterns
- Reports findings with confidence scores (80+ threshold)
- Enforces constitutional filter (Director + AI workforce: enterprise patterns OK when justified)

### Execution Mode (Direct Testing)

For targeted testing without full discovery. 15 steps from context extraction through report generation.

> See `references/execution-mode.md` for the full 15-step execution pipeline, validation rules, file listing, testing instructions, and success criteria.

## Validation Rules

- **Before testing**: Verify target files exist, validate paths are in project root
- **During testing**: All test execution must produce actual output (no synthesis)
- **After testing**: Verify test results before caching (no corrupted cache entries)
- **Multi-terminal**: Always acquire lock before cache operations, release after
- **Windows-only**: Use msvcrt.locking(), never Unix domain sockets or POSIX flock

## Execution Directive

For `/t` requests, execute this workflow:

```bash
# Main entry point
cd P:/.claude/skills/t && python __main__.py "target" --force-full

# With context-aware routing
python __main__.py  # Auto-detects from conversation
python __main__.py router.py  # Target specific file
python __main__.py --force-full  # Override: force full suite
```

## Usage

```bash
# Smart orchestration (default) - Discovery -> Plan -> Execute -> Verify
/t

# Specific modes
/t --mode discovery      # Test coverage analysis only
/t --mode execution       # Direct testing with analytics
/t --mode bisect         # Regression hunting
/t --mode comprehensive   # Run all testing modes

# Target specific file or module
/t router.py
/t auth/

# Force full test suite (ignore risk scoring)
/t --force-full
```

## Output Format

Output includes: Executive Summary, Decision Table, Incremental Test Scope, and Advanced Analytics (cache stats, flaky tests, coverage trends, slow tests, grouped failures).

> See `references/output-format.md` for complete output format examples.

## Integration with Existing Skills

- **`/test`** - Reuses test discovery patterns and health check utilities
- **`/tdd`** - Consumes `.test_gaps.json` for test-driven development
- **`/verify`** - Shares pytest results and coverage data

## Files

- `__main__.py` - Entry point with CLI argument parsing
- `t_core.py` - Context extraction + codemap integration
- `risk_scoring.py` - Deterministic risk formula
- `director_output.py` - Director-friendly formatting
- `windows_ipc.py` - Windows file locking primitives
- `incremental_testing.py` - Incremental test scope calculation
- `test_cache.py` - Test result caching
- `flaky_detection.py` - Flaky test detection
- `coverage_trends.py` - Coverage trend analysis
- `profiling.py` - Test execution profiling
- `failure_grouping.py` - Failure pattern grouping
- `code_map.py` - Codemap visualization wrapper

## Testing

Tests are located in `tests/`:
- `test_windows_ipc.py` - Windows file locking tests
- `test_risk_scoring.py` - Risk scoring determinism tests
- `test_codemap_integration.py` - Codemap reuse tests

```bash
cd P:/.claude/skills/t && python -m pytest tests/ -v
```

## Success Criteria

- Context extraction works (conversation-based, no git needed)
- Codemap reuse successful (leveraging enhance_command.create_codemap())
- Risk scoring is deterministic (same inputs -> same score)
- Multi-terminal safety (no corrupted cache, no deadlocks)
- All test types run (functional, unit, regression, integration, intelligent)
- Incremental testing works (400+ seconds saved on average)
- Test caching works (6+ seconds saved per run)
- Flaky detection flags intermittent failures
- Coverage trends track improving/degrading modules
- Profiling identifies slow tests (>5s)
- Failure grouping reduces noise by clustering root causes

## Tree-of-Thought (ToT) Integration (v2.2)

/t integrates Tree-of-Thought reasoning for enhanced adaptive testing scenario exploration. ToT generates branching test scenarios (happy path, edge case, failure mode, performance) scored by likelihood (sure/maybe/unlikely) during Phase 2 (Planning) and Phase 3 (Execute). ToT also enhances flaky detection, coverage trends, and failure grouping with scenario classification.

- **Opt-out**: `export ADAPTIVE_TESTING_NO_TOT=true`

> See `references/tot-integration.md` for full ToT branch types, workflow diagram, example output, analytics enhancements, and changelog.

## Reference Files

| File | Contents |
|------|----------|
| `references/python-regex.md` | Regex pattern string escaping best practices |
| `references/execution-mode.md` | Full 15-step execution pipeline, validation rules, files, testing, success criteria |
| `references/output-format.md` | Complete output format examples (executive summary, decision table, analytics) |
| `references/tot-integration.md` | ToT branch types, workflow, example output, analytics enhancements, changelog |
