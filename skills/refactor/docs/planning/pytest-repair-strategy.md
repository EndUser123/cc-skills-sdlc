# Pytest Repair Strategy (C2)

**Status:** Design (C-series: C1 classify → C2 design → C3 first repair pass)
**Date:** 2026-06-05
**Author:** Claude (per stop-hook attribution)

## Context

This document captures the design of the pytest repair strategy, between C1 (failure classification) and C3 (first repair pass implementation). The C-series ran under tasks 448–450. C1 produced a failure taxonomy; C3 implemented the first pass. This doc captures the **design rationale** that C1's findings implied and C3's implementation followed.

## Failure Categories (from C1)

Based on observed pytest runs in this monorepo:

1. **Import-time hook failures** — PreToolUse/PostToolUse/Stop hooks fail at collection time because of sys.path, plugin-cache drift, or import alias mismatches.
2. **Cross-worktree path resolution** — Tests that resolve `P:/.claude/.state/` or `P:/.claude/hooks/` fail when run from a worktree.
3. **Stale `.pyc` cache** — Tests pick up compiled bytecode that no longer matches source after refactors.
4. **Plugin cache drift** — Hook code edited on `P:` but cache on `C:` not refreshed, so test imports pull the old version.
5. **Transient/sandbox hangs** — Long-collection hangs that don't fail but block the suite (e.g., snapshot scan, dream daemon).
6. **Constitutional filter overfires** — Tests that write to artifact paths that are not in the allowlist.

## Repair Tiers

### Tier 1 — Auto-fixable (no human review)

- **Stale `.pyc` cache** → `find . -name __pycache__ -type d -exec rm -rf {} +` (safe; bytecode regenerates).
- **Plugin cache drift** → `python plugin-audit-and-fix.py --bump <name>` (verified-safe; documented in skill).
- **Allowlist gaps** → edit `settings.json` per artifact convention; small, audited changes.

### Tier 2 — Parameterized rollbacks (one-line confirmation)

- **Import alias mismatches** → fix the alias in the plugin's `__lib/_bootstrap.py`; verify the import resolves in cache before/after.
- **Cross-worktree path** → read `terminal_id` from env, fall back to CWD-hash; already implemented in `_get_terminal_id()` (verified at `bf_agent.py`).

### Tier 3 — Manual investigation (must not be auto-fixed)

- **Constitutional filter overfires** — risk of removing a real safety check. Investigate allowlist, the test's write path, and the filter rule before changing either.
- **Hook code that imports a module that no longer exists** — risk of cascading failure. Investigate module relocation vs. test-only mocking.

## Safety Rails

- **Pre-fix gate:** `git diff --cached --name-only` (per CLAUDE.md Git Destructive Operation Guard). If it returns files, abort.
- **Edit-then-verify:** after every Edit/Write, Read the modified lines to confirm the change persisted. Windows 11 + WSL/Git Bash can silently drop edits.
- **No destroy-by-default:** prefer `--dry-run` and `--auto-fix --summarize` patterns. Never `git clean -f` or `git reset --hard` without explicit confirmation.
- **Run-then-summarize:** `run-qa-verification.py` already follows this pattern (refactored in #502 to use direct GTO import).

## Tooling

- **`run-qa-verification.py`** — primary runner. Direct GTO import per task #502.
- **`plugin-audit-and-fix.py --drift`** — plugin cache drift detection. Already in cc-skills-utils.
- **`gto`** — gap analysis. Detects Tier-1 issues automatically.
- **`/pre-mortem`** — pre-fix review for Tier-3 changes (after C-series completion).
- **`/recap`** + **`/rns`** — render results in RNS machine+human format.

## Acceptance Criteria for C3 (First Repair Pass)

- Stale `.pyc` cache eliminated from all cc-skills-* plugin tests.
- Plugin cache drift detection runs in CI; failures block the run.
- All tests resolve cross-worktree path correctly without env-var injection.
- No constitutional filter test is failing in steady state.

## Risk Register

| Risk | Mitigation |
|---|---|
| Auto-fix removes a real bug instead of a test issue | Tier-1 only touches cache + allowlist; never source logic |
| Plugin bump breaks a loaded session | Cache-refresh + `/reload-plugins` documented; never bump during active work |
| Rollback removes recent feature | Tier-2 changes scoped to a single alias/path; PR review catches broader removals |
| Manual investigation burns hours on a mockable issue | Tier-3 has a 30-min time-box per finding; if no root cause found, mock and move on |

## Related

- C1 evidence: tasks #448 (Run full pytest suite and classify failures) — completed
- C3 implementation: task #450 (Implement first repair pass) — completed
- `docs/planning/plan.md` — the 8-improvement plan for /refactor
- `references/agent-configs.md` — 5-agent configuration that includes the pytest-repair agent
