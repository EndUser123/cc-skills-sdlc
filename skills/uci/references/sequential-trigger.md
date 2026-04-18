# Intelligent Sequential Trigger

**Purpose**: Conditionally trigger sequential agent execution when justified by code characteristics, avoiding blanket "always parallel" or "always sequential" decisions.

**Problem Solved**: Sequential execution provides better detection for some bug categories (state-transition bugs, TOCTOU, coupled defects) but has 600% performance overhead. The trigger decides when this overhead is justified.

## Quality-First Mode (DEFAULT)

Triggers sequential whenever it improves detection quality, regardless of performance overhead. The 600% overhead is acceptable when it means catching more bugs.

## Two-Phase Evaluation

### Phase 1: Before Agents Run (Codebase Characteristics)

- **State-machine heavy**: 1+ state-related patterns (state assignment, transitions, async primitives)
- **Concurrency heavy**: 1+ concurrency patterns (async/await, threading, multiprocessing)
- **Security-critical**: 2+ security patterns OR security-related file paths
- **Complex control flow**: 1+ nested control structures (nested loops/conditionals, multiple exception handlers)

### Phase 2: After First Wave (Early Finding Patterns)

- **High finding density**: 3+ findings in first wave
- **Critical severity cluster**: 2+ critical/blocker findings
- **Coupled bug types**: 3+ findings in same file location

## Quality-First Triggering (DEFAULT MODE)

| Condition | Trigger Sequential | Expected Improvement |
|-----------|-------------------|---------------------|
| ANY condition suggests improved quality | Yes | Medium/High (75-90% confidence) |
| Critical severity cluster | Yes | High (90% confidence) |
| Coupled bugs OR Security-critical | Yes | High (85% confidence) |
| High density OR State-heavy OR Concurrency | Yes | Medium (75% confidence) |
| No early findings | No | None (sequential won't help) |
| Simple code, no characteristics | No | Low (nothing to improve) |

## Performance Baseline

(Phase 0.75 findings)
- Parallel execution: ~30 seconds (4 agents in parallel)
- Sequential execution: ~180 seconds (4 agents in series)
- Overhead: 600% (5x slower)
- **Quality-First Decision**: Sequential when ANY condition suggests better detection quality (600% overhead is acceptable for catching more bugs)

## Cost-Constrained Mode (Optional)

Set `quality_first=False` to use cost-constrained triggering where sequential only triggers when multiple conditions together justify the 600% overhead.

## Implementation

`lib/sequential_trigger.py` -- SequentialTrigger class with pattern detection, early finding analysis, and confidence-based decision making.
