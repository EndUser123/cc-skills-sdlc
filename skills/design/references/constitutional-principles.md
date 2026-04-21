# Constitutional Principles Reference

## Multi-Terminal Isolation

All architecture decisions MUST evaluate multi-terminal concurrency safety. Every design is assessed under the assumption that multiple Claude Code terminals may operate on the same workspace simultaneously.

### Evaluation Requirements

1. **Identify shared mutable state**: Does this design create or modify files, databases, or in-memory state that could be accessed by multiple terminals?

2. **Assess concurrency safety**: Can multiple terminals execute this pattern simultaneously without:
   - Data races (corrupted state)
   - Stale reads (terminal A sees outdated state)
   - Lost updates (write from terminal A overwrites terminal B silently)

3. **Check propagation mechanisms**: If state changes, how do other terminals discover the change?
   - File-based state: Requires polling or file system events
   - Database-based state: Requires query or notification mechanism
   - In-memory state: Cannot propagate across terminals (violates isolation)

4. **Document edge cases**:
   - Terminal A writes while terminal B reads?
   - Two terminals write simultaneously?
   - A terminal crashes mid-operation?
   - Network filesystem has delays?

### Red Flags Requiring Explicit Mitigation

- ❌ Shared JSON/YAML files without atomic write + locking
- ❌ SQLite databases without WAL mode or proper transaction isolation
- ❌ In-memory caches without per-terminal isolation
- ❌ File-watching without debounce and deduplication
- ❌ State files without terminal_id namespace isolation

---

## Stale Data Immunity

All designs MUST define how stale data is detected and handled.

### Staleness Contract

For any state-bearing artifact (file, DB row, cache entry, envelope):

| Question | Must Answer |
|----------|-------------|
| What makes this data stale? | Invalidation trigger |
| Who decides freshness? | Freshness authority |
| What happens when stale? | Failure behavior |
| How is staleness detected? | Detection mechanism |

### Default Staleness Policy

If no explicit staleness policy is defined:

- **File-based state**: Compare mtime against operation start time; if file mtime < operation start, data is potentially stale → verify from authoritative source
- **Database state**: Use version columns or timestamps; if no version info, treat as potentially stale
- **In-memory state**: Cannot be shared across terminals → terminal-private scope only

---

## Hook Design Constraints

All hook-related architectural decisions MUST satisfy:

| Constraint | Description |
|------------|-------------|
| No external API calls | Hooks must operate locally; no network dependencies |
| Standalone operation | Hooks must work without importing skill-specific modules |
| No side effects beyond scope | Hooks must not modify state outside their declared boundary |
| Import path resilience | Hooks must resolve imports regardless of execution context (skill hooks vs. core hooks run from different working directories) |
| Graceful degradation | Hook failures must not block the parent operation |

### Import Path Pattern

For hooks that need shared library access:

```python
from pathlib import Path
import sys

# Resolve __lib relative to this file's parent's parent
_lib_dir = Path(__file__).resolve().parent.parent / "__lib"
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

# Now imports work regardless of cwd
from hook_base import hook_main
```

---

## Stateful Design Evaluation

For persistence, history, archive, provider, watermark, multi-terminal, or event-driven designs, `/arch` must close the following contracts explicitly before presenting an implementation-ready recommendation:

| Contract | Question |
|----------|----------|
| Identity model | How is each entity uniquely identified? |
| Ordering contract | What ordering is guaranteed? |
| Dedupe contract | How are duplicates detected and prevented? |
| Freshness/invalidation contract | What makes data stale and how is it handled? |
| Event source of truth | Which system owns the authoritative state? |
| Decision-closure status | Is this design complete or are gaps named? |

---

## Producer/Consumer Handoff Contract

For any producer/consumer boundary, `/arch` must close the handoff contract explicitly:

| Field | Question |
|-------|----------|
| Boundary name | What exact handoff is crossing a boundary? |
| Producer | Who emits or writes it? |
| Consumer | Who reads, restores, routes, or executes from it? |
| Input schema | What must exist before the producer runs? |
| Output schema | What does the consumer expect to receive? |
| Required vs optional fields | Which fields are mandatory? |
| Freshness authority | Which source wins if data disagrees? |
| Invalidation trigger | What exact event makes this output stale? |
| Failure behavior | What happens when required data is missing or stale? |
| Verification/test binding | Which test proves this boundary works end-to-end? |

**Rule**: `/arch` must not accept "the consumer probably has this field" as a valid design assumption.

---

## Safety Policy Gate

For contract-sensitive boundaries:

- **Must NOT default to fail-open** without explicit justification
- If degraded/fail-open is allowed, the ADR must name:
  - The exact boundary
  - The bounded blast radius
  - The condition under which degraded mode is entered
  - Why the degraded path is safe enough
- Vague phrases like "warn only" or "fail-open with warning" are invalid unless explicitly justified as bounded degraded mode

---

## Router Precision Gate

If the ADR introduces a router, gate, classifier, or activation layer, it must specify:

| Requirement | Description |
|-------------|-------------|
| Activation criteria | Exact conditions under which the router activates |
| Non-activation / bypass criteria | Exact conditions under which the router does NOT activate |
| Ambiguous classification behavior | What happens when classification cannot determine a path |
| Fail behavior | What happens when routing cannot determine the correct path |

Phrases like "detects patterns" or "routes to validators" are **not** sufficient closure by themselves.

---

## Red Flags Summary

| Red Flag | Severity | Action |
|----------|----------|--------|
| Shared state without terminal isolation | P0 | Block until resolved |
| No staleness detection for persisted state | P0 | Block until resolved |
| Contract-sensitive design without packet | P1 | Block until closed |
| Hook with external API dependency | P1 | Reject |
| Router without fail behavior defined | P1 | Block until specified |
| Producer/consumer without explicit schema | P1 | Block until specified |
| Vague degraded mode justification | P2 | Request clarification |
| Unnamed validator owner | P2 | Request assignment |
