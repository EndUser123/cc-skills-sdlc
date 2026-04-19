---
name: profile
version: 1.0.0
description: Performance baseline and comparison tool for modernization workflows.
category: utilities
status: stable
triggers:
  - /profile
aliases:
  - /profile

suggest:
  - /evolve
  - /perf
  - /complexity
---

# /profile - Performance Baseline & Comparison

## Purpose

Measure and compare performance metrics for code modernization workflows. Provides baseline measurements and before/after comparisons to verify optimizations don't regress performance.

**This is NOT `/perf`** - See "Distinction from /perf" below.

## Project Context

### Constitution / Constraints
- Solo-dev constraints apply (CLAUDE.md)
- No enterprise monitoring infrastructure
- Simple, direct measurements preferred
- Graceful degradation on measurement failures

### Technical Context
- Baseline mode: Record resource usage and timing for "before" state
- Compare mode: Compare current metrics against previously recorded baseline
- Integration: Used by `/evolve` workflow in Phase 1 (AUDIT) and Phase 4 (HARDEN)
- Storage: Baseline data stored in `P:/.claude/state/profile_baselines.json`

### Architecture Alignment
- Complements `/perf` (anti-pattern detection)
- Integrates with `/evolve` modernization workflow
- Provides L3 metrics (resource usage, timing) for verification

## Distinction from /perf

**These are DIFFERENT tools for DIFFERENT purposes:**

| Aspect | `/profile` (this skill) | `/perf` (existing) |
|--------|------------------------|-------------------|
| **Purpose** | Performance measurement | Anti-pattern detection |
| **Use Case** | Baseline & comparison | Find code issues |
| **Flags** | `--baseline`, `--compare` | (runs on command) |
| **Output** | Timing metrics, resource usage | Pattern analysis report |
| **Example** | "How fast is this function?" | "Are there nested ThreadPoolExecutors?" |

**When to use which:**
- Use `/profile` when you need to measure "how fast" or compare before/after
- Use `/perf` when you need to detect anti-patterns like nested thread pools

## Your Workflow

### Baseline Mode (Before Modernization)

1. **Parse target** - Identify file/directory to profile
2. **Run measurements** - Execute code with timing instrumentation
3. **Store baseline** - Save metrics to `profile_baselines.json`
4. **Report results** - Show timing, memory usage, complexity metrics

### Compare Mode (After Modernization)

1. **Load baseline** - Read previously saved baseline from JSON
2. **Run measurements** - Execute current code with same instrumentation
3. **Compare metrics** - Calculate delta (before vs after)
4. **Report findings** - Show improvements or regressions

## Usage

```bash
# Establish performance baseline
/profile <target> --baseline

# Compare against baseline
/profile <target> --compare

# Example: Profile a Python module
/profile P:/.claude/hooks/UserPromptSubmit_modules/registry.py --baseline

# Example: Compare after refactoring
/profile P:/.claude/hooks/UserPromptSubmit_modules/registry.py --compare
```

## Metrics Measured

- **Execution Time**: Wall-clock time for main functions
- **Complexity**: Cyclomatic complexity (CC) scores
- **Lines of Code**: SLOC metrics
- **Import Time**: Time to import module
- **Memory Usage**: Peak memory during execution (if available)

## Output Format

### Baseline Mode

```markdown
## Performance Baseline: registry.py

**Timestamp**: 2026-03-15T01:30:00Z
**Target**: UserPromptSubmit_modules/registry.py

**Metrics**:
- Execution Time: 145ms
- Import Time: 23ms
- Complexity: CC 16 (run_hooks), CC 13 (_log_execution_trace)
- Lines of Code: 625

**Baseline saved to**: P:/.claude/state/profile_baselines.json
```

### Compare Mode

```markdown
## Performance Comparison: registry.py

**Baseline**: 2026-03-15T01:30:00Z
**Current**: 2026-03-15T01:45:00Z

**Delta**:
- Execution Time: 145ms → 138ms ✅ (-4.8%)
- Import Time: 23ms → 21ms ✅ (-8.7%)
- Complexity: CC 16 → CC 12 ✅ (-25%)
- Lines of Code: 625 → 610 ✅ (-2.4%)

**Result**: IMPROVEMENT - All metrics improved
```

## Error Handling

- **Missing baseline**: If `--compare` used but no baseline exists, fall back to `--baseline`
- **Target not found**: Warn and suggest valid targets
- **Measurement failures**: Graceful degradation, report what succeeded
- **File access errors**: Create state directory if missing

## Implementation Notes

- Use `time.perf_counter()` for high-resolution timing
- Use `radon` for complexity analysis (already in project)
- Store baselines as JSON with timestamp for versioning
- Support multiple baselines per target (timestamped entries)

## Files

- `SKILL.md` - This file
- `__main__.py` - Entry point with CLI argument parsing
- `lib/profiler.py` - Core profiling logic
- `lib/baseline.py` - Baseline storage and retrieval
- `lib/reporter.py` - Report generation
- `tests/test_profile.py` - Unit tests

## Success Criteria

- ✅ Baseline mode saves metrics to JSON
- ✅ Compare mode calculates deltas correctly
- ✅ Graceful degradation on errors
- ✅ Clear distinction from /perf documented
- ✅ Integrates with /evolve workflow

## Version History

- **v1.0.0** (2026-03-15): Initial release
  - Baseline and compare modes
  - JSON storage for baselines
  - Integration with /evolve workflow
  - Distinction from /perf documented
