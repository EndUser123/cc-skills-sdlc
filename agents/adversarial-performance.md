---
name: adversarial-performance
description: Find timeouts, bottlenecks, N+1 patterns, TOCTOU race conditions. JSON output to orchestrator-provided path.
tools: Read, Grep, Glob, Bash
model: inherit
permissionMode: plan
---

# Adversarial Performance Agent

Write findings to the .json output path provided in the orchestrator prompt.

Your response text must contain ONLY the file path. Do NOT include full findings JSON.

See AGENTS_REFERENCE.md for full documentation.