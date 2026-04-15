# Plan: Parallel Worktree Implementation with Multiple LLMs for /code

**Created**: 2026-04-15
**Status**: DRAFT — awaiting review
**Scope**: Optional mode where /code spawns a second worktree with a different LLM implementing the same feature, then compares outputs

---

## Executive Summary

**What**: Add an optional `--parallel-llm` flag to `/code` that: (1) creates a second git worktree, (2) sends the same plan/requirements to a second LLM (DeepSeek V3.2 or GPT-5.4), (3) after both implementations complete, runs a diff-and-compare step to pick the better approach or merge insights.

**Why**: For non-trivial features, two independent implementations expose different approaches to the same problem. The comparison step catches architectural differences that a single-model review pass misses — e.g., one implementation might handle error paths differently, or choose a more idiomatic API. This is most valuable when the problem has multiple valid design choices.

**Risk**: High complexity. Two worktrees × two LLM sessions × plan synchronization is a multi-terminal concurrency problem. The plan must respect instance isolation (CLAUDE.md: worktree isolation via `cwd`-based state keys). This is an opt-in feature, not the default path.

**Failure mode that would invalidate this plan**: If the second LLM produces a subtly broken implementation that looks correct in isolation, and the merge step picks the wrong solution, the result is worse than single-LLM. The compare step must include test execution in both worktrees, not just diff inspection.

---

## Background

`/code` already supports git worktrees:
- `SKILL.md:125`: "Git worktree is available via `/git worktree` but not prompted during build"
- CLAUDE.md: worktree isolation keyed on `cwd`, worktrees identified by `worktrees/` in path

The `/ai-oc-nvidia-ds-v32` skill uses OpenCode CLI, which can operate on a specified directory. GPT-5.4 via `/codex` uses Codex CLI, which also supports directory scoping.

This plan is scoped to the **PLAN → TDD → TEST** phases only. PRE-FLIGHT and REQUIREMENTS are shared (run once). AUDIT and TRACE are run on whichever implementation is selected after compare.

---

## Architecture

### Workflow

```
Phase 1-4 (shared):
  REQUIREMENTS → PRE-FLIGHT → EXPLORE → PLAN (produces plan.md)

Phase 5-7 (parallel, two worktrees):
  Worktree A (main):     Claude TDD → TEST                → results_a/
  Worktree B (parallel): DeepSeek V3.2 TDD → TEST         → results_b/

Compare step:
  - Diff implementations (structural, not line-by-line)
  - Run tests in both worktrees
  - Score: test pass rate, code quality, line count, approach clarity
  - Select winner or flag manual merge needed

Phase 8-11 (selected implementation):
  AUDIT → TRACE → PRODUCER/CONSUMER TRACE → DONE
```

### Worktree Naming

```
P:/worktrees/<feature-slug>-primary/    # Claude implementation
P:/worktrees/<feature-slug>-deepseek/   # DeepSeek implementation
```

State files keyed on `cwd` to prevent cross-worktree state contamination (per CLAUDE.md isolation pattern).

### Kill Switch

Set `SDLC_MULTI_LLM=0` in the environment to skip all external LLM slots. When set, worktree B is not created and the parallel workflow is bypassed entirely. Checked at invocation time, before any worktree or CLI call is made.

### LLM Invocation for Worktree B

```bash
# DeepSeek implements the plan in worktree B (no cd — use absolute path via --cwd)
# Kill switch: skip if SDLC_MULTI_LLM=0
opencode run \
  --cwd P:/worktrees/<feature-slug>-deepseek \
  --model deepseek-v3.2 \
  --include-dir . \
  --prompt "Implement the feature described in plan.md.
  Follow TDD: write failing tests first, then implement.
  Run: pytest after implementation.
  Target dir: P:/worktrees/<feature-slug>-deepseek"
```

For GPT-5.4 variant (worktree C, if `--codex` flag added):
```bash
# Kill switch: skip if SDLC_MULTI_LLM=0
codex -a full-auto \
  -m gpt-5.4 \
  --cwd P:/worktrees/<feature-slug>-codex \
  "Implement the feature in plan.md using TDD. Run pytest when done."
```

### Compare Step Output

Written to `P:/worktrees/<feature-slug>-compare/compare.md`:

```markdown
## Implementation Comparison: <feature>

| Dimension         | Worktree A (Claude) | Worktree B (DeepSeek) |
|-------------------|--------------------|-----------------------|
| Tests pass        | Y/N (N passing)    | Y/N (N passing)       |
| Test coverage     | N%                 | N%                    |
| Lines changed     | N                  | N                     |
| Error handling    | [approach]         | [approach]            |
| Notable diff      | [key difference]   | [key difference]      |

**Recommendation**: A / B / Manual merge required
**Reason**: [one sentence]
```

### Compare Step Consumer

**Consumer**: Claude in-context synthesis (not a subagent).

After `compare.md` is written, Claude reads it in-context and makes the final recommendation call. The file is input to Claude's synthesis, not the output of a separate subagent. This avoids the orphaned-consumer problem where compare.md exists but no one acts on it.

The comparison table provides structured data; Claude provides judgment. If the recommendation field is empty or the table is incomplete, Claude flags it rather than picking by default.

---

## Tasks

### TASK-001: Verify worktree creation is safe in this codebase
- Run `git worktree list` to see existing worktrees
- Confirm `P:/worktrees/` exists or can be created
- Confirm no hooks block operations in worktrees (check `PreToolUse` hooks for path guards)
- **Output**: Verified worktree creation command and any hook exclusions needed

### TASK-002: Verify DeepSeek and/or Codex CLI support directory-scoped execution
- Invoke `/ai-oc-nvidia-ds-v32` with `--include-dir` on a test directory
- Invoke `/codex` with a simple implementation task in a temp directory
- **Output**: Verified invocation patterns for both CLIs or `[UNSUPPORTED]` flags

### TASK-002b: Confirm plan.md is accessible from worktree B context
- After worktree B is created, verify the plan.md absolute path is reachable from that worktree's working directory
- Inject the plan.md absolute path into the DeepSeek/Codex invocation prompt (not a relative path)
- If plan.md lives in the main repo, reference it as an absolute path in the LLM prompt so worktree B can read it
- **Output**: plan.md path confirmed injectable; DeepSeek reports "plan.md not found" warning resolved

### TASK-003: Define compare step scoring rubric
- Write `references/worktree-compare-rubric.md` with scoring criteria
- Criteria: test pass rate (weight 0.5), coverage (0.2), implementation clarity (0.2), line count (0.1)
- Define "Manual merge required" threshold: test pass rate differs by >10% or both have unique valid patterns
- **Output**: `P:/packages/sdlc/skills/code/references/worktree-compare-rubric.md`

### TASK-004: Add --parallel-llm flag to SKILL.md
- Add `--parallel-llm [deepseek|codex]` to the argument-hint in SKILL.md frontmatter
- Add flag documentation to the Key Flags table (`SKILL.md:97`)
- **Output**: Updated SKILL.md frontmatter and flags table

### TASK-005: Add parallel worktree workflow to SKILL.md
- Add optional section "## Parallel Worktree Mode (--parallel-llm)" after Phase 4 (PLAN)
- Document: worktree creation, LLM invocation, compare step, winner selection, teardown
- **Output**: New section in SKILL.md

### TASK-006: Define worktree teardown
- After winner selected, document how to: merge winner to main, delete losing worktree, git clean
- Write teardown to `references/worktree-compare-rubric.md` (teardown section)
- **Output**: Teardown procedure documented

### TASK-007: Integration test (small feature)
- Pick a simple 1-file feature from the backlog
- Run `/code <feature> --parallel-llm deepseek`
- Confirm: both worktrees created, both tests run, compare.md produced, winner applied
- **Pass criteria**: compare.md exists with non-empty recommendation, winner's tests pass in main

---

## Verification

| Check | How | Pass |
|-------|-----|------|
| State isolation | check state file paths in both worktrees | different instance_ids |
| No cross-worktree contamination | both worktrees show clean git status independently | no shared file writes |
| Fallback if DeepSeek hangs | kill DeepSeek process, check Claude worktree | Claude proceeds to AUDIT |
| Compare step determinism | run compare twice | same recommendation |
| Teardown | delete losing worktree | `git worktree list` shows only main |

---

## Open Questions for Review

1. Should this be a dedicated `/code-parallel` command instead of a flag on `/code`, to avoid complicating the default path?
2. Is Copilot (when skill is available) the better second LLM here given its native code context awareness?
3. If both implementations fail tests, should we compare partial implementations or fail the whole parallel run?
4. The compare step needs a consumer — should it be Claude (in-context synthesis) or another subagent?
