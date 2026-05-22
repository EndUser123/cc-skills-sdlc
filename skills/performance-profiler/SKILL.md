# Performance Profiler

## Overview

Analyze code for performance bottlenecks and optimization opportunities.

**Mandatory Protocol:** See `__lib/performance_standards.md` for Algorithmic Complexity rules (O(n²) check) and the Optimization Checklist.

## Features

- Loop performance analysis.
- Duplicate calculation detection.
- Synchronous blocking identification.

---

**Note**: For dynamic tracing, use `/perf`. For speed measurement, use `/profile`.

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
