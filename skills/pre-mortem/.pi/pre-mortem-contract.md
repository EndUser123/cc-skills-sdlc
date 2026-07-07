# PI Harness Pre-Mortem Contract

This file defines a harness-readable contract for using the package-owned pre-mortem method without depending on Claude Code slash commands.

## Inputs

- `target`: path or textual description of the work to review.
- `repo_root`: repository root for resolving related files.
- `mode`: `quick`, `standard`, or `deep`.
- `profile`: optional repo-local profile path.
- `evidence_dir`: optional output directory, default `.logs/pre-mortem/<run-id>/`.

## Required Reads

The harness or agent must load:

- `../references/method.md`
- `../references/failure-mode-checklist.md`
- `../references/output-contract.md`
- `../references/pre-mortem-evidence-tiers.md`
- `../references/modes.md`
- `../references/investigation-types.md`
- `../references/static-test-contract.md`
- `../references/non-static-validation.md`
- `../references/review-lenses.md`
- `../references/project-profiles.md`
- `../references/decision-model.md`
- `../references/live-probe-planner.md`
- `../references/finding-synthesis.md`
- `../references/destructive-live-preflight.md`
- `../references/historical-regression-awareness.md`
- `../references/predictable-issues.md`
- `profile`, when provided and present

## Output

The harness should produce Markdown or JSON containing:

- `intent_summary`
- `health_score`
- `findings`, each with `severity`, `domain`, `description`, `evidence`, and `recommendation`
- `investigation_coverage`, separating static artifacts reviewed from non-static probes run or recommended
- `static_test_coverage`, listing static checks run, missing, or insufficient
- `review_lens_coverage`, listing lenses applied, skipped, and recommended next
- `project_profile_applied`, naming the profile path used or `none found`
- `missing_profile_sections`, listing absent profile sections and their stop/go impact
- `stop_go_decision`
- `live_probe_plan`
- `historical_regression_check`
- `recommended_next_steps`
- `verification_required`
- `stop_go_recommendation`

## Exit Behavior

- Advisory mode: always exit 0 and write findings.
- Blocking mode: exit non-zero when CRITICAL findings exist, when required evidence cannot be gathered, or when data-safety boundaries are missing for destructive/live work.

## Safety Rules

- Do not perform destructive actions.
- Do not run non-static probes unless the harness invocation explicitly authorizes them.
- Do not treat `0 - Do ALL Recommended Next Steps` as execution permission.
- Do not use Claude Code `.claude/.evidence` paths unless explicitly requested by the caller.
- Preserve primary failure context when reporting cleanup or postflight failures.
