# GoT and ToT Enhancement Integration

## Overview

This skill now includes **Graph-of-Thought (GoT)** and **Tree-of-Thought (ToT)** cognitive enhancement features to improve analysis quality and depth.

## Features

### Graph-of-Thought (GoT) Enhancement

**What it does:**
- Extracts and categorizes nodes from plan Architecture sections (constraints, ideas, risks)
- Analyzes relationships between nodes (supports, contradicts, unrelated)
- Detects circular dependencies and architectural deadlock risks
- Provides architectural insights that might be missed in manual review

**When it runs:**
- Automatically during Phase 4 (PLAN) when creating or updating implementation plans
- After plan structure is complete, before TDD phase begins
- Only if plan.md has an Architecture section with relevant content

**Opt-out:**
- Use `--no-got` flag to disable GoT enhancement
- Set environment variable `SKILL_NO_GOT=true` to disable globally
- Example: `/code --no-got "implement feature X"`

### Tree-of-Thought (ToT) Enhancement

**What it does:**
- Generates branching reasoning paths for conditional logic in code
- Scores branches by likelihood (sure/maybe/unlikely)
- Prunes unlikely branches to focus on high-value execution paths
- Identifies edge cases and hidden error paths

**When it runs:**
- Automatically during Phase 8 (TRACE) when verifying code logic
- After manual TRACE completes, before error handling verification
- Only if traced code contains conditional logic (if/elif/else, for/while, try/except)

**Opt-out:**
- Use `--no-tot` flag to disable ToT enhancement
- Set environment variable `SKILL_NO_TOT=true` to disable globally
- Example: `/code --no-tot "implement feature X"`

## Usage Examples

### Enable All Enhancements (Default)

```bash
# Both GoT and ToT enabled by default
/code "implement user authentication"
```

### Disable Specific Enhancement

```bash
# Disable GoT only (skip architecture node analysis)
/code --no-got "implement user authentication"

# Disable ToT only (skip branch analysis)
/code --no-tot "implement user authentication"

# Disable both enhancements
/code --no-got --no-tot "implement user authentication"
```

### Disable via Environment Variable

```bash
# Disable GoT globally
export SKILL_NO_GOT=true
/code "implement feature X"

# Disable ToT globally
export SKILL_NO_TOT=true
/code "implement feature Y"

# Disable both globally
export SKILL_NO_GOT=true
export SKILL_NO_TOT=true
/code "implement feature Z"
```

## Design Philosophy

**Quality-First Design:**
- Both enhancements are **enabled by default** to maximize analysis quality
- Users must explicitly opt-out if they don't want the enhancement
- This aligns with the skill's philosophy of prioritizing quality over speed

**Independent Operation:**
- GoT and ToT flags work independently
- Disabling one does not affect the other
- Each enhancement has its own opt-out mechanism

**Constitutional Compliance:**
- Opt-out flags **do NOT bypass safety checks** (SEC-001)
- Safety verification runs regardless of enhancement settings
- Only the enhancement is disabled, not core safety mechanisms

## Performance

**GoT Enhancement:**
- Node extraction: < 1 second for typical plans
- Edge analysis: < 0.5 seconds for typical node counts
- Minimal overhead, significant value for complex architectures

**ToT Enhancement:**
- Branch generation: < 2 seconds for typical code files
- Branch scoring: < 0.5 seconds for typical conditionals
- Focuses TRACE effort on high-value paths

## Technical Details

### GoT Implementation

**Utils Module:** `P:/.claude/skills/code/utils/got_planner.py`

**Key Classes:**
- `GotPlanner`: Extracts nodes from plan Architecture sections
- `GotEdgeAnalyzer`: Analyzes relationships between nodes
- Edge types: supports, contradicts, unrelated
- Cycle detection: Identifies circular dependencies

**Node Categories:**
- **Constraints:** Requirements and limitations
- **Ideas:** Implementation approaches and strategies
- **Risks:** Potential issues and concerns
- **Components:** System boundaries and modules
- **Data flows:** Communication paths

### ToT Implementation

**Utils Module:** `P:/.claude/skills/code/utils/tot_tracer.py`

**Key Classes:**
- `BranchGenerator`: Generates branching reasoning paths
- Branch types: if statements, elif statements, for/while loops, try/except blocks
- Branch scoring: sure (high confidence), maybe (medium), unlikely (low)
- Branch pruning: Removes 'unlikely' branches to focus TRACE effort

**Integration Points:**
- Phase 4 (PLAN): GoT node extraction and edge analysis
- Phase 8 (TRACE): ToT branch generation and scoring

## Testing

All enhancements have comprehensive test coverage:

**GoT Tests:**
- Node extraction quality (8 tests)
- Edge analysis accuracy (9 tests)
- Opt-out flag behavior (10 tests)
- Total: 27 GoT-specific tests

**ToT Tests:**
- Branch generation quality (11 tests)
- Branch scoring accuracy (12 tests)
- Opt-out flag behavior (10 tests)
- Total: 33 ToT-specific tests

**Integration Tests:**
- Flag independence verification (10 tests)
- Constitutional compliance (10 tests)
- Quality-first design validation (10 tests)
- Total: 30 integration tests

**Overall: 90 tests passing** across all GoT/ToT functionality

## Troubleshooting

**Issue:** GoT enhancement not running during PLAN phase
- **Cause:** Plan.md lacks Architecture section or is malformed
- **Fix:** Ensure plan.md has proper Architecture section with Constraints/Ideas/Risks subsections

**Issue:** ToT enhancement not running during TRACE phase
- **Cause:** Traced code has no conditional logic
- **Fix:** This is expected behavior for linear code. ToT only enhances conditional code paths.

**Issue:** Enhancement running despite --no-got or --no-tot flag
- **Cause:** Environment variable may be overriding flag
- **Fix:** Check `SKILL_NO_GOT` and `SKILL_NO_TOT` environment variables; flags take precedence

## Further Reading

- **GoT Research:** "Graph-of-Thought: Solving Elaborate Problems with Large Language Models" (2023)
- **ToT Research:** "Tree-of-Thought: Deliberate Problem Solving with Large Language Models" (2023)
- **Implementation:** `P:/.claude/skills/code/utils/got_planner.py` and `tot_tracer.py`
- **Tests:** `P:/.claude/skills/code/tests/test_opt_out_flags.py`

## Version History

- **v2.22.0** (2026-03-09): Initial integration of GoT and ToT enhancements
  - Phase 4 (PLAN): GoT node extraction and edge analysis
  - Phase 8 (TRACE): ToT branch generation and scoring
  - Opt-out flags: `--no-got`, `--no-tot`
  - Environment variables: `SKILL_NO_GOT`, `SKILL_NO_TOT`
  - Quality-first design: Both enhancements enabled by default
  - Comprehensive test coverage: 90 tests passing
