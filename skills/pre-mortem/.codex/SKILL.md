---
name: pre-mortem
description: Codex adapter for package-owned pre-mortem review. Use when checking predictable issues, live-run readiness, cleanup safety, implementation plans, or failure modes.
---
# Pre-Mortem - Codex Adapter

This is the Codex adapter for the package-owned pre-mortem skill at `P:/packages/cc-skills-sdlc/skills/pre-mortem`.

## Required References

Read these package-owned files before producing findings. Use the absolute paths below because this adapter may be installed into Codex as a junction where `../references` does not resolve to the package source.

- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/method.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/failure-mode-checklist.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/output-contract.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/evidence-contract.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/modes.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/investigation-types.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/static-test-contract.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/non-static-validation.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/review-lenses.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/project-profiles.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/decision-model.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/live-probe-planner.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/finding-synthesis.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/destructive-live-preflight.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/historical-regression-awareness.md`
- `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/predictable-issues.md`

If the active repository has a repo-local pre-mortem profile, read it after the shared references. Common locations:

- `docs/operations/pre-mortem-profile.md`
- `docs/pre-mortem-profile.md`
- `.codex/pre-mortem-profile.md`

## Codex Execution Rules

- Default to `quick` or `standard` single-agent review.
- Treat static investigation as the default. Do not run non-static probes unless they are already authorized by the user request and current Codex rules.
- Do not spawn subagents unless the user explicitly asks for subagents, delegation, or parallel agent work.
- Do not use Claude slash-command assumptions such as `/pre-mortem`, `Task`, `.claude/.evidence`, or `0` as implicit execution permission.
- Prefer repo-local evidence paths such as `.logs/pre-mortem/<timestamp>/` when writing artifacts.
- Follow the current Codex/developer instructions for file edits, verification, destructive actions, and final reporting.

## Output Shape

For routine Codex use, report:

1. Static predictable issues
2. Live/runtime predictable issues
3. Data safety and cleanup issues
4. Observability/tracing gaps
5. Non-static probes run or recommended
6. Logic review
7. Review lens coverage
8. Live Probe Plan
9. Historical Regression Check
10. Stop/Go Decision
11. Recommended Next Steps
12. Verification required before trial/live use

For larger reviews, use the full output contract from `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/output-contract.md`.

## Data-Safety Gate

For deletion, cleanup, migration, credential, auth, NotebookLM, browser-profile, or external-service work, always include:

- What is safe to touch.
- What must not be touched.
- How list/parse/auth/validation failure behaves.
- Whether stale state can target the wrong resource.
- Whether cleanup failure preserves the primary failure context.

## Static And Non-Static Checks

Use `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/static-test-contract.md` to decide whether static tests cover the risk. Use `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/non-static-validation.md` when behavior cannot be proven statically.

When live/plugin validation would be useful but is not authorized, report it as a recommended probe with the exact command and expected signal.

## Decision Requirement

End with a Stop/Go Decision from `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/decision-model.md`. For HIGH/CRITICAL findings, include evidence strength, falsifier, and wrong-order risk from `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/finding-synthesis.md`.

## Recommended Next Steps Requirement

If the review reaches a concrete action stage, include `Recommended Next Steps` in the same RNS/GTO-compatible format used by `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/output-contract.md`. Do not omit the section just because the review is being run from Codex.

## Quality Bar

Outcomes must be at least as strong as the Claude Code workflow for the same mode:

- no producer-only success proofs;
- no uncited assumptions presented as fact;
- no recommendations that expand scope silently;
- no destructive or live operation without explicit safety boundaries;
- no "looks fine" conclusion without stating residual risks and verification gaps.
- no omitted `Recommended Next Steps` when the review produces concrete follow-up actions.
