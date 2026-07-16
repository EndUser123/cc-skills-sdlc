---
name: code-review
description: "Multi-agent code review for local diffs OR GitHub PRs. Uses 5 parallel reviewers + confidence scoring + 80-filter cutoff."
enforcement: advisory
workflow_steps: []
---

# /cc-skills-sdlc:code-review [PR-number]

Multi-agent code review that works on **local changes** (no PR needed).

## Mode selection

- **With a PR number** (`/cc-skills-sdlc:code-review 123`): delegates to the official `/code-review:code-review 123` (which requires a GitHub PR)
- **Without a PR number** (`/cc-skills-sdlc:code-review`): runs the full multi-agent review against local `git diff HEAD`

## Procedure (no PR given)

### Step 1: Discover the diff and context

First, determine what changed. For a regular repo:
```bash
git diff HEAD --name-only
```

For a git submodule (if inside one):
```bash
# Determine if inside a submodule
git rev-parse --show-toplevel
git diff HEAD --name-only  # or HEAD~N if needed
```

Read `P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/CLAUDE.md` and any CLAUDE.md in the repo root for project-specific review guidelines.

### Step 2: Launch 5 parallel reviewers

Launch 5 parallel Sonnet subagents to independently code review the change. Each agent reads the full diff (`git diff HEAD`) and returns a structured list of issues. Provide each agent with the CLAUDE.md guidance content.

- **Agent #1 (CLAUDE.md compliance):** Audit changes against project CLAUDE.md rules. For each violation, quote the exact rule and cite the offending code location.
- **Agent #2 (correctness bugs):** Read the file changes and scan for obvious bugs. Focus on large bugs, avoid nitpicks. Ignore likely false positives.
- **Agent #3 (git blame/history):** Read git log for the modified files to identify relevant context. Run `git log --oneline -5 -- <file>` for each changed file. Flag if the new code reintroduces a previously fixed pattern.
- **Agent #4 (existing code comments):** Read code comments in the modified files. Flag if the change violates documented contracts, invariants, or assumptions in the comments.
- **Agent #5 (cross-boundary):** For plugin code, check if any import targets `P:/.claude/hooks/` or reverse-imports from local hooks into plugin `__lib/` without a shim.

### Step 3: Score and filter

For each issue found in Step 2, run a Haiku subagent that takes the issue description and CLAUDE.md context, and returns a **confidence score 0-100**:

- 0: False positive — doesn't stand up to light scrutiny, or pre-existing
- 25: Might be real but unverified
- 50: Real but minor — not very important relative to the PR
- 75: Highly confident — verified, will be hit in practice
- 100: Absolutely certain — confirmed real, frequent, and severe

Filter out all issues with score < 80.

### Step 4: Report

If no issues remain after filtering, report:

> ### Code review
>
> No issues found. Checked for bugs and CLAUDE.md compliance.

If issues remain, report each one in this format:

> ### Code review
>
> Found N issues:
>
> 1. <brief description> (<source: CLAUDE.md rule / bug / history / comment>)
>
> <code citation with file:line>
>
> ...
>
> Generated with cc-skills-sdlc local code reviewer

### Step 5: Cleanup

Clear any subagent artifacts left in `.claude/.artifacts/` or `TEMP`.

## Relationship to the official plugin

This skill replicates the official `code-review@claude-plugins-official` workflow for environments where no PR exists (local development, submodule work). The official plugin remains the canonical reviewer for PR-based workflows.
