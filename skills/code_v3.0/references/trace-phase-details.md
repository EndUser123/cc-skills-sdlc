# Phase 8: TRACE - Detailed Instructions

## Why TRACE Matters

The verification gap -- tests can pass while code has bugs like:
- Lock cleanup race conditions (finally block deletes another process's lock)
- File descriptor reuse (fd consumed, then reused in except block)
- Incorrect fallback chains (stale data used instead of fresh source)

## TRACE Protocol

**When**: After BOTH TEST and AUDIT phases complete, before DONE.

**What**: Manual trace-through of each modified file for logic correctness.

**How**: Use the `/trace` skill for systematic code TRACE.

### Step 8.1: Error Handling Verification

Before manual trace-through, verify error handling completeness:

```
Agent(subagent_type="pr-review-toolkit:silent-failure-hunter", description="Error handling and silent failure detection for <target>")
```

**What this does:**
- Detects silent error handling (swallowed exceptions without logging)
- Identifies missing exception cases
- Checks for incomplete error recovery paths
- Reports findings with confidence scores (80+ threshold)

**Integration notes:**
- Run AFTER manual TRACE completes
- Complements TRACE (focuses on error paths, TRACE focuses on logic)
- TRACE phase passes only after both manual TRACE AND error handling verification

### Execution

1. **List modified files** from git diff or plan.md
2. **For each modified file**, run `/trace code:<file>`:
   ```bash
   /trace code:src/handoff.py
   /trace code:src/core/ledger.py
   ```
3. **Review TRACE report** for:
   - Logic errors (P0 severity)
   - Resource leaks (P0 severity)
   - Race conditions (P0 severity)
   - Code quality issues (P1-P3 severity)
   - **Pre-mortem integration**: Ensure each pre-mortem scenario appears as a TRACE scenario row
4. **Run error handling verification** (Step 8.1)
5. **Fix any issues found** and re-run affected tests
6. **Only after BOTH TRACE and error handling verification pass** -> proceed to DONE

**TRACE output includes**:
- 3 scenarios traced (happy path, error path, edge case)
- State tables tracking variables/resources at each step
- Resource management verification (fds, locks, connections)
- Exception handling analysis
- Checklist of 100+ verification points
- Specific recommendations with severity levels

**Effectiveness**:
- Detection rate: 60-80% for logic errors
- Combined with static analysis: 85-95% bug detection

### Step 8.2: Tree-of-Thought (ToT) Enhancement

**Purpose**: Apply Tree-of-Thought reasoning to explore branching execution paths in code.

**When**: During TRACE phase, after manual TRACE completes, before error handling verification.

**Opt-out**: Use `--no-tot` flag to disable ToT enhancement.

**Execution**:

1. **Generate branches** for each conditional in traced code:
   ```python
   from utils.tot_tracer import BranchGenerator
   generator = BranchGenerator(code_content)
   branches = generator.generate_branches()
   ```

   Branch types detected:
   - **if statements**: true/false branches
   - **elif statements**: condition true/false branches
   - **for loops**: loop iteration/exit branches
   - **while loops**: loop iteration/exit branches
   - **try/except blocks**: success/exception branches

2. **Score branches** by likelihood:
   - **sure**: High-confidence paths (e.g., "if user.authenticated")
   - **maybe**: Medium-confidence paths (e.g., "elif request.method == 'POST'")
   - **unlikely**: Low-confidence paths (e.g., "except ValueError")

3. **Prune branches** to high-value paths:
   ```python
   pruned_branches = generator.prune_branches(branches)
   ```
   - Removes 'unlikely' scored branches
   - Focuses TRACE effort on high-impact paths

4. **Document findings** in TRACE report:
   - Add "ToT Branch Analysis" section
   - List generated branches with descriptions and scores
   - Note any unlikely branches that were pruned
   - Identify edge cases that ToT revealed

**What this catches**:
- Unexplored error paths
- Edge cases in conditional logic
- Loop exit conditions (may never exit under load)
- Nested branch interactions

**Duration**: 3-8 minutes for typical files (generates 5-20 branches, scores each, prunes 2-5 unlikely)

## TRACE Integration

**TRACE is mandatory for ALL code changes** -- no exceptions.

**TRACE depth scales with complexity**:
- **1-2 files changed**: Light trace (5-10 minutes) -- focus on error paths
- **3-5 files changed**: Standard trace (10-20 minutes) -- full checklist per file
- **6+ files changed**: Deep trace (20-60 minutes) -- systematic TRACE with state tables

**TRACE exemption** (only one):
- Pure documentation changes (.md, .rst) with ZERO code execution

**When TRACE finds issues**:
1. Fix the issue
2. Re-run affected tests
3. Re-TRACE the fixed code
4. Only proceed to SHIP after TRACE passes

**See `/trace` skill for**:
- Full TRACE methodology: `P:/.claude/skills/trace/templates/TRACE_METHODOLOGY.md`
- Code TRACE templates: `P:/.claude/skills/trace/templates/code/TRACE_TEMPLATES.md`
- TRACE checklist: `P:/.claude/skills/trace/templates/code/TRACE_CHECKLIST.md`
- Real-world case studies: `P:/.claude/skills/trace/templates/code/TRACE_CASE_STUDIES.md`
