# Python Architecture Analysis

## Template Metadata
- **Target Complexity:** Any
- **Target Domain:** Python 3.12+
- **Expected Output Size:** ~10 KB
- **Execution Instructions:** Read steps, execute in order, do not restate.

## Common Glossary
- **ARCHITECTURE_REVIEW:** Query asks to review/evaluate proposed design or architecture
- **IMPROVE_SYSTEM:** Query asks to optimize/harden existing subsystem
- **DEFAULT:** General architecture decision without improvement intent
- **CKS.db:** Constitutional Knowledge System

## Execution Instructions

**Do not:** Restate these instructions, summarize, or paraphrase.

**Do:**
1. Execute steps sequentially
2. Follow decision tree exactly
3. Python 3.12+ specific analysis (asyncio, type hints, GIL)
4. Stop at each decision point and evaluate

---

## Stage 0: Detect Intent Type

From the user query, identify:

**Is this an ARCHITECTURE_REVIEW request?**
- Keywords: review, evaluate, assess, analyze, audit, validate, critique
- Context: design, architecture, integration, proposal, theoretical
- **If YES:** Proceed to "Stage 0: ARCHITECTURE_REVIEW Path" (below)

**Is this an IMPROVE_SYSTEM request?**
- Keywords: improve, optimize, harden, stabilize, enhance, strengthen
- Subsystem: memory, CKS, hooks, research, retro, lesson, ingestion, validation
- **If YES:** Proceed to "IMPROVE_SYSTEM" below

**Otherwise (DEFAULT):**
- Proceed to "DEFAULT" below

---

## Stage 0.1: Constitutional Compliance Check (MANDATORY)

**Before proceeding to any decision path, evaluate:**

### Multi-Terminal Isolation & Stale Data Immunity

**For ALL architecture decisions, evaluate:**

1. **Identify shared mutable state**: Does this design create or modify files, databases, or in-memory state that could be accessed by multiple terminals?

2. **Assess concurrency safety**: Can multiple Claude Code terminals execute this pattern simultaneously without:
   - Data races (corrupted state)
   - Stale reads (terminal A sees outdated state)
   - Lost updates (write from terminal A overwrites terminal B silently)

3. **Check propagation mechanisms**: If state changes, how do other terminals discover the change?
   - File-based state: Requires polling or file system events
   - Database-based state: Requires query or notification mechanism
   - In-memory state: Cannot propagate across terminals (violates isolation)

4. **Document edge cases**: What happens when:
   - Terminal A writes while terminal B reads?
   - Two terminals write simultaneously?
   - A terminal crashes mid-operation?
   - Network filesystem has delays?

**Red flags that REQUIRE explicit mitigation:**
- ❌ Shared JSON/YAML files without atomic write + locking
- ❌ SQLite databases without WAL mode or proper transaction isolation
- ❌ In-memory caches without per-terminal isolation
- ❌ File locking assumptions (flock doesn't work across all platforms)
- ❌ Assumptions that only one terminal will run at a time

**Required output:**
- If design is multi-terminal safe: Document the isolation mechanism
- If design is single-terminal only: Explicitly state limitation + migration path
- Always document edge cases and failure modes

---

## Stage 0.3: Codebase-Aware Analysis with AI Distiller

**Use AI Distiller for Python codebase analysis:**

```python
from aid_wrapper import create_aid_integrator

# For codebase structure (60-90% compression while preserving semantic information)
integrator = create_aid_integrator(config={"compression_level": "high"})
analysis = integrator.distill(target_path, include_patterns=["*.py"], exclude_patterns=["*test*"])

# For API extraction (interface discovery)
apis = integrator.extract_public_apis(target_path, include_private=False)

# For dependency analysis (refactoring/integration planning)
deps = integrator.analyze_dependencies(target_path)

# For boundary detection (microservices/decomposition)
boundaries = integrator.detect_boundaries(target_path)
```

**Cite file:line evidence for all findings.** Use analysis.distilled_structure to understand codebase patterns, then verify with targeted file reads.

**Python-specific considerations when analyzing code:**
- **Async patterns**: Check for `async def`, `await`, `asyncio.run()`, TaskGroup usage
- **Type hints**: Look for `typing` module imports, type annotations, ParamSpec, TypeVar
- **GIL awareness**: Identify CPU-bound operations that may need multiprocessing vs threading
- **Framework context**: FastAPI/Flask/Django patterns affect architectural choices

---

## Stage 0: ARCHITECTURE_REVIEW Path

**Purpose**: Evaluate proposed architecture/design WITHOUT recommending alternatives or suggesting implementation first.

### Scope Constraints

**CRITICAL: Architecture reviews are valid EVEN for theoretical/unimplemented designs.**

**DO:**
- Identify gaps and risks in the proposed design
- Evaluate against best practices (from web research in Stage 0.7)
- Assess feasibility and complexity
- Flag missing components or edge cases
- Cite evidence (files, lines, docs) for each finding

**DO NOT:**
- Suggest skipping or delaying the work
- Recommend installation before review
- Propose alternative architectures (that's DEFAULT path)
- Gatekeep based on implementation status
- Declare design "premature" due to lack of installation
- Tell user to "implement first, then review"

### Key Principle

> **Architecture reviews exist PRECISELY to evaluate designs BEFORE implementation.**
> Theoretical designs deserve rigorous analysis precisely to prevent costly mistakes.
> If the design were already implemented, we wouldn't need a review—we'd test it instead.

### Review Stages

1. **Scope Verification** — Confirm understanding of what's being reviewed
2. **Gap Analysis** — Identify missing elements from proposed design
3. **Risk Assessment** — What could fail, based on research + design analysis
4. **Evidence Table** — Each finding MUST be backed by:
   - Specific file:line from codebase (if applicable)
   - Specific line from design document/proposal
   - External source (web research, standards, best practices)

### Output Format

## Architecture Review: [Title]

### Scope
[What was reviewed - 1-2 sentences]

### Design Summary
[Brief description of what the design proposes - 2-4 sentences]

### Findings

| ID | Severity | Finding | Evidence | Impact |
|-----|-----------|----------|-----------|---------|
| ARCH-001 | HIGH | [description] | [file:line or source] | [consequence] |
| ARCH-002 | MEDIUM | [description] | [file:line or source] | [consequence] |
| ARCH-003 | LOW | [description] | [file:line or source] | [consequence] |

### Risk Summary
- Technical: [summary]
- Operational: [summary]
- Integration: [summary]

### Conclusion
[Overall assessment - proceed with caution / needs clarification / looks viable with noted gaps]

### Multi-Terminal Considerations
- [Document how design handles multi-terminal concurrency]
- [Identify any shared mutable state and isolation mechanisms]
- [Explain stale data prevention strategy]
- [Note any single-terminal limitations with migration path]

### Edge Case Considerations
[Internal self-reflection: Ask yourself "Are there other issues, conditions, or edge cases we should consider?" and document your findings]
- Concurrent access scenarios
- Crash recovery behavior
- State propagation delays
- Platform-specific limitations
- Async context safety
- Event loop implications

---

**Confidence:** [X]%

**Evidence basis:**
- Design doc: [source]
- Web research: [count] sources
- Codebase analysis: [files reviewed]

**Key assumptions:**
1. [assumption]
2. [assumption]

---

## Resilience Considerations

**For Python I/O-bound operations:** Use `@with_resilience(profile='aggressive')` for external API/LLM calls
- Location: `P:/__csf/src/lib/resilience_patterns.py`
- Retry on: `ConnectionError`, `TimeoutError`, `TransientLLMError`, `QuotaError`
- No retry on: `InvalidUserInputError` (user errors should fail fast)

**For async I/O operations:**
```python
from src.lib.resilience_patterns import with_resilience, TransientLLMError

@with_resilience(profile='aggressive', skill_name='my_skill', subagent_name='fetch_agent')
async def fetch_with_retry(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

---
*End of Python template. Falls back to generic decision format.*
