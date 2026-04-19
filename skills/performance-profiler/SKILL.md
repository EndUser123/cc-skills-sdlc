---
name: performance-profiler
description: Analyze code performance, identify bottlenecks, and provide optimization recommendations. Detects loop performance issues, repeated calculations, synchronous blocking, complexity problems, and memory leak risks.
version: 1.0.0
status: stable
category: analysis
---

# Performance Profiler

Analyzes code performance to identify bottlenecks and suggest optimizations.

## Features

- Loop performance analysis
- Duplicate calculation detection
- Synchronous blocking identification
- Complexity computation
- Optimization recommendation generation

## Trigger Words

- "performance analysis"
- "performance bottleneck"
- "optimize performance"
- "profiling"

## Detected Issues

- Array operations inside loops
- Repeated function calls
- Synchronous blocking operations
- Memory leak risks

## Output Example

```json
{
  "issues": [
    {
      "type": "loop_push",
      "location": "line 42",
      "suggestion": "Use array comprehension or pre-allocate"
    }
  ],
  "complexity": "O(n²)",
  "score": 75
}
```
