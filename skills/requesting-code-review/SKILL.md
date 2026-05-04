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
