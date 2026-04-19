# GoT Integration Reference

## Graph-of-Thought Architecture for `/arch`

### Overview

GoT enhancement is **enabled by default** for `/arch` execution. It extracts architecture nodes from the analysis, analyzes edge relationships between nodes, detects circular dependencies, and provides multi-alternative comparison.

**Opt-out**: `export ARCH_NO_GOT=true` or `--no-got` flag.

---

## Node Types

| Node Type | Description | Example |
|-----------|-------------|---------|
| `DECISION` | An architectural choice being evaluated | "Use SQLite vs PostgreSQL for state storage" |
| `CONSTRAINT` | A limiting factor on the design space | "Must work on Windows 11 without admin" |
| `DEPENDENCY` | A required component, library, or service | "Requires `sqlite-utils` package" |
| `RISK` | A potential failure mode or threat | "Race condition if two terminals write simultaneously" |
| `TRADEOFF` | A quality tradeoff explicitly acknowledged | "Faster writes but harder deduplication" |

---

## Edge Types

| Edge Type | Semantics | Effect |
|-----------|-----------|--------|
| `SUPPORTS` | One node strengthens or enables another | Increases confidence in supported node |
| `CONTRADICTS` | One node weakens or conflicts with another | Decreases confidence; flags tension |
| `DEPENDS` | One node requires another to be true | Creates ordering constraint |
| `MITIGATES` | A risk reduction relationship | Reduces risk probability or impact |

---

## Controller Operations

| Operation | Description |
|-----------|-------------|
| `EXTRACT` | Parse the architecture analysis text and identify nodes |
| `CONNECT` | Analyze relationships between nodes and add edges |
| `SCORE` | Evaluate each node on feasibility, completeness, novelty, risk |
| `PRUNE` | Remove nodes that are dominated by alternatives |
| `EXPLORE` | Generate new candidate nodes to fill gaps in the graph |
| `COMPARE` | Produce a multi-alternative comparison from the graph |

---

## Scoring Dimensions

| Dimension | Scale | Description |
|-----------|-------|-------------|
| Feasibility | 0-1 | Can this be implemented with current constraints? |
| Completeness | 0-1 | Does this address all aspects of the problem? |
| Novelty | 0-1 | Is this meaningfully different from standard approaches? |
| Risk | 0-1 | What is the failure probability and impact? (1 = highest risk) |

---

## Circular Dependency Detection

When the graph contains cycles in the `DEPENDS` edge subgraph:

1. **Identify the cycle**: List all nodes involved in the circular dependency
2. **Assess severity**: 
   - **Direct cycle**: A → B → A (critical — impossible to implement)
   - **Indirect cycle**: A → B → C → A (warning — requires careful ordering)
3. **Recommendation**: Break the cycle by removing the weakest `DEPENDS` edge

---

## Multi-Alternative Comparison

After scoring, produce a comparison table:

| Option | Feasibility | Completeness | Novelty | Risk | Net Score | Favored Lens |
|--------|-------------|--------------|---------|------|-----------|--------------|
| A | 0.9 | 0.7 | 0.3 | 0.2 | 0.70 | Reliability |
| B | 0.7 | 0.9 | 0.6 | 0.4 | 0.65 | Maintainability |
| C | 0.5 | 0.5 | 0.9 | 0.7 | 0.30 | Portability |

Net Score = (Feasibility + Completeness + Novelty - Risk) / 3

---

## Integration with Verbalized Sampling

GoT scoring feeds into the Verbalized Sampling (VS) candidate selection:

- **K candidates**: Number of options to present (3 for fast, 4 for deep)
- **Probability banding**: Derived from GoT net scores
- **Tail exploration**: Lowest-scored candidates that offer novel approaches
- **Jaccard distance**: Structural diversity between options
