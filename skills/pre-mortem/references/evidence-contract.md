# Evidence Contract

Pre-mortem output must be bound to evidence gathered in the current turn, current session, or cited artifacts.

## Evidence Levels

- Observed: directly read from file, command output, log, test result, trace, or current runtime state.
- Inferred: reasoned from observed evidence but not directly proven.
- Unverified: from memory, prior summary, or likely convention that was not refreshed.

Findings should mark inference or uncertainty when evidence is incomplete.

## Verification Requirements

Before claiming a pre-mortem workflow is complete:

- Verify referenced paths exist when they are central to the finding.
- Verify moved or renamed prompt files are still referenced correctly.
- Run available layout or unit tests when code or package structure changed.
- For live-run readiness, specify the exact smoke or guarded run that proves the change.
- For deletion/cleanup work, verify fail-closed behavior and safe target selection before live use.

## Artifact Guidance

Claude Code may write pre-mortem evidence under `.claude/.evidence` and `.claude/.artifacts` when the primary Claude workflow is active.

Codex and PI adapters should prefer repo-local evidence paths, for example:

```text
.logs/pre-mortem/<timestamp>/
```

Do not write persistent state inside an ephemeral plugin installation directory.
