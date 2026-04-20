# Comprehensive Architecture Review (deep.md)

> **Extends:** base.md (shared stages)
> **Configuration:** MAX_FILES=5, COMPRESSION_LEVEL=high, SEARCH_COUNT=3-5, OUTPUT_SIZE_GUIDANCE=~15-30 KB

## Template Metadata
- **Target Complexity:** HIGH
- **Target Domain:** Generic
- **Expected Output Size:** ~15-30 KB
- **Execution Instructions:** Read base.md stages, apply deep-specific config

---

## Deep-Template Configuration

**Override these base.md variables:**

| Variable | Value |
|----------|-------|
| `{MAX_FILES}` | 5 files maximum for codebase analysis |
| `{COMPRESSION_LEVEL}` | high (70% compression) |
| `{SEARCH_COUNT}` | 3-5 web searches (comprehensive depth) |
| `{OUTPUT_SIZE_GUIDANCE}` | ~15-30 KB output (comprehensive analysis) |
| `{TEMPLATE_TYPE}` | "deep" (for output filename) |

---

### Verbalized Sampling Configuration (Deep Template)

**For complex decisions, deep template enforces stronger VS constraints:**

- **K = 4 candidates** (vs 3 in fast) for more comprehensive exploration
- **Tail exploration mandatory**: At least 1 option with probability ≤ 0.25
- **Probability banding**: Distribute candidates across bands:
  - 1 option in [0.5, 0.8] (high-confidence mainstream)
  - 1 option in [0.3, 0.5] (moderate confidence)
  - 1-2 options in [0.05, 0.3] (tail exploration)
- **Minimum Jaccard distance**: 0.4 between any two options (structural diversity)
- **Lens coverage**: Candidates should span at least 3 distinct primary lenses
- **Include tail option**: At least one candidate must explore unconventional or high-risk/high-reward approaches

**Deep template VS output includes:**
- Probability estimates for each option
- Primary lens tags
- Key tradeoffs (favors X, sacrifices Y)
- Structural changes (components modified, dependencies added/removed)

---

## Template-Specific Additions

**Deep template includes additional analysis beyond fast.md:**

### Additional Web Searches (3-5 total)
3. **Failure modes** — What typically goes wrong with this pattern at scale?
4. **Alternatives** — What are the main alternatives used in production?
5. **Security advisories** — Any security considerations for the patterns involved?

### Enhanced Codebase Analysis
- Read up to 5 key files (vs 3 in fast)
- Use high compression for large codebases
- Boundary detection for decomposition decisions
- Dependency analysis for integration planning

### Structured Analysis (Optional for Complex Reviews)

For multi-system or complex integration reviews, use graph-based reasoning:

```
Step 1: Generate Architecture Nodes
- Node A: "Federated query architecture"
- Node B: "Checkpoint integration"
- Node C: "claude-mem integration"

Step 2: Generate Edge Relationships
- A → B: "A depends on B for query federation"
- A → C: "A shares state with C via session handoff"

Step 3: Aggregate Findings
- Merge related concerns into synthesis nodes
- Identify cross-cutting risks

Step 4: Refine Output
- Converge graph-based analysis into final review format
- Preserve traceability of reasoning path
```

**Note:** This GoT-style approach is optional. Use for complex multi-system reviews when simple linear analysis is insufficient.

### Graph-of-Thought (GoT) Integration

**Deep template includes automatic GoT node extraction and edge analysis:**

When analyzing architecture alternatives:
- Extract nodes: constraints, ideas, risks, components, data flows
- Analyze edges: supports, contradicts, depends, unrelated
- Detect cycles: circular dependencies that could cause deadlock
- Document findings in "GoT Analysis" section

**Example:**
```markdown
### GoT Analysis

**Extracted Nodes:**
- Constraints: ["Must use JWT", "Response time < 200ms"]
- Ideas: ["Use Redis for caching", "Implement OAuth 2.0"]
- Risks: ["Secret management critical", "OAuth latency"]
- Components: ["API Gateway", "Auth Service"]

**Edge Relationships:**
- "Use Redis" supports "Token caching"
- "Must use JWT" contradicts "Shared session store"

**Cycles Detected:** None

**Architectural Insights:**
- Contradiction: JWT vs session store needs resolution
```

### Lean System Design Integration

**Deep template applies Lean System Design principles:**

- **Value Optimization**: Each component must advance core goals
- **Merge Duplicate Mechanisms**: Compare against existing patterns
- **Ruthless Dependency Pruning**: MUST/SHOULD/MAY classification
- **Contract-First Design**: Define schemas/APIs before implementation

**Add these sections to output:**
- "Core Contracts" - API signatures and data models
- "Dependency Audit" - What's actually needed vs nice-to-have
- "Environment & Preference Fit" - Solo-dev friendly patterns

---

## Include base.md stages

Execute all stages from **base.md** with the above configuration:

1. **Stage 0:** Detect Intent Type
2. **Stage 0.1:** Constitutional Compliance Check
3. **Stage 0.2:** Pre-Stage Discovery Hint
4. **Stage 0.3:** Codebase-Aware Analysis (max 5 files, with GoT/Lean analysis)
5. **Stage 0.6:** Domain Resource Inclusion
6. **Stage 0.7:** Web Research (3-5 searches with failure modes/alternatives/security)
7. **Stage 0.8:** Verbalized Sampling Option Generation (K=4, tail exploration mandatory)
8. **Decision Path:** ARCHITECTURE_REVIEW / IMPROVE_SYSTEM / DEFAULT

---

## Success Criteria

✅ Comprehensive coverage of systems thinking
✅ Trade-offs analyzed with risk assessment
✅ Multiple alternatives considered (quality gate enforced)
✅ Evidence table with file:line citations
✅ GoT analysis for complex reviews (optional)
✅ Lean design principles applied
✅ Ready for implementation or validation

---
*End of deep.md template. Extends base.md with deep-specific additions.*
