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
