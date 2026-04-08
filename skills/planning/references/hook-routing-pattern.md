# Thin Global Routing Hook Pattern

## Principle

A global PostToolUse hook must be a **thin router**, not a semantic brain.

- The global hook detects file type or artifact marker and dispatches to the owning skill's validator.
- It carries no domain logic of its own.
- Heavy validation semantics live in the skill that owns the artifact.

## Rationale

When a global hook accumulates semantic logic, every schema change requires editing a shared file with broad blast radius. New artifact types can silently alter the hook's behavior in unexpected ways.

Keeping the global hook thin means:
- Each skill owns its validator and can evolve it independently.
- The global hook's behavior is predictable: it always routes, never decides.
- Skill-level validators can be tested in isolation.

## Pattern

```
PostToolUse (global, thin)
  → detect file type or artifact marker
  → dispatch to skill-owned validator
  → return exit code from validator, not own verdict
```

**Current instance:** `PostToolUse_contract_authority_validator.py` is advisory-only and does not carry semantic authority — it routes to skill validators. This is intentional. Do not add semantic logic to global hooks; extend skill-owned validators instead.

## Advisory vs Blocking

The global routing hook is advisory only. Skill-owned validators invoked from consumer precheck carry enforcement weight. This separation ensures:
- False positives in advisory mode do not block work.
- Skill-level enforcement is explicit and tied to the consumer's execution context.

## Reference

- `/code` SKILL.md — Consumer Contract Precheck (enforcement-lives-with-consumer principle)
- `/planning` SKILL.md — Graduated Validation Modes