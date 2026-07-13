---
name: source-authority-discovery
description: Build an evidence-backed inventory before planning, reviewing, or implementing non-trivial changes to hooks, skills, plugins, entrypoints, defaults, state, worktrees, or orchestration.
---

# Source Authority Discovery

Use this skill before making or approving a non-trivial change when the task
could depend on whether an implementation, registration, caller, default,
cache, worktree, test, or competing plan already exists.

## Required workflow

1. Read applicable `AGENTS.md`, `CLAUDE.md`, package handoffs, and current
   operating documents.
2. Run the shared Windows audit utility with explicit relevant scopes and
   target tokens:

   ```powershell
   python P:\.agents\skills\source-authority-discovery\scripts\discovery_audit.py `
     --scope P:\.claude `
     --scope P:\packages\.claude-marketplace\plugins `
     --scope P:\.agents `
     --scope P:\docs `
     --target <capability-or-entrypoint> `
     --target <registration-or-dispatcher> `
     --target <default-or-state-key> `
     --output P:\tmp\source-discovery.json `
     --fail-on-conflict
   ```

3. Read every matching implementation, caller/registration, test, active plan,
   cache/generated copy, and worktree record reported by the audit.
4. Classify each artifact as canonical source, runtime state, generated
   output, cache, worktree, fixture, documentation, or historical artifact.
5. For a new file, prove that no existing file owns the same role. For a
   default or lifecycle change, inspect every reader, writer, and consumer.
6. Report the packet path, revision, scopes, conflicts, and intentionally
   uninspected areas.

## Hard stops

- Do not infer absence, uniqueness, activation, or completeness from a plan,
  summary, cache, filename search, or another model's review.
- Do not create a replacement or wrapper until similarly purposed entrypoints
  and their contracts are classified.
- Do not change a default until all occurrences and lifecycle consumers are
  classified.
- If the audit returns `needs_review` or `blocked`, do not implement. Gather
  evidence or obtain an explicit user decision first.

## Output contract

Use a compact table:

`artifact | classification | owner/caller | state/default consumers | tests | cache/generated copies | conflict | evidence`

Separate verified facts, measured results, inferences, hypotheses, and
unknowns. This skill is a discovery gate; it does not authorize production
configuration changes or cleanup of concurrent work.
