---
name: uci
disable-model-invocation: true
description: "DEPRECATED — use /review full. Unified Code Inspection (14-agent registry, 3-tier verdict)."
enforcement: advisory
workflow_steps: []
---

# /uci — DEPRECATED

`/uci` is now `/review full`:

```
/review full             # auto-depth (triage→comprehensive)
/review full --lite      # force 3-agent
/review full --full      # force 14-agent
```

The uci **engine is unchanged** — `/review full` dispatches into this directory:
- Agent registry, mode detection, sequential trigger, memory integration → `references/`
- Executable internals → `__lib/`
- Tests → `tests/`

The earlier in-doc claim that "`/review` and `/adversarial-review` were consolidated into this skill" is superseded: `/uci` now folds under `/review` as its `full` mode. This stub will be removed after one release cycle.
