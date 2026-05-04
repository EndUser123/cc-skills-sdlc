# Performance and Optimization Standards

## 1. Algorithmic Complexity (Static)
- **Iron Law**: Avoid O(n²) or worse in performance-critical paths (handlers, loops).
- **Checklist**:
  - Array operations (`push`, `spread`) inside loops.
  - Repeated function calls for static values.
  - Synchronous blocking I/O in async functions.
  - Memory leak risks (global state accumulation).

## 2. Anti-Pattern Detection (Dynamic)
- **Nested Pools**: Avoid creating `ThreadPoolExecutor` or `ProcessPoolExecutor` inside worker threads.
- **Resource Creation**: Create shared resources (sessions, DB connections) BEFORE entering parallel loops.
- **Worker/CPU Ratio**: Warn if worker count exceeds `CPU_CORES * 2`.

## 3. Benchmarking Protocol
- **Baseline**: Record wall-clock time, import time, and memory usage BEFORE changes.
- **Compare**: Measure same metrics AFTER optimization.
- **Verification**: Optimization is only valid if it shows a statistically significant delta without regressing reliability.

## 4. AID Integration
Use AI Distiller (AID) for deep performance audit:
```bash
aid <path> --ai-action prompt-for-performance-analysis
```
Focuses on N+1 queries, complexity bottlenecks, and scalability gaps.
