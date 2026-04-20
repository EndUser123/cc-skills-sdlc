# Quick Architecture Decision (fast.md)

> **Extends:** base.md (shared stages)
> **Configuration:** MAX_FILES=3, COMPRESSION_LEVEL=moderate, SEARCH_COUNT=1-2, OUTPUT_SIZE_GUIDANCE=~5 KB

## Template Metadata
- **Target Complexity:** LOW
- **Target Domain:** Generic
- **Expected Output Size:** ~5 KB
- **Execution Instructions:** Read base.md stages, apply fast-specific config

---

## Fast-Template Configuration

**Override these base.md variables:**

| Variable | Value |
|----------|-------|
| `{MAX_FILES}` | 3 files maximum for codebase analysis |
| `{COMPRESSION_LEVEL}` | moderate (50% compression) |
| `{SEARCH_COUNT}` | 1-2 web searches (targeted depth) |
| `{OUTPUT_SIZE_GUIDANCE}` | ~5 KB output (keep it tight) |
| `{TEMPLATE_TYPE}` | "fast" (for output filename) |

---

### Verbalized Sampling Configuration (Fast Template)

**For quick decisions, fast template uses lighter VS constraints:**

- **K = 3 candidates** (vs 4 in deep) for rapid assessment
- **No tail requirement** (all options should be reasonably viable)
- **Probability banding**: At least 2 options with probability ≥ 0.3
- **Lens coverage**: Candidates should span at least 2 distinct primary lenses
- **Keep it simple**: Focus on the most relevant lenses for the query context

**Fast template VS output includes:**
- Probability estimates for each option
- Primary lens tags
- Key tradeoffs (favors X, sacrifices Y)

---

## Template-Specific Guidance

**Fast template is for:**
- Quick decisions on single files or small modules
- Simple architectural choices with clear options
- Rapid assessment without deep analysis

**Keep output focused:**
- One decision statement paragraph
- 2-3 real options (no fake alternatives)
- Before/after code or pseudocode
- One-line confidence with evidence

**Skip detailed analysis when:**
- Query is straightforward (single file, clear scope)
- User asks for quick opinion
- Best practices are well-established

### Verbalized Sampling Configuration (Fast Template)

**For quick decisions, fast template uses lighter VS constraints:**

- **K = 3 candidates** (vs 4 in deep) for rapid assessment
- **No tail requirement** (all options should be reasonably viable)
- **Probability banding**: At least 2 options with probability ≥ 0.3
- **Lens coverage**: Candidates should span at least 2 distinct primary lenses
- **Keep it simple**: Focus on the most relevant lenses for the query context

**Fast template VS output includes:**
- Probability estimates for each option
- Primary lens tags
- Key tradeoffs (favors X, sacrifices Y)

---

## Include base.md stages

Execute all stages from **base.md** with the above configuration:

1. **Stage 0:** Detect Intent Type
2. **Stage 0.1:** Constitutional Compliance Check
3. **Stage 0.2:** Pre-Stage Discovery Hint
4. **Stage 0.3:** Codebase-Aware Analysis (max 3 files)
5. **Stage 0.6:** Domain Resource Inclusion
6. **Stage 0.7:** Web Research (1-2 searches)
7. **Stage 0.8:** Verbalized Sampling Option Generation (K=3, no tail requirement)
8. **Decision Path:** ARCHITECTURE_REVIEW / IMPROVE_SYSTEM / DEFAULT

---

## Success Criteria

✅ Output under 5 KB
✅ No fake alternatives (quality gate enforced)
✅ Clear before/after comparison
✅ Confidence score with evidence basis
✅ Ready to implement now

---
*End of fast.md template. Extends base.md with fast-specific configuration.*
