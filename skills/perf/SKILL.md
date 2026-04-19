---
name: perf
description: Performance tracing wrapper for Python - detects anti-patterns like nested ThreadPoolExecutors.
version: 1.0.0
status: stable
category: utilities
triggers:
  - /perf
aliases:
  - /perf

suggest:
  - /bug-hunt
  - /analyze
  - /r
---

# /perf - Performance Tracing Wrapper

Run Python commands with performance anti-pattern tracing enabled.

## AID Integration (v1.1.0)

**Enhanced performance analysis via AI Distiller (AID):**

```bash
# Analyze codebase for performance bottlenecks
aid <path> --ai-action prompt-for-performance-analysis
```

**AID `prompt-for-performance-analysis` provides:**
- **Algorithmic Complexity**: O(n²) → O(n log n) optimization opportunities
- **N+1 Detection**: Database/API query batching opportunities
- **Async Anti-patterns**: Blocking I/O in async functions
- **Profiling Guidance**: What to profile and where
- **Scalability Analysis**: Bottlenecks under load

**When to use AID for performance:**
- Pre-deployment performance audits
- Scaling analysis before traffic increases
- Legacy code performance modernization
- CI/CD performance regression checks

**Integration**: Run AID analysis before `/perf` tracing to identify target areas.

---

## Purpose

Detect performance anti-patterns in Python code execution (nested ThreadPoolExecutors, resource waste).

**⚠️ NOT THE SAME AS /profile**: This skill (`/perf`) detects anti-patterns in running code. The missing `/profile` command (referenced in `/evolve` workflow) should provide performance baselines and comparisons (`--baseline`, `--compare` flags). These are **different tools** for different purposes:
- `/perf` - Anti-pattern detection (what's wrong?)
- `/profile` - Performance measurement (how fast? baseline vs comparison)

## Project Context

### Constitution/Constraints
- Evidence-first: Report actual detected patterns, not speculation
- Fail fast: Surface performance issues immediately

### Technical Context
- Traces ThreadPoolExecutor and ProcessPoolExecutor usage
- Configurable thresholds via set_threshold()
- Disable with PERF_TRACE=0 environment variable

### Architecture Alignment
- Supports /analyze for performance profiling
- Integrates with /bug-hunt for pattern detection

## Your Workflow

1. Wrap Python command with /perf prefix
2. Execute with tracing enabled
3. Detect anti-patterns during execution
4. Display report at exit with recommendations

## Validation Rules

- MUST show actual detected patterns, not theoretical issues
- MUST include specific line numbers and recommendations
- DO NOT suppress warnings without explicit disable flag

## Usage

```bash
# Trace Python scripts
/perf python my_script.py --arg value

# Trace pytest runs
/perf pytest tests/test_parallel.py

# Trace Python modules
/perf python -m mymodule
```

## Auto-Detects

- Nested ThreadPoolExecutors
- ProcessPoolExecutor nesting (expensive IPC overhead)
- Per-worker resource creation patterns
- Thread count vs CPU cores (warns if workers > cores*2)
- Threshold-based alerts (configurable)

**Shows report at exit** with automatic pattern analysis and recommendations.

Note: The perf_tracer module with configurable thresholds is not currently implemented. Basic command timing is available via the `/perf` command.

## Disable Tracing

Set `PERF_TRACE=0` to disable:
```bash
PERF_TRACE=0 /perf python my_script.py
```

## Output Examples

### Wasteful 1:1 Pattern
```
🔍 Performance Anti-Pattern Report
=====================================
📊 ThreadPoolExecutor:
   Instances created: 4
   Max nesting depth: 2
   Max workers: 4
   └─ Inner TPEs per outer worker: 1.0:1 (4 inner / 4 workers)

   ⚠️  WASTEFUL NESTING DETECTED [HIGH]
   └─ Each of 4 outer workers creates ~1 inner TPE.
      💡 Recommended actions:
      • Create shared resource BEFORE the outer ThreadPoolExecutor
      • Pass shared instance to workers via closure or argument
```
