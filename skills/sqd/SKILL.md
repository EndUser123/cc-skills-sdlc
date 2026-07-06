---
name: sqd
disable-model-invocation: true
description: "DEPRECATED — use /review multi. Parallel multi-LLM adversarial review dispatcher."
enforcement: advisory
workflow_steps: []
---

# /sqd — DEPRECATED

`/sqd` is now `/review multi`:

```
/review multi           # parallel DeepSeek/Gemini/Claude/GPT adversarial dispatch
```

The sqd **engine is unchanged** — `/review multi` invokes it via:

```bash
cd "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc" && python -m sqd dispatch --target "<path>" --models deepseek gemini claude --parallel
```

Phase gates (dispatch → collect → synthesize), exit codes (0 consensus / 1 divergence / 2 agent failure / 3 target not found), and synthesis artifacts in `findings/` are all preserved. Engine code in `layers/dispatcher.py`, `__lib/`, `__main__.py` is untouched. This stub will be removed after one release cycle.
