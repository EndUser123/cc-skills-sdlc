# Requesting Code Review

## Overview

Offload code evaluation to a specialized reviewer subagent to preserve context and catch issues early.

**Mandatory Protocol:** See `__lib/review_management.md` for When to Request, Git SHA identification, and Context Provisioning rules.

## Quick Start

1. **Identify SHAs**: `git rev-parse HEAD~1` (Base) vs `git rev-parse HEAD` (Head).
2. **Dispatch Reviewer**:
   - Agent Type: `code-reviewer`
   - Inputs: Plan, Requirements, Implementation Summary.

## Integration

- **Subagent-Driven**: Mandatory review after EACH task.
- **Executing Plans**: Review after every 3 tasks (batch).
- **Ad-Hoc**: Review before merge to `main`.

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
