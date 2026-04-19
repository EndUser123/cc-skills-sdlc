---
name: local-pr-ready
version: 0.4.0
description: Local-only Ralph loop with worktree enforcement, auto-detected review depth, simplify override signal, and PR artifact generation.
category: execution
enforcement: blocking
triggers:
  - '/go'
aliases:
  - '/go-local'
  - '/local-pr-ready'
workflow_steps:
  - worktree_enforcement
  - task_contract
  - verify_end_to_end
  - simplify_code
  - seven_pass_review
  - create_pr_artifacts
  - loop_check
suggest: []
---
# /go — Local PR-Ready Ralph Loop

**MANDATORY SEQUENCE:** Worktree Check → Contract → Verify → Simplify → 7-Pass Review → PR Artifacts → Loop Check

## Ralph Loop

This skill is a Ralph loop: autonomous iteration until `<promise>PR_READY</promise>`.

**Completion token:** `<promise>PR_READY</promise>`
**Blocking token:** `<promise>BLOCKED</promise>`

**Ralph-mode activation:**
- Auto-detected when working from `plan.md` or batch tasks
- Manual override: `/go --ralph` to enable, `/go --no-ralph` to disable

**Loop behavior:** After PR artifacts created, re-reads `plan.md` and resumes next task if items remain.

---

## STEP 0: WORKTREE ENFORCEMENT (BLOCKING)

**STOP IMMEDIATELY if not in a worktree:**

```bash
git worktree list --porcelain | head -1
pwd
git branch --show-current
```

**Required state:**
- Must be in a git worktree (not main checkout)
- Branch name must contain task identifier
- cwd must be inside worktree directory

**If any condition fails:**
```
ERROR: /go only works inside task worktrees.

Create one:
  git worktree add ../worktrees/{ticket} -b {ticket}

Then cd into it and retry /go.
```

**Do not proceed to STEP 1 without worktree confirmation.**

---

## STEP 1: TASK CONTRACT

**Create `.claude-state/task-definition.md` before beginning:**
```bash
mkdir -p .claude-state/review-passes
```

```markdown
# Task Contract

## Objective
{One sentence: what this PR accomplishes}

## Scope
**In scope:** {bullet list}
**Out of scope:** {bullet list}

## Forbidden Files
{Files/code that must NOT be modified}

## Acceptance Criteria
- [ ] {Criterion 1}
- [ ] {Criterion 2}

## Verification Commands
These are run literally after every edit.

```bash
{Command to verify criterion 1}
{Command to verify criterion 2}
```
```bash
# Optional: end-to-end test
{Command for e2e verification}
```

## State
- Created: {timestamp}
- Status: IN_PROGRESS
- Iteration: 0
- Review Depth: {auto-detected in STEP 1B}
```

---

## STEP 1B: AUTO-DETECT REVIEW DEPTH

**Run immediately after task-definition.md is created.**

```bash
git diff --stat
git diff --shortstat
```

**Compute review depth from metrics:**

| Files changed | Lines changed | Depth | Passes |
|---------------|---------------|-------|--------|
| < 3 | < 50 | **quick** | 1, 2, 7 |
| < 10 | < 200 | **standard** | 1, 2, 3, 5, 7 |
| ≥ 10 | ≥ 200 | **full** | 1, 2, 3, 4, 5, 6, 7 |

**Downgrade rules (override depth upward but not downward):**
- No existing tests found → standard skips pass 3 (tests), quick skips pass 3
- Changes affect only docs/config → quick only
- Hook/router changes → always standard minimum
- Multi-file refactors → always full

**Write detected depth to task-definition.md:**
```bash
# Update State section
sed -i 's/- Review Depth: {auto-detected}/- Review Depth: {quick|standard|full}/' .claude-state/task-definition.md
```

**If files were auto-detected:**
- Pass 4 (simplicity) always runs regardless of depth
- Pass 6 (maintainability) only in full depth

**State files structure (MANDATORY):**
```
.claude-state/
├── task-definition.md      (canonical contract)
├── progress.txt            (iteration log)
├── decisions.md            (design rationale)
├── risks.md                (open issues, blocking items)
└── review-passes/          (7 files, one per pass)
    ├── correctness.md
    ├── scope.md
    ├── tests.md
    ├── simplicity.md
    ├── regressions.md
    ├── maintainability.md
    └── pr-ready.md
```

---

## STEP 2: VERIFICATION COMMANDS (MANDATORY)

**Extract verification commands from `.claude-state/task-definition.md` — run them literally.**

**No claims of completion without running the actual commands from task-definition.md.**

**Every edit triggers:**
1. Run each verification command literally
2. Copy-paste output to `.claude-state/verification-results.txt`
3. Compare against previous iteration's results

**Verification types:**

| Work Type | Verification Method |
|-----------|---------------------|
| Backend | Start service + run actual test suite or curl/http request |
| Frontend | Browser test or screenshot |
| CLI tool | Execute command with real arguments |
| Desktop app | Computer use to interact with GUI |
| Hook/router | Smoke test proving activation path works |
| State/resume | Prove restoration from checkpoint actually succeeds |

**Evidence format (REQUIRED):**
```
## Verification Results

**Type:** {backend|frontend|cli|desktop|hook|state}
**Command:** {actual command run}
**Baseline:** {X passed, Y failed}
**After:** {X+N passed, Y-Z failed}

**Integration:**
- Function at: path/to/file.py:line
- Called from: module1.py, module2.py
- NOT called from: (explain if expected consumer missing)

**Output saved to:** .claude-state/verification-results.txt

**Conclusion:** PASS / FAIL
```

**If verification FAILS:**
1. Update `.claude-state/risks.md` with failure analysis
2. Emit `<promise>BLOCKED</promise>`
3. Do not proceed until fixed.

---

## STEP 3: SIMPLIFY (MANDATORY QUALITY GATE FOR COMMITTED CHANGES)

**Intent:** `/simplify` applies to files being committed, not to generated PR artifacts.

### Diff Classification

Before running simplify, classify the current git diff:

- **Code / executable / skill changes** include:
  - `*.py`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.sh`, `*.ps1`
  - `SKILL.md`
  - files under `src/`, `app/`, `lib/`, `scripts/`, `.claude/skills/`, `.claude/commands/`
- **Docs-only changes** include:
  - `*.md`, `*.txt`
  - documentation folders
  - files that do not affect runtime behavior

### Required Behavior

#### Case A: Code / skill / script changes present
Run `/simplify` on the changed files before review passes.

```bash
/simplify
```

**Required result:**
- If `/simplify` returns **PASS** → continue to STEP 4.
- If `/simplify` returns **LOW/MEDIUM findings** → fix if reasonable, then continue with findings recorded.
- If `/simplify` returns **HIGH/CRITICAL findings**:
  1. Record them in `.claude-state/risks.md`
  2. Attempt one corrective cycle
  3. Re-run `/simplify`
  4. If still HIGH/CRITICAL, stop and emit `<promise>BLOCKED</promise>`
  5. Proceed only with explicit user waiver recorded in `.claude-state/risks.md`

#### Case B: Docs-only diff
Do **not** run `/simplify` on generated PR artifacts or prose-only outputs.

Record in `.claude-state/decisions.md` and `.claude-state/progress.txt`:
```
SIMPLIFY STATUS: SKIPPED (DOCS-ONLY DIFF)
```

### Mandatory Logging

Write simplify status to `.claude-state/simplify-status.md`:

```md
# Simplify Status

Status: {PASS|SKIPPED|BLOCKED|WAIVED}
Changed files reviewed:
- path/to/file1
- path/to/file2

Findings:
- none | LOW | MEDIUM | HIGH | CRITICAL
```

**Rule:** `/go` must never emit `<promise>PR_READY</promise>` for code changes unless simplify is `PASS` or explicitly `WAIVED`.

---

## STEP 4: REVIEW PASSES

**Execute only the passes required by the auto-detected review depth.**

Read `.claude-state/task-definition.md` to get the `Review Depth` value.

**Quick (3 passes):** correctness, scope, pr-ready
**Standard (5 passes):** correctness, scope, tests, regressions, pr-ready
**Full (7 passes):** correctness, scope, tests, simplicity, regressions, maintainability, pr-ready

### Pass 1: Correctness
```markdown
# Review Pass: Correctness

## Criteria
- [ ] Code matches acceptance criteria
- [ ] No logic errors or off-by-one bugs
- [ ] Edge cases handled

## Findings
{evidence}

## Status: PASS / FAIL
```

### Pass 2: Scope Compliance
```markdown
# Review Pass: Scope

## Criteria
- [ ] Only modified files listed in task contract
- [ ] No forbidden files touched
- [ ] Changes align with stated objective

## git diff analysis
```bash
git diff --stat
```

## Status: PASS / FAIL
```

### Pass 3: Test Coverage
```markdown
# Review Pass: Tests

## Criteria
- [ ] New code has tests
- [ ] Existing tests still pass
- [ ] Integration tests prove end-to-end behavior

## Test output
```bash
{test command}
```

## Status: PASS / FAIL
```

### Pass 4: Simplicity
```markdown
# Review Pass: Simplicity

## Criteria
- [ ] No unnecessary abstraction layers
- [ ] Code is readable by humans
- [ ] No premature optimization

## Findings
{evidence}

## Status: PASS / FAIL
```

### Pass 5: Regression Check
```markdown
# Review Pass: Regressions

## Criteria
- [ ] Core functionality unchanged
- [ ] No breaking changes to existing APIs
- [ ] Backward compatibility preserved

## git log analysis
```bash
git log --oneline -5
```

## Status: PASS / FAIL
```

### Pass 6: Maintainability
```markdown
# Review Pass: Maintainability

## Criteria
- [ ] No technical debt accumulation
- [ ] Documentation updated if needed
- [ ] No TODO/FIXME left behind

## Findings
{evidence}

## Status: PASS / FAIL
```

### Pass 7: PR-Ready Audit
```markdown
# Review Pass: PR-Ready

## Criteria
- [ ] Commit message follows convention
- [ ] PR title is descriptive
- [ ] No secrets or credentials in code
- [ ] No debug code left in

## Secret scan
```bash
git diff --staged | grep -i "password\|secret\|key\|token" || echo "CLEAN"
```

## Status: PASS / FAIL
```

**All 7 passes must be PASS to proceed.**

---

## STEP 5: LOCAL PR-READY (NO REMOTE PUSH)

**Preconditions:**
- Verification: PASS
- Simplify: `PASS`, `SKIPPED (DOCS-ONLY DIFF)`, or `WAIVED` with rationale in `.claude-state/risks.md`
- All required review passes: PASS

**All required review passes must pass before this step.**

### Important Distinction

PR artifacts are **outputs derived from already-reviewed changes**, not inputs to `/simplify`.

Do **not** run `/simplify` on: `commit-message.txt`, `pr-title.txt`, `pr-body.md`, `pr-ready.md`

### Create artifacts:

**1. `commit-message.txt`:**
```
{type}: {short description}

VERIFIED:
- {verification evidence 1}
- {verification evidence 2}

REVIEW DEPTH: {quick|standard|full}
REVIEW PASSES: {list of passes that ran}
SIMPLIFY: {PASS|SKIPPED|WAIVED}

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**2. `pr-title.txt`:**
```
{type}: {descriptive title}
```

**3. `pr-body.md`:**
```markdown
## Summary
{bullet points of changes}

## Verification
{evidence from step 2}

## Simplify
{results from step 3}

## Review
Depth: {quick|standard|full}
Required passes completed and saved to `.claude-state/review-passes/`

🤖 Generated with [Claude Code](https://claude.ai/claude-code)
```

**4. `pr-ready.md`:**
```markdown
# PR Ready

## Task
{objective from task-definition.md}

## Review Depth
{quick|standard|full}

## Status
- Completed: {timestamp}
- All verification commands: PASS
- Required review passes: PASS
- Simplify: {PASS / SKIPPED / WAIVED}

## Next Steps
1. Review `commit-message.txt` and `pr-body.md`
2. Run:
   ```bash
   git add -A
   git commit -F commit-message.txt
   git log -1 --oneline
   ```
3. Push manually when ready:
   ```bash
   git push -u origin HEAD
   gh pr create --title "$(cat pr-title.txt)" --body "$(cat pr-body.md)"
   ```

## Artifacts
- Commit message: `commit-message.txt`
- PR title: `pr-title.txt`
- PR body: `pr-body.md`
```

### Emit completion token

**Only after all artifacts are written:**
```
<promise>PR_READY</promise>
```

**Do NOT:**
- `git push`
- `gh pr create`
- Merge automatically

---

## STEP 6: LOOP CHECK

**After PR artifacts created, if Ralph-mode is active:**

1. Read `plan.md` from project root
2. Check for remaining incomplete tasks
3. If tasks remain:
   ```
   <promise>MORE_TASKS_IN_PLAN</promise>

   Next task: {task name}
   Run /go to continue?
   ```
4. If no tasks remain:
   ```
   <promise>ALL_TASKS_COMPLETE</promise>

   All tasks from plan.md have been completed.
   PR artifacts created and ready for review.
   ```

---

## RALPH COMPLETION CRITERIA

Emit `<promise>PR_READY</promise>` ONLY when ALL pass:

```
✓ task-definition.md acceptance criteria all satisfied
✓ All verification commands pass (output saved to .claude-state/verification-results.txt)
✓ Simplify passes (or explicitly skipped by user)
✓ Required review passes for the auto-detected depth all PASS
✓ .claude-state/risks.md has no HIGH/CRITICAL items
✓ git diff shows only allowed files changed
✓ commit-message.txt, pr-title.txt, pr-body.md, pr-ready.md all created
```

**If blocked:** Update risks.md, emit `<promise>BLOCKED</promise>`.

---

## Ralph State Files

| File | Purpose |
|------|---------|
| `.claude-state/task-definition.md` | Canonical task contract |
| `.claude-state/progress.txt` | Iteration log |
| `.claude-state/decisions.md` | Design rationale |
| `.claude-state/risks.md` | Open issues, blocking items |
| `.claude-state/verification-results.txt` | Command outputs |
| `.claude-state/review-passes/*.md` | Individual review pass results |

---

## Prohibited Actions

- Claiming verified without running actual commands
- Skipping simplify step (must at least attempt)
- Creating remote PR or pushing
- Using mocks as proof of integration
- Proceeding past verification failure
- Editing on main branch
- Skipping any required review pass for the detected depth
- Emitting PR_READY without all artifacts

---

## Dependencies

- `git worktree` for branch isolation
- Appropriate verification tools for work type
- `/simplify` plugin recommended; if unavailable:
  - Docs-only diffs may skip simplify (log `SKIPPED (DOCS-ONLY DIFF)` in decisions.md)
  - Code diffs require either manual equivalent simplify review, or explicit waiver in `.claude-state/risks.md`
- `gh` CLI optional — only for later manual PR creation, not used by `/go`
