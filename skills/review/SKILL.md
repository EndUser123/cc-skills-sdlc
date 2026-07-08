---
name: review
description: "Unified code & PR review — modes: pr (default), diff, file, tests, errors, types, simplify, critical, multi (multi-LLM), full (14-agent inspection)"
argument-hint: "[mode] [scope]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
triggers:
  - /review
aliases:
  - /review
enforcement: advisory
depends_on_skills: []
workflow_steps: []
suggest:
  - /red-team
  - /improve
  - /skill-audit
---

# /review — Unified Code & PR Review

Single entry point for every code-review flavor in the marketplace. Pick a mode or let the default `pr` mode run.

## Escalation — when to leave `/review`

`/review` is a **routine code/diff review** workflow. It produces file:line
findings, not trust verdicts. Escalate to a specialized command when the work
crosses into a different layer:

| If the work involves... | Escalate to | Why |
|---|---|---|
| Hook wiring, gate ordering, dispatch double-fire, plugin loading, marketplace cache hygiene | `/claude-audit` | Runtime/environment/config layer. `/review` can find the bug; `/claude-audit` owns the surface. |
| Skill/command contracts, capability preservation, absorbed/stub claims, alias routing, advertised capabilities | `/skill-audit` | 8-category rubric + capability-preservation check. `/review` is wrong layer for skill design. |
| Trust/adversarial verdict on a proposal (PROCEED/REVISE/BLOCK), security boundary, secret handling, prompt-injection surface | `/red-team` | Adversarial specialist dispatch + critic verdict. `/review` doesn't run specialists. |
| Improving a single artifact's design (prompt, hook config, code slice) | `/improve` | Review-with-recommendation machinery. |

Use the routing table. Do not let `/review` absorb adversarial or audit work
because the file:line findings are similar in shape.

## Modes

## Modes

| Mode | What it does | Engine |
|------|--------------|--------|
| `pr` *(default)* | Multi-agent PR review: comments, tests, errors, types, code, simplify | this skill (see workflow below) |
| `diff` | Review only `git diff main...HEAD` (or staged/latest commit) | this skill, scope-narrowed |
| `file` | Review one file or path prefix passed as scope | this skill, scope-narrowed |
| `tests` | Behavioral test-coverage quality + critical gaps | `pr-test-analyzer` agent |
| `errors` | Silent failures, catch blocks, error logging | `silent-failure-hunter` agent |
| `types` | Type encapsulation, invariant expression, design quality | `type-design-analyzer` agent |
| `simplify` | Clarity/maintainability pass after review passes | `code-simplifier` agent |
| `critical` | High-precision bug + logic-defect review against CLAUDE.md | `code-reviewer` agent |
| `multi` | Parallel multi-LLM adversarial dispatch (DeepSeek/Gemini/Claude/GPT) + synthesis | `skills/sqd/` (`python -m sqd dispatch`) |
| `full` | Unified Code Inspection — auto-depth 3→14 agent registry + 3-tier verdict | `skills/uci/` (auto/`--lite`/`--full`) |

**Mode resolution:** `/review tests errors` runs multiple aspect modes. `/review multi` and `/review full` delegate to their engines. Bare `/review` = `pr` mode over the auto-detected scope.

## Workflow (default `pr` mode)

1. **Determine scope** — user scope > feature branch (`git diff main...HEAD`) > staged > latest commit. Run `git diff --name-only`; check `gh pr view` if a PR exists.
2. **Pick aspects** — from `$ARGUMENTS` or default to all applicable:
   - Always: `code-reviewer` (general quality, CLAUDE.md compliance)
   - Test files changed → `pr-test-analyzer`
   - Comments/docs added → `comment-analyzer`
   - Error handling changed → `silent-failure-hunter`
   - Types added/modified → `type-design-analyzer`
   - After passing → `code-simplifier`
3. **Dispatch** — sequential by default (each report complete before the next); add `parallel` to run all at once.
4. **Aggregate** — Critical (must fix) / Important (should fix) / Suggestions / Strengths, each with `file:line`.
5. **Action plan** — fix critical → important → suggestions → re-run to verify.

## Mode-specific contracts

### `multi` (delegates to `skills/sqd/`)
```bash
cd "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc" && python -m sqd dispatch --target "<path>" --models deepseek gemini claude --parallel
```
Three phase gates (dispatch → collect → synthesize). Exit codes: 0 consensus, 1 divergence, 2 agent failure, 3 target not found. Synthesis + per-agent artifacts land in `skills/sqd/findings/`.

### `full` (delegates to `skills/uci/`)
Auto-selects depth from risk/file-count/line-count signals: `triage` (3 agents) → `standard` (4) → `deep` (8) → `comprehensive` (14). Force with `--lite` or `--full`. Per-agent additive triggers fire on code patterns regardless of mode. Three-tier verdict: **Ready to Merge** / **Needs Attention** / **Needs Work**. Pre-existing-issue detection separates MUST-FIX from background debt. Full registry + sequential-trigger + memory-integration docs live in `skills/uci/references/`.

> **Historical note:** `/uci`'s claim that "`/review` and `/adversarial-review` were consolidated into this skill" is stale as of this consolidation — `/uci` now folds under `/review full`. The uci engine remains the execution backend.

## Output

Markdown by default (verdict → findings with impact/effort → cross-agent validation → action plan). `full` mode also supports `--format json|summary`.

## When to escalate (suggest)

- **Trust boundary / security / gate / hook changes** → `/red-team`
- **Design-level improvement opportunity** → `/improve`
- **Systemic skill-design issues across multiple skills** → `/skill-audit`

## Evidence-First Principles

- **E1**: claims of absence require confirmed Read/Grep/git failure.
- **E4**: read source before reviewing; don't ask the user for what you can find.
- **E5**: no "I assume / probably" without tool verification.

## Cross-Skill Transfer Check (XSTC)

`/review` emits XSTC only for **recurring** code-review/test-quality
patterns (≥2 occurrences across runs), not every routine finding. Recurring
patterns → `classification: applies_to_related_skills` with owner
`/improve` (if a workflow change) or `/skill-audit` (if it's about how
`/review` itself is invoked). One-off findings → no XSTC; just include in
the file:line output. Canonical template at
`debrief/references/cross-skill-transfer-check.md`.

**Advisory status:** XSTC discipline is currently prompt-advisory only.
Runtime enforcement is a future enhancement, not a current guarantee. The
sibling Completion Evidence Contract (CEC) is enforced via `/red-team`'s
Pre-check 0 BLOCK authority; XSTC has no runtime enforcement equivalent.

## Completion Evidence Contract — required for code/diff/test claims

When reviewing code/test/diff completion claims, the Completion Evidence
Contract governs the acceptance bar. The contract lives at
`debrief/references/completion-evidence-contract.md`. Required mappings:

- `file_changed` rows require the Edit/Write receipt + a Read of the
  modified lines confirming the change persisted. Mtime-only verification
  is NOT sufficient.
- `test_passed` rows require the actual pytest output line (`N passed`)
  for the relevant test file. Reporting "tests pass" without the line is
  `NOT_PROVEN`.
- A test that checks text exists is `static_invariant_tested`, NOT
  `behavior_eval_tested`. If the report claims the latter, flag the
  overclaim.
- Runtime behavior changes require a live smoke proof or recorded
  behavior change, not just a code diff.

If a `/review` report's claims can't be backed by Edit receipts + pytest
output + Read receipts, the verdict is REVISE.

## Thought Partner Addendum

Emit a Thought Partner Addendum (TPA) ONLY when the review surfaced a broader
recurring engineering pattern, a test-strategy gap, or a runtime/user-surface
verification gap — not for routine reviews. Each item carries `observation`,
`why_it_matters`, `evidence`, `recommended_action`,
`urgency: now | later | watch`. Omit the section for ordinary file:line
findings; never displace the review verdict or the CEC ledger. Canonical
contract + worked examples at `debrief/references/thought-partner-addendum.md`
(canonical owner: `/improve`). The TPA is prompt-advisory only.

## Report-Contract Vocabularies

`/review` emits claims under the cross-command report contracts. The canonical
field definitions live at
`debrief/references/report-contract-vocabularies.md`:

- **Coverage Authority** — name `sampled | targeted | whole_repo_static |
  runtime_surface | live_behavior` on any audit claim (no bare "full coverage").
- **Activation Truth Model** — name one of `source_changed | cache_rebuilt |
  plugin_loaded | command_resolves | behavior_observed` on any "live / wired"
  claim. Do not claim live behavior from a source/cache evidence alone.
- **Bounded Action Continuation** — when the goal is authorized and the next
  action is bounded + reversible + directly implied, complete it directly
  instead of ending with "say the word."
- **Manifest generator** — before claiming `whole_repo_static` evidence breadth,
  run `cc-skills-architect/skills/ask/lib/abstraction_audit_manifest.py` and
  cite the produced `manifest.json`.

Advisory status: prompt-advisory. Static-invariant-tested at most. No runtime
hook enforces these fields.

## Partner Posture

`/review`'s posture is **Code Review Partner** (see the Partner Posture Map
in `debrief/references/thought-partner-addendum.md`). `/review` reviews
concrete code, diffs, tests, errors, and implementation quality, escalates to
`/red-team`, `/skill-audit`, or `/claude-audit` when the diff affects trust
boundaries, skills, hooks, plugins, runtime behavior, or user-facing
capability, and surfaces broader recurring engineering patterns only when
non-trivial. Posture is prompt-advisory.

## Deprecated aliases

`/review-pr`, `/uci`, `/sqd` still resolve (5-line router stubs in their own SKILL.md) and forward here. They will be removed after one release cycle.
