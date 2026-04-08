# Artifact Contract & V1 vs V2 Differences

## Key Differences from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Artifact shape | Normalized plan + findings + verification in one file | Plan artifact only; findings in separate files |
| Placeholder handling | auto_fix inserts placeholder content | auto_fix does NOT insert placeholders; draft stays draft |
| Readiness gate | `auto_verify` passes if no HIGH findings | Blocked if any placeholders, contradictions, or unresolved blockers |
| Status tracking | None | `draft` -> `in-review` -> `implementation-ready` |
| auto_fix scope | Adds missing sections with placeholder content | Non-semantic repairs only (headers, ordering, metadata) |
| Review output | Appended to plan file | Separate `*.review.summary.md`; plan stays pure |

## Separate Files (not merged into plan)

- **Plan artifact**: `*.md` -- only the implementation specification
- **Verification result**: `*.review.result.json` -- deterministic check output
- **Findings**: `*.review.findings.json` -- raw adversarial findings per agent
- **Review summary**: `*.review.summary.md` -- synthesized change list plus machine-readable disposition table

## Plan Artifact Structure

Every plan artifact MUST begin with this status header:

```markdown
---
status: draft | in-review | implementation-ready
source: <path to ADR, transcript, or null>
unresolved_blockers: <integer>
---

# Plan: <title>
```

The plan artifact itself must contain ONLY:
- Goal
- Current state with evidence
- Design decisions and invariants
- Implementation changes (with concrete scope per change)
- Test matrix
- Assumptions/defaults
- Open questions

Legacy v1 section headings are accepted during migration, but `auto_fix.py` normalizes them to the v2 canonical headings above.

## ADR-to-Plan Handoff

When the source artifact is an ADR, the authoritative ingestion order is:

1. `Planning Handoff Packet` from `/arch` when present
2. `Contract Authority Packet` for boundary semantics when present
3. ADR prose as explanatory source material only

ADR headings such as `Context`, `Design`, `Dependencies`, `Consequences`, or `Implementation Sequence` are not valid plan sections. `/planning` must map those sources into the canonical plan artifact shape before writing the first draft.

If `/planning` writes a draft that still uses ADR headings or reduced matrix columns, that is a planning rewrite defect, not proof that `/arch` must be reinvoked.

If `/planning` invokes `/arch` from verification while repairing such a plan, that `/arch` call is a nested remediation step. Control returns automatically to `/planning`; the user should not have to rerun `/planning` manually.

## Source-to-Plan Handoff

When the source artifact is not an ADR, the authoritative ingestion order is:

1. `Planning Source Packet` embedded in the source artifact when present
2. Explicit extraction map built by `/planning`
3. Source prose as explanatory material only

Arbitrary source headings are not valid plan sections. `/planning` must map those sources into the canonical plan artifact shape before writing the first draft.

If `/planning` writes a draft that still mirrors source headings or reduced matrix columns, that is a planning rewrite defect, not proof that `/arch` must be reinvoked.

Source-derived rewrite defects are still owned by `/planning` even when `/arch` provided upstream decisions. `/arch` closes the architecture; `/planning` resumes automatically and finishes the plan rewrite.

The plan artifact must NOT contain:
- Raw adversarial findings tables
- Verification dumps or audit logs
- Placeholder text (`TODO`, `TBD`, `path/to/`, `Component A`, etc.)

## Review Summary Disposition Table

`*.review.summary.md` MUST include a disposition table:

```markdown
## Finding Dispositions

| Finding ID | Disposition | Rationale |
|------------|-------------|-----------|
| SEC-001 | accepted | Incorporated into locking design |
| TEST-004 | deferred | Follow-up task after v1 rollout |
| LOGIC-002 | rejected | Reviewer concern invalid after state-machine simplification |
```
