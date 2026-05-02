---
name: improve-codebase-architecture
description: Surface architectural friction and propose deepening opportunities — refactors that turn shallow modules into deep ones. Use when code architecture is causing friction, modules are shallow, or there are testability issues.
category: architecture
enforcement: advisory
triggers:
  - improve architecture
  - refactor
  - shallow modules
  - deepen modules
  - architectural friction
  - testability
workflow_steps:
  - explore: Read project glossary and ADRs, use Explore subagent to walk codebase
  - present: Present numbered deepening opportunities with files, problem, solution, benefits
  - grill: Walk design tree — constraints, dependencies, shape of deepened module, tests
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities** — refactors that turn shallow modules into deep ones. The aim is testability and AI-navigability.

## Glossary

Use these terms exactly in every suggestion. Consistent language is the point — don't drift into "component," "service," or "boundary."

- **Module** — anything with an interface and an implementation (function, class, package, slice).
- **Interface** — everything a caller must know to use the module: types, invariants, error modes, ordering, config. Not just the type signature.
- **Implementation** — the code inside.
- **Depth** — leverage at the interface: a lot of behaviour behind a small interface.
- **Seam** — where an interface lives; a place behaviour can be altered without editing in place.
- **Adapter** — a concrete thing satisfying an interface at a seam.
- **Leverage** — what callers get from depth.
- **Locality** — what maintainers get from depth: change, bugs, knowledge concentrated in one place.

Key principles:

- **Deletion test**: imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.**
- **One adapter = hypothetical seam. Two adapters = real seam.**

## Process

### 1. Explore

Read the project's domain glossary and any ADRs in the area you're touching first. Then use the `Explore` subagent to walk the codebase. Note where you experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow**?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called (no **locality**)?
- Where do tightly-coupled modules leak across their seams?
- Which parts are untested, or hard to test through their current interface?

### 2. Present candidates

Present a numbered list of deepening opportunities. For each:

- **Files** — which files/modules are involved
- **Problem** — why the current architecture is causing friction
- **Solution** — plain English description of what would change
- **Benefits** — explained in terms of locality and leverage

Use CONTEXT.md vocabulary for the domain, and LANGUAGE.md vocabulary for the architecture. ADR conflicts: only surface when friction is real enough to warrant revisiting. Mark clearly. Do NOT propose interfaces yet.

### 3. Grilling loop

Walk the design tree with them — constraints, dependencies, the shape of the deepened module, what sits behind the seam, what tests survive.

Side effects happen inline as decisions crystallize:

- **Naming a deepened module after a concept not in `CONTEXT.md`?** Add the term.
- **Sharpening a fuzzy term?** Update `CONTEXT.md` right there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR framed appropriately.
- **Want to explore alternative interfaces?** See INTERFACE-DESIGN.md.
