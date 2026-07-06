---
name: review-pr
disable-model-invocation: true
description: "DEPRECATED — use /review (pr mode is the default). Multi-agent PR review."
enforcement: advisory
workflow_steps: []
---

# /review-pr — DEPRECATED

`/review-pr` is now `/review` (the `pr` mode is the default). Use:

```
/review                  # same multi-agent PR review
/review tests errors     # aspect-specific
```

The original workflow (code-reviewer, pr-test-analyzer, comment-analyzer, silent-failure-hunter, type-design-analyzer, code-simplifier) is preserved as `/review`'s default mode. See `skills/review/SKILL.md`.

This stub will be removed after one release cycle.
