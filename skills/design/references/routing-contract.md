# Routing Contract Reference

## Input-to-Template Routing Flow

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  Stage 0: Pre-Flight Checks     │
│  - Preset expansion             │
│  - Self-verification check      │
│  - Out-of-scope detection       │
│  → Redirect or proceed          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 0.5: Clarity Gate        │
│  - Context inference (Step 1)   │
│  - Clarification (Step 2, only  │
│    when context exhausted)      │
│  → Proceed or ask 1 question    │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1: Classify Intent       │
│  - Template override?           │
│  - ADF delegation?              │
│  - Intent type (review/improve  │
│    /default)                    │
│  - Domain detection             │
│  - Complexity detection         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1.4: Contract Sensitivity│
│  - Mark contract-sensitive if   │
│    touching boundaries          │
│  - Default: NOT sensitive       │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1.5: Boundary Inventory  │
│  (if contract-sensitive)        │
│  - List all producer/consumer   │
│    boundaries                   │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1.6: Boundary Closure    │
│  (if contract-sensitive)        │
│  - Close each boundary with     │
│    explicit field values        │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1.7: Emit Packets        │
│  - Contract Authority Packet    │
│  - Planning Handoff Packet      │
│    (if feeding /planning)       │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1.8: Consistency Check   │
│  - Safety policy gate           │
│  - Router precision gate        │
│  - Packet-to-summary            │
│    consistency                  │
│  - Validator alignment          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  Execute Template               │
│  - fast / deep / cli / python / │
│    data-pipeline / precedent    │
│  - Output ADR or recommendation │
└─────────────────────────────────┘
```

---

## Template Selection Priority

| Priority | Source | Template | Confidence |
|----------|--------|----------|------------|
| 1 (highest) | `template=<name>` parameter | Explicit override | High |
| 2 | `template=X+Y+Z` in query text | Query override + chained domains | High |
| 3 | Domain keywords in query | Keyword detection | Medium |
| 4 | Config file (`.archconfig.json`, `~/.archconfig.json`) | Default domain | Medium |
| 5 | Environment variable `ARCH_DEFAULT_DOMAIN` | Default domain | Medium |
| 6 (lowest) | Complexity indicators | `deep` or `fast` | Low |

---

## Template Matrix

| Template | Target Complexity | Domain | Output Size | Typical Use |
|----------|-------------------|--------|-------------|-------------|
| `fast` | LOW | Generic | ~5 KB | Quick decisions, single file, clear scope |
| `deep` | HIGH | Generic | ~15-30 KB | Redesign, overhaul, multi-system |
| `cli` | Any | CLI/POSIX | ~8 KB | Shell tools, terminal utilities |
| `python` | Any | Python 3.12+ | ~10 KB | Python modules, async, type hints |
| `data-pipeline` | Any | Data Systems | ~12 KB | ETL, streaming, batch processing |
| `precedent` | Any | ADR | ~20 KB | Decision records, precedent analysis |

---

## Template Chaining Rules

Syntax: `template=X+Y+Z`

| Rule | Description |
|------|-------------|
| Primary template (X) | Determines output structure |
| Chained templates (Y, Z) | Provide domain context layering |
| Max chained domains | 2 (primary + 2 chained = 3 total) |
| `precedent` cannot be secondary | `precedent` must be primary if used |
| `fast`/`deep` are complexity selectors | Cannot be chained with other templates |
| All parts must be in allowlist | Invalid template → fall back to complexity detection |

---

## Domain Detection Keywords

| Domain | Keywords |
|--------|----------|
| `cli` | cli, command line, terminal, shell, posix, exit code, argument parsing |
| `python` | python, asyncio, type hint, pydantic, fastapi, flask, django, async, await, decorator, context manager |
| `data-pipeline` | etl, elt, pipeline, streaming, batch, kafka, spark, airflow, dagster, prefect, warehouse, data lake |
| `precedent` | adr, decision record, precedent, document decision, architecture decision record |

Priority: `cli` > `python` > `data-pipeline` > `precedent`

---

## Complexity Detection Keywords

High complexity (triggers `deep` template):

> redesign, overhaul, architecture, microservices, from scratch, rewrite, replace, multi-system, service boundary, schema migration, breaking change

Default: `fast`

---

## Intent Type Detection

| Intent | Keywords | Context |
|--------|----------|---------|
| `ARCHITECTURE_REVIEW` | review, audit, assess, evaluate, critique | + design/architecture/system |
| `IMPROVE_SYSTEM` | improve, optimize, harden, stabilize, enhance, strengthen | + memory/cks/hooks/research/retro/lesson/ingestion/validation |
| `DEFAULT` | Everything else | — |

---

## Expected Execution Time by Stage

| Stage | Expected Time | Notes |
|-------|---------------|-------|
| Stage 0: Pre-flight | < 1s | Pattern matching on query text |
| Stage 0.5: Clarity gate | < 1s | Transcript scan (if context inference needed) |
| Stage 1: Intent classification | < 1s | Keyword matching |
| Stage 1.4: Contract sensitivity | < 1s | Classification rules |
| Stage 1.5-1.7: Contract closure | 0s if not sensitive, 30-60s if sensitive | Packet emission |
| Template execution | 5-30s | Depends on template (fast vs deep) |

---

## Error Recovery

| Error | Recovery |
|-------|----------|
| Invalid template override | Fall back to complexity detection, notify user |
| Config file parse error | Fall back to next config source in priority chain |
| Template file not found | Block with error; template is required |
| CKS unavailable | Continue with generic analysis, log warning |
| Contract closure incomplete | Label design as incomplete, name remaining gap |
