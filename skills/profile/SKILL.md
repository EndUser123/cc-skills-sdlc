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
