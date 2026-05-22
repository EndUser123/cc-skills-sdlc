# Common Pre-Mortem Method

This file defines the environment-neutral pre-mortem method. Claude Code, Codex, PI harnesses, and project profiles should use this as the shared quality bar.

## Purpose

A pre-mortem identifies predictable failures before implementation, trial runs, live operations, or irreversible changes. It should challenge happy-path assumptions, producer-only success proofs, stale state, dependency boundaries, and operational failure modes.

## Required Review Domains

Every standard or deep pre-mortem must cover:

- Intent and scope: what is being reviewed, what is explicitly out of scope, and whether the target is in a valid critiqueable state.
- Investigation type: what was reviewed statically, what was observed live, and what non-static probes still require permission.
- Consumer contract: what downstream users, validators, hooks, scripts, agents, or runtime paths require.
- Static predictable issues: logic, data validation, state transitions, paths, schemas, naming, and missing tests.
- Live/runtime predictable issues: external services, subprocesses, resource contention, retries, timeouts, auth/session expiry, and telemetry.
- Data safety: deletion scope, migration scope, rollback path, low-reversibility changes, and "must not touch" boundaries.
- Dependency chain: related code, supporting files, configuration, scripts, tests, and operational docs needed for the target to work.
- Evidence and verification: what concrete checks would downgrade, confirm, or overturn the findings.

## Consumer-Contract Review

For stateful, resumable, hook, artifact, handoff, benchmark, cleanup, or live-run targets, include a consumer-contract review:

- What does the producer promise?
- What does the consumer actually require?
- Where is the validator?
- What happens when required fields are missing, stale, partial, or malformed?
- Is the design proving only producer success instead of consumer success?

## Quality Bar

A useful pre-mortem is:

- Specific: findings identify a concrete failure mode and affected file, command, artifact, or runtime path.
- Ordered: highest-severity and lowest-reversibility risks appear first.
- Actionable: recommendations can be executed without a second design discussion.
- Evidence-bound: claims distinguish observed evidence from inference.
- Investigation-aware: static findings, live observations, and recommended probes are clearly separated.
- Scope-aware: recommendations do not silently expand ownership or architecture.

## Non-Goals

Do not use a pre-mortem to:

- Rewrite the architecture without user intent.
- Convert every local issue into an enterprise process.
- Treat missing evidence as proof of failure.
- Recommend destructive cleanup without data-safety boundaries.
- Hide uncertainty behind confident wording.
