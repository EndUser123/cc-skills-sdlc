---
name: design-v1
description: "TOMBSTONE — design-v1 is unregistered and its referenced runtime (P:\tools\research_run_v1) has been relocated to P:\packages\research_runtime\. The contract-driven decision synthesis engine lives at research_runtime.design but is not wired into any skill dispatch. Canonical /design is the registered architecture-advisor skill (cc-skills-sdlc:/design)."
enforcement: tombstone
workflow_steps: []
---

# `/design-v1` — TOMBSTONE

**This skill is not registered and cannot be invoked.**

The `research_runtime.design.synthesize()` function exists in the shared
research-runtime package but is not wired into any Claude Code skill dispatch
mechanism (no plugin.json entry, no router.py entry, no settings.json hook).

**Do not register this skill.** The decision-contract workstream (decision-request.v1,
decision-result.v1, synthesis) is unresolved and should remain unregistered until
a future task integrates it into the canonical `/design` workstream.

## What happened

- Old path: `P:\tools\research_run_v1\design.py`
- New path: `P:\packages\research_runtime\src\research_runtime\design.py`
- Old import: `from tools.research_run_v1.design import synthesize`
- New import: `from research_runtime.design import synthesize`
- Registered skill: `cc-skills-sdlc:/design` (architecture advisor, unrelated)
- This file: TOMBSTONE only

## Historical note

design-v1 was created as a contract-driven decision synthesis prototype. It was
never wired into dispatch. The decision contracts (decision-request.v1,
decision-result.v1) remain valid schemas in the research_runtime package, but
no consumer currently reads them at runtime. The canonical `/design` skill
(cc-skills-sdlc) is an independent architecture-advisor workflow with no
shared code with this tombstone.

See `P:\docs\research-run-v1.md` for the canonical research-run spec.
See `P:\packages\research_runtime\src\research_runtime\` for the shared runtime.
