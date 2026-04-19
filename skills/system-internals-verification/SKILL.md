---
name: system-internals-verification
description: Mandatory verification protocol before claiming how system components work.
version: "1.0.0"
status: stable
category: verification
triggers:
  - 'how does'
  - 'how does the system'
  - 'how do skills work'
  - 'how do commands work'
  - 'how do hooks work'
  - 'how does routing work'
  - 'how does discovery work'
aliases:
  - '/system-internals'
suggest:
  - /research
---

## Purpose

Before claiming how ANY system component works (skills, commands, hooks, routing, discovery), you MUST verify by reading the actual code.

## Required Protocol

1. **State intent**: "I will verify by reading [specific file path]"
2. **Actually read**: Call Read/Grep on that file
3. **Cite evidence**: "Per `file.py:127-135`, this works by..."

## Valid Claim Format

```
Per `P:/.claude/hooks/UserPromptSubmit_command_directive_injector.py:45-52`:
Commands are discovered by scanning .claude/commands/ for .md files.
```

## Invalid Claim Format

```
The system is looking for a command (.md file in commands/), not a skill.
[No prior Read, no file:line citation]
```

## If You Cannot Cite a Specific file:line

- Say: "I would need to read [specific file] to verify how this works"
- Do NOT make claims about internal behavior

## Covered Topics (Require Citation Before Claiming)

- How skills/commands are discovered or routed
- How hooks are triggered or ordered
- What files the system expects or searches for
- How any Claude Code component works internally

## Trigger

Activate when:
- About to claim how a system component works
- Explaining system behavior
- Describing internal mechanisms
- Answering "how does X work" questions
