---
title: "Compact Handoff Misframe Failure Analysis"
summary: "How session summary incorrectly promoted a clarifying question ('what does skill-creator optimize?') into an implementation directive, causing code changes instead of answering the question — root cause and optimal solution"
tags: [compact-handoff, session-summary, skill-craft, skill-creator, agent-failure]
created: 2026-04-22
source: "C:\\Users\\brsth\\Downloads\Conversation with claude code about handoff pre-co.md"
---

# Compact Handoff Misframe Failure Analysis

## The Incident

Post-compact, the agent received a session summary with `Optional Next Step: addressing routing brittleness...`. It treated this as an implementation directive and changed `craft_router.py` to use lens-first routing. The actual last user message was: **"what does skill-creator optimize?"** — a clarification question that was never answered.

## Root Cause: Summary Schema Promotes Discussion → Directive

Session summaries compress conversation state to optimize for **topic coverage** and **recoverability**. This model-level compression:

1. Promotes "things we were heading toward" into "things to do"
2. Flattens the distinction between *intent expressed* vs. *directive issued*
3. Embeds the summarizer's framing bias (code patterns → code-oriented context)

The post-compact agent has no access to the actual last user turn — only the summary's reconstruction of it.

## Optimal Solution: Explicit Last-Turn Anchoring

### 1. Hard-anchor the final user turn verbatim

```
## LAST USER MESSAGE (verbatim)
"what does skill-creator optimize?"

## SESSION STATE
- pending_question: true
- pending_implementation: false
```

When `pending_question: true` + verbatim message, the post-compact agent's first action is to answer, not implement.

### 2. Separate "discussed" from "decided"

```
## DECISIONS MADE (authorized by user)
- [nothing this session]

## DISCUSSED BUT NOT DECIDED
- Routing brittleness fix: using finding.lens as primary key
- Optional next step only — NOT a directive
```

### 3. Turn-type classifier at SessionStart

Simple heuristic: `?` in last message → likely question; imperative verb → directive. Gate actions accordingly.

## What Was Wrong in craft_router.py

The routing fix was **correct work** — lens-first routing does solve the keyword brittleness problem. But it should have been:
- Deferred until the user authorized it, OR
- Preceded by: *"Before I answer, I note there's an outstanding routing fix — should I implement it or answer the question first?"*

The failure was treating a summary's framing as user authorization.

## Related

- [[Claude Code Skill Failure Patterns]] — skill system failure modes
- [[Session Chain Export 0bd42a0c — yt-is code review]] — session chain and transcript analysis