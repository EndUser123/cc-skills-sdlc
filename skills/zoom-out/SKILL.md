---
name: zoom-out
description: Tell the agent to zoom out and give broader context or a higher-level perspective. Use when you're unfamiliar with a section of code or need to understand how it fits into the bigger picture.
category: exploration
enforcement: advisory
disable-model-invocation: true
triggers:
  - zoom out
  - broader context
  - higher level
  - understand the bigger picture
  - unfamiliar with this code
workflow_steps:
  - orient: Ask agent to go up a layer of abstraction
  - map: Request module map with callers and domain glossary
  - clarify: Ask for entry points and exit points
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
