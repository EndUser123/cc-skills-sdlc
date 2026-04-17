---
name: sqd
version: 0.1.0
status: prototype
description: SDLC Quality Dispatcher — parallel multi-LLM adversarial review dispatcher. Use when running adversarial review across multiple LLM providers simultaneously, or when a single review needs to be stress-tested by competing perspectives from DeepSeek, Gemini, Claude, and GPT models.
category: quality
enforcement: advisory
triggers:
  - /sqd
workflow_steps:
  - dispatch_agents
  - collect_findings
  - synthesize_results
---

# /sqd — SDLC Quality Dispatcher

## Purpose

Parallel multi-LLM adversarial review dispatcher. Spawns adversarial review agents across multiple LLM providers (DeepSeek, Gemini, Claude, GPT) simultaneously and synthesizes their competing findings.

## When to Use

- `/sqd <target>` — Run adversarial review with multiple LLM perspectives in parallel
- When a single model's review might miss systemic issues
- When adversarial consensus needs to be established before shipping

## Execution

```bash
cd "P:/packages/sdlc" && python -m sqd dispatch --target "<path or description>" --models deepseek gemini claude --parallel
```

## Architecture

```
sqd/
├── SKILL.md           ← This file
├── layers/            ← Review dispatch layers
│   ├── __init__.py
│   └── dispatcher.py  ← Parallel spawn + synthesis
├── lib/               ← Shared utilities
│   └── __init__.py
├── hooks/             ← Pre/post dispatch hooks
├── findings/          ← Output artifacts
└── tests/            ← Test suite
```

## Exit Codes

- 0: All models returned consensus (or all agreed no issue)
- 1: Divergent findings — synthesis report written to `findings/`
- 2: One or more models failed to respond
- 3: Dispatch target not found or inaccessible

## Related Skills

- `/sqa` — Sequential quality assurance (single-model, audit mode)
- `/planning` — Planning with adversarial review slot
- `/arch` — Architecture review with ADR critic
