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
