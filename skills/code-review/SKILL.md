---
name: code-review
description: Automate comprehensive code review workflows using parallel specialist agents. Dispatches security, logic, performance, and quality subagents to analyze code and synthesize actionable findings.
version: "1.0.0"
category: analysis
status: stable
triggers:
  - /review
  - "review code"
  - "review my code"
enforcement: advisory
parallel_agents: true
depends_on_skills: []
---

# Code Review — Automated Multi-Agent Review

A skill that automates code review by dispatching specialist agents in parallel and synthesizing their findings into actionable recommendations.

**Mandatory Protocol:** See `__lib/adversarial_review_protocol.md` for the Critic persona and perspective-based review rules.

## Review Workflow

1. **Capture Target**: Resolve path, directory, or glob.
2. **Initialize Session**: Create per-run directory in `.claude/.evidence/code-review/`.
3. **Launch Specialists**: Dispatch parallel agents challenging:
   - Security & I/O
   - Logic & Concurrency
   - Performance & Scaling
4. **Synthesize**: Combine findings into a final report with Health Score.

## Health Score Calculation

`100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`, capped at 0-100.

## Specialist Agent Reference

| Agent | Focus | Applies To |
|-------|-------|------------|
| `adversarial-security` | Auth, injection, data exposure | All code |
| `adversarial-logic` | Conditionals, operators, flow | All code |
| `adversarial-performance` | Loops, DB, N+1, hot paths | All code |
| `adversarial-quality` | Tech debt, maintainability | All code |

See `__lib/adversarial_review_protocol.md` for detailed findings format and severity definitions.
