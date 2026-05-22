# Static Test Contract

Static tests are the default validation layer for pre-mortem quality. They check package structure, prompt wiring, schemas, static references, and review coverage without running live systems or mutating external state.

## Required Static Checks

Every change to the pre-mortem package should be covered by static checks for:

- layout: required skills, references, adapters, scripts, and phase prompts exist;
- path resolution: installed adapters do not reference paths that break after symlink or junction installation;
- specialist availability: every specialist named by Phase 1 exists in the package-owned `agents/` folder;
- prompt wiring: Phase 1, Phase 2, and Phase 3 mention required gates and output sections;
- investigation coverage: static and non-static investigation are separated;
- logic review: logical correctness is either covered by `adversarial-logic` or explicitly waived with a reason;
- output coverage: final synthesis includes investigation coverage, review lens coverage, risks, recommendations, and verification;
- generated artifacts: source folders do not rely on `__pycache__`, `.pytest_cache`, or stale generated files;
- version/cache hygiene: plugin version changes when installed plugin cache must refresh.

## Static Checks That Are Not Enough

Static tests cannot prove:

- Claude Code has refreshed its plugin cache;
- Codex can read an installed adapter through a junction;
- helper code can create and recover a real session directory;
- a selected specialist can execute in the current agent runtime;
- a live benchmark, NotebookLM operation, browser profile, auth check, or external CLI behaves correctly.

When static tests are insufficient, report the required non-static validation using `references/non-static-validation.md`.

## Minimum Local Commands

```powershell
powershell -ExecutionPolicy Bypass -File P:\packages\cc-skills-sdlc\skills\pre-mortem\scripts\verify-pre-mortem-layout.ps1
python -m pytest P:\packages\cc-skills-sdlc\skills\pre-mortem\tests
```

These commands are necessary but not sufficient for plugin-install confidence. Use the live validation script when validating actual Claude/Codex availability.
