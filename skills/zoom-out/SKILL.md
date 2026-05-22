---
name: zoom-out
description: Tell the agent to zoom out and give broader context or a higher-level perspective. Use when you're unfamiliar with a section of code or need to understand how it fits into the bigger picture.
---
# Zoom Out

> "I don't know this area of code well. Go up a layer of abstraction. Give me a map of all the relevant modules and callers, using the project's domain glossary vocabulary."

## When to Use

- Unfamiliar with a code section
- Need to understand how a module fits into the bigger picture
- Starting work on a new area of the codebase
- Onboarding to an unfamiliar component

## What to Ask For

Request a map covering:
- All relevant modules and their relationships
- Key callers and callees
- Domain glossary terms used in the codebase
- Architectural layers and boundaries

## Response Expectations

The agent should provide:
1. High-level module map
2. Key dependencies and relationships
3. Domain terminology glossary
4. Entry points and exit points

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
