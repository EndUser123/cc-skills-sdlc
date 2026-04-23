---
title: "pi CLI NVIDIA_NIM_API_KEY Requirement Bug"
summary: "pi v0.67.68 requires NVIDIA_NIM_API_KEY at startup even when using openrouter-only models — bug vs design investigation, workarounds, and upstream filing"
tags: [pi-cli, nvidia-nim, openrouter, multi-provider, bug-report]
created: 2026-04-22
source: "C:\\Users\\brsth\\Downloads\\● Problem Statement for External Review__  Title_.md"
---

# pi CLI NVIDIA_NIM_API_KEY Requirement Bug

## Problem

`pi --model openrouter/elephant-alpha` fails immediately at startup with:
```
NVIDIA NIM: NVIDIA_NIM_API_KEY environment variable is not set.
```
This happens **before** pi parses `--model` or contacts OpenRouter. Both OpenRouter and NVIDIA API keys are stored in `~/.pi/agent/auth.json`. Curl confirms openrouter/elephant-alpha works directly with the openrouter key.

## Root Cause (Inferred)

The `@mariozechner/pi-ai` provider initialization checks `NVIDIA_NIM_API_KEY` unconditionally during startup, before model routing. Not in plaintext JS source (`"NVIDIA NIM"` absent) — likely in bundled/minified code or the `pi-ai` provider init.

## Bug vs Design

- **Likely a bug**: Multi-provider CLIs typically validate lazily per-provider after model selection. No documentation mandates NVIDIA key for OpenRouter-only usage.
- **No existing GitHub issue** matches this exact error string in `badlogic/pi-mono/issues`.
- **No Reddit threads** document this specific failure.
- NVIDIA's own docs only require NIM keys **when calling NIM endpoints** — no NVIDIA guidance justifies enforcing NIM key presence for non-NIM provider usage.

## Workarounds

| Approach | Command | Likelihood |
|----------|---------|------------|
| Dummy env | `NVIDIA_NIM_API_KEY=dummy pi --model openrouter/elephant-alpha` | High |
| auth.json | Add `"nvidia-nim": "nvapi-dummy"` to `~/.pi/agent/auth.json` | Medium |
| Fork & patch | Clone `badlogic/pi-mono`, patch provider init, npm pack | High |

## Recommended Actions

1. Test `NVIDIA_NIM_API_KEY=dummy` workaround first
2. File issue at `github.com/badlogic/pi-mono` with exact `pi --version`, env state, and curl confirmation that OpenRouter works directly
3. Patch `packages/ai/src/providers/nvidia-nim.ts` to lazy-init instead of global startup check

## Source

- [[pi-mono repo]](https://github.com/badlogic/pi-mono) — source for pi coding agent
- [[pi issues]](https://github.com/badlogic/pi-mono/issues) — no existing issue for this error