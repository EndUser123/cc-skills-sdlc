# Contract Authority Packet (CAP)

> **Step 5 output** — emitted when a design decision is **contract-sensitive**.

A CAP is a structured artifact that binds the design decision to its evidence chain and enforcement mechanism. It is not a summary — it is a **commitment record** that downstream systems can verify.

---

## When to Emit a CAP

A design is contract-sensitive when ANY of these are true:
- It introduces a new plugin, hook, or skill that modifies Claude Code behavior
- It changes how files are edited, created, or deleted
- It adds a new dependency on external resources (APIs, databases, external services)
- It creates new conventions that other skills are expected to follow
- It affects session state that persists across terminal sessions

**If in doubt, emit a CAP.** The cost of a CAP is low; the cost of a missed contract is high.

---

## CAP Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `title` | Yes | Short name for the decision |
| `date` | Yes | ISO date (YYYY-MM-DD) |
| `status` | Yes | `proposed` / `accepted` / `deprecated` |
| `problem_statement` | Yes | What problem does this solve (1-2 sentences) |
| `audit_summary` | Yes | 2-3 sentences: what was audited, what was found, what gap remains |
| `reuse_decision` | Yes | `reuse` / `refactor` / `build` — with justification |
| `affected_systems` | Yes | List of files, skills, hooks, or agents this decision touches |
| `conventions_introduced` | No | New naming, filing, or behavioral conventions other skills must follow |
| `reversal_criteria` | Yes | What condition would make us undo this decision? |
| `verification_evidence` | Yes | File paths or test output proving the decision was implemented as specified |
| `gaps_addressed` | Yes | List of gap IDs from the Gap Analysis Report this solves |
| `authority` | Yes | Who approved this, or `none` if proposed |

---

## Output Format

```markdown
# Contract Authority Packet: {title}

**Status:** {status}
**Date:** {date}
**Authority:** {authority}

## Problem Statement

{problem_statement}

## Audit Summary

{audit_summary}

## Reuse Decision

**Decision:** {reuse|refactor|build}
**Justification:** {why this approach was chosen}

## Affected Systems

- {affected_system_1}
- {affected_system_2}

## Conventions Introduced

{conventions_introduced}  # omit if none

## Reversal Criteria

{reversal_criteria}

## Verification Evidence

- {evidence_1}
- {evidence_2}

## Gaps Addressed

- Gap {id}: {gap description from Gap Analysis Report}
```

---

## Storage Convention

Place CAPs in:
```
.claude/design/contracts/{title-slug}.md
```

This path is auto-scannable by other skills that need to verify existing contracts before proposing changes.

---

## Enforcement

A CAP without `reversal_criteria` is **invalid** — return it for completion before proceeding past Step 5.

A CAP without `audit_summary` is **invalid** — the audit-first step must precede contract closure.

---

## Worked Example: Mutation Testing CAP

```markdown
# Contract Authority Packet: Add mutation testing for skill_guard.breadcrumb.inference

**Status:** accepted
**Date:** 2026-06-06
**Authority:** solo

## Problem Statement

The skill-guard inference module classifies user intent into skills. A bug in
this classifier silently misroutes user requests to the wrong skill. Unit tests
with 95% line coverage are not the same as tested behavior — we need to measure
fault-detection strength, not just execution coverage.

## Audit Summary

Audited coverage of skill_guard.breadcrumb.inference: 95% line, 88% branch.
Audited mutation-testing landscape: mutmut 3.x selected (see selection rationale
in `design/resources/python.md`). Confirmed mutmut 3.6.0 is installable in
Python 3.14 + pip 26.0.1. No equivalent tool (cosmic-ray, mutpy) is actively
maintained for 2025+ Python.

## Reuse Decision

**Decision:** reuse (build on existing mutmut 3.x)
**Justification:** No custom mutation harness needed. mutmut supports
coverage-guided mode and pytest integration natively. Reusing avoids the
maintenance burden of a custom tool.

## Affected Systems

- P:/.claude/quality_gates.json (new — single source of truth for mutation targets)
- skills/__lib/mutation_config.py (new — shared reader across 5 SDLC skills)
- skills/__lib/tests/test_mutation_config.py (new — 17 tests, all passing)
- skills/design/resources/python.md (updated — Test Tooling Selection section)

## Conventions Introduced

- Mutation score target: 60% default, 80% for critical-path modules
- Equivalent-mutant budget: 15% of total mutants per module
- Module tiers: `critical` and `standard`
- Waiver required for sub-target scores on critical modules
- Single source of truth: P:/.claude/quality_gates.json (v1 schema)

## Reversal Criteria

- mutmut 3.x becomes unmaintained → migrate to next-generation tool; the
  quality_gates.json `tool.version` block encodes the version constraint
- Mutation testing slows CI by >2x → drop coverage-guided mode, or drop
  below-critical modules from mandatory mutation testing
- Equivalent-mutant budget proves unworkable in practice → re-tune threshold
  based on 90 days of real data

## Verification Evidence

- `python -c "import mutation_config"` → success
- `pytest skills/__lib/tests/test_mutation_config.py` → 17 passed in 0.22s
- `mutmut 3.6.0` installed and importable

## Gaps Addressed

- Gap M-001: Unit tests covered lines, not behavior. Now measured by mutation score.
- Gap M-002: No critical-path weighting. Now enforced via quality_gates.json.
- Gap M-003: No equivalent-mutant policy. Now explicit 15% threshold per module.
```

This example demonstrates how a CAP binds a tool-selection decision (mutmut 3.x)
to its evidence chain (installation, schema, unit tests) and the conventions it
introduces (single source of truth, tier-based targets).
