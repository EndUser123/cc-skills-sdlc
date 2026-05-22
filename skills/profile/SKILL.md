# /profile - Performance Baseline & Comparison

## Overview

Measure and compare performance metrics to verify optimizations.

**Mandatory Protocol:** See `__lib/performance_standards.md` for the Benchmarking Protocol (Baseline vs Compare).

## Usage

```bash
/profile <target> --baseline     # Establish baseline
/profile <target> --compare      # Compare after changes
```

## Metrics

- Execution Time (Wall-clock)
- Import Time
- Memory Usage (Peak)
- Complexity (CC Score)

---

**Note**: `/profile` is for **Measuring Speed**; use `/perf` for **Finding Issues**.

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
