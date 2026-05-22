# /perf - Performance Tracing Wrapper

## Overview

Detect performance anti-patterns (nested pools, resource waste) in running Python code.

**Mandatory Protocol:** See `__lib/performance_standards.md` for Anti-Pattern Detection rules and Worker/CPU ratios.

## Usage

```bash
/perf python my_script.py        # Trace script execution
/perf pytest tests/              # Trace test runs
```

## AID Audit

```bash
aid <path> --ai-action prompt-for-performance-analysis
```

---

**Note**: `/perf` is for **Finding Issues**; use `/profile` for **Measuring Speed**.

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
