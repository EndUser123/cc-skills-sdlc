# Audit-First Protocol

> **Non-negotiable**: Search existing implementations before routing to any template or proposing new infrastructure.

## When to Run

Run this protocol for ALL design/architecture tasks:
- Proposing new infrastructure, tools, or utilities
- Writing ADRs or design documents
- Solving problems that might already have partial solutions
- Refactoring existing systems
- Making architectural decisions

## Audit Steps

1. **Search the codebase** for existing implementations in relevant categories:
   - File editing/patching tools
   - Validation/verification scripts
   - Cache management utilities
   - Path handling/sanitization
   - Hook systems
   - MCP servers
   - CLI tools
   - Similar utilities in `__lib/`

2. **Identify reusable components** — what already solves part of the problem

3. **Map integration points** — where existing code could be extended

4. **Document gaps** — what is genuinely missing

## Gap Analysis Report

Produce this structured output before proceeding:

```
## Gap Analysis: [Problem Statement]

### Existing Functionality Audit

| Component | Location | Current Capability | Reusable? |
|---|---|---|---|
| [name] | `path/to/file.py` | Does X | Yes/Partial/No |
| [name] | `path/to/tool` | Does Y | Yes/Partial/No |

### Reuse Opportunities

**Reusable as-is:**
- [component] already solves [specific aspect]

**Refactorable with minimal change:**
- [component] can be extended by [specific change]

**Composable:**
- [component A] + [component B] can be combined to [outcome]

### Genuine Gaps

**Missing functionality:**
1. [gap 1] — no existing solution
2. [gap 2] — existing solutions incomplete for [reason]

### Minimal-Change Recommendation

[Describe the smallest viable change that maximizes reuse]

**Approach:**
- Reuse: [list]
- Refactor: [list with before/after]
- Build new: [list with justification]

**Decision bias: Reuse > Refactor > Build**
```

## Decision Framework

Use this decision tree after audit:

```
Does existing code already solve this?
├─ YES → Reuse as-is (stop here, emit recommendation)
├─ NO
  ├─ Can existing code be extended with minimal change?
  │   ├─ YES → Refactor/extend (proceed with extension plan)
  │   └─ NO
  │     ├─ Can partial solutions be composed?
  │     │   ├─ YES → Compose existing pieces
  │     │   └─ NO
  │     └─ Genuine gap → Build new (document in ADR)
```

## Red Flags (Audit Violations)

These patterns indicate the audit was skipped:
- Proposing a new utility when similar ones exist
- Building "just in case" infrastructure
- Duplicating logic that already exists elsewhere
- "We need a new X" without proving existing X is insufficient

## Enforcement

If a design proposal arrives without a Gap Analysis Report, **reject it** and request the audit first. This is non-negotiable for:
- New CLI tools
- New utility modules
- New validation/verification infrastructure
- New cache management
- New file-editing mechanisms

## Feed-Forward (Downstream Integration)

Every design output should be consumable by downstream orchestrators: `/go`, `/planning`, `/executing-plans`, `/writing-plans`.

**Machine-readable stub** — write this to `.claude/design/pending/{slug}.json`:

```json
{
  "title": "{title}",
  "status": "proposed",
  "reuse_decision": "reuse|refactor|build",
  "gaps": ["gap description"],
  "affected_systems": ["path/to/file"],
  "contract_path": ".claude/design/contracts/{slug}.md"
}
```

**What downstream skills do with it:**
- Scan `.claude/design/pending/` on startup
- Create task items from pending designs
- Check `affected_systems` before operating on those files
- Move to `.claude/design/contracts/` when the design is accepted and implemented

This means `/design` doesn't need to know which orchestrator will be used — any of them can find and consume the output.

## Fast Path

For **fast** queries (single file, clear scope), the audit may be minimal:
- Check 2-3 most likely locations
- If reusable component found, return it immediately
- Only document genuinely missing pieces

For **deep** queries or ADRs, full audit is required.
