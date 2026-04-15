# Cognitive Stack & Tree-of-Thought (ToT) Integration

## Cognitive Stack Integration (v2.4)

**Auto-select appropriate thinking modes from cognitive stack based on problem characteristics.**

### Problem Type Auto-Detection

| Problem Type | Triggers | Primary Thinking Modes |
|--------------|----------|-------------------------|
| **ERROR** | Runtime exceptions, AttributeError, ImportError | Five Whys, Linear Thinking |
| **PERFORMANCE** | Slow, timeout, latency | Systems Thinking, First Principles |
| **CRASH** | Segfault, abort, traceback | Five Whys, Scientific Method |
| **SECURITY** | Auth, vulnerability, injection | Risk Assessment, Tree Thinking |
| **INTEGRATION** | Cross-component, API, interface | Systems Thinking, Collaborative Reasoning |
| **INTERMITTENT** | Flaky, sometimes, race condition | Systems Thinking, Scientific Method |
| **NEW/NOVEL** | Never seen, first time, unusual | First Principles, Tree Thinking |

### Mental Model Selection in Output

Include in RCA output:

| Model | Rationale | Confidence Boost |
|-------|-----------|------------------|
| Systems Thinking | Performance issue with cross-component interactions | +15% |
| Scientific Method | Multiple plausible causes require hypothesis testing | +10% |

**Overall confidence boost from cognitive enhancement:** +30%

---

## Tree-of-Thought (ToT) Integration (v2.7)

### 1. ToT Branching Hypothesis Generation

**What**: Automatically generate branching hypotheses based on causal reasoning paths
**When**: Automatic enhancement during Step 1.75 (hypothesis generation)
**Benefit**: Discover alternative causal paths beyond manual hypothesis generation

**Hypothesis Branch Types Detected**:
- **Direct causation**: Symptom X directly causes problem Y
- **Contributing factors**: Multiple factors combine to cause issue
- **Root cause chains**: A -> B -> C causal chains
- **Interaction hypotheses**: Component interactions cause unexpected behavior
- **Environment hypotheses**: External factors (timing, state, configuration) contribute

**Branch Scoring**:
- **sure**: High-confidence causal paths (e.g., direct correlation with evidence)
- **maybe**: Medium-confidence causal paths (e.g., plausible mechanism without direct evidence)
- **unlikely**: Low-confidence causal paths (e.g., speculative or requires assumptions)

**Opt-out Flag**:
```bash
# Disable ToT enhancement
export DEBUGRCA_NO_TOT=true

# Or programmatically in investigation
```

### 2. Integration with Hypothesis Scoring System

ToT branches integrate with the existing scoring formula:
- **Reproducibility** (0.3): Branch confidence (sure=1.0, maybe=0.5, unlikely=0.1)
- **Recency** (0.2): Code change timeline matches branch hypothesis
- **Impact** (0.5): How well branch explains all symptoms

**Scoring Formula with ToT**:
```
Hypothesis Score = Reproducibility(0.3) x Recency(0.2) x Impact(0.5)
```

**Branch Pruning**:
- `sure` branches: Primary investigation (score >= 0.7)
- `maybe` branches: Secondary investigation (score >= 0.4)
- `unlikely` branches: Pruned (score < 0.4) unless evidence emerges

### 3. Multi-Angle Hypothesis Generation

ToT enhancement generates hypotheses from multiple causal angles:

**Mechanism-based hypotheses**: Generated from code inspection
- "Function X at line Y has race condition"
- "Missing error handling in API call"

**Functional hypotheses**: Generated from visible symptoms
- "Symptom S indicates component C failure"
- "Observable O suggests configuration issue"

**Temporal hypotheses**: Generated from recent changes
- "Git commit C introduced breaking change"
- "Recent refactoring broke integration"

**Interaction hypotheses**: Generated from component relationships
- "Component A interaction with B causes unexpected state"
- "Library L version incompatible with framework F"

### 4. ToT Workflow Integration

**During Step 1.75 (Hypothesis Generation)**:

1. **Generate ToT branches** using BranchGenerator
   - Analyze multi-angle search results
   - Extract causal relationships
   - Generate 2-3 branches per finding

2. **Score each branch**
   - Apply reproducibility x recency x impact formula
   - Tag branches as sure/maybe/unlikely

3. **Prune unlikely branches**
   - Remove branches with score < 0.4
   - Focus investigation on high-value paths

4. **Document in hypothesis table**
   - Include ToT branches with manual hypotheses
   - Mark ToT-generated hypotheses for traceability

**Example Enhanced Hypothesis Table**:

| # | Hypothesis | Type | Repro | Recency | Impact | Score | Status |
|---|------------|------|-------|---------|--------|-------|--------|
| 1 | Manual stdout writes missing rate limit | Manual | 1.0 | 0.5 | 1.0 | 0.85 | TESTING |
| 2 | Rich Progress refresh too high | Manual | 1.0 | 0.5 | 0.5 | 0.65 | Eliminated |
| 3 | ToT: Progress + stdout compound issue | ToT (sure) | 0.8 | 0.5 | 0.7 | 0.68 | Pending |
| 4 | ToT: Event loop interaction | ToT (maybe) | 0.5 | 0.3 | 0.4 | 0.35 | Pruned |

**Integration Notes**:
- ToT enhancement is **enabled by default** (quality-first design)
- Use `--no-tot` flag to disable for simple issues
- ToT findings complement manual hypothesis generation
- For straightforward bugs (< 2 possible causes), ToT may be skipped with explicit note
