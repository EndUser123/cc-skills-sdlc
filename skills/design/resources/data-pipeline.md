# Data Pipeline Architecture Analysis

## Template Metadata
- **Target Complexity:** Any
- **Target Domain:** Data Systems
- **Expected Output Size:** ~12 KB
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
3. Data systems specific analysis (ETL, streaming, batch)
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
- **If YES:** Proceed to "IMPROVE_SYSTEM: Optimize Existing Pipeline" below

**Otherwise (DEFAULT):**
- Proceed to "DEFAULT: New Pipeline Design" below

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

---
**Confidence:** [X]%

**Evidence basis:**
- Design doc: [source]
- Web research: [count] sources
- Codebase analysis: [files reviewed]

**Key assumptions:**
1. [assumption]
2. [assumption]
Bronze (raw) → Silver (cleaned) → Gold (aggregated)

---

## Success Criteria

✅ Batch vs streaming justified
✅ Backpressure strategy defined
✅ Orchestration tool appropriate for scale
✅ Data quality checkpoints defined
✅ Cost considered (warehouse compute vs cluster)
✅ Late data handling specified

---

## Stage 0.3: Codebase-Aware Analysis

> See **Codebase-Aware Analysis (Stage 0.3)** in `shared_frameworks.md`.

If query references existing pipeline code/DAGs/configs, read them first. Build CODEBASE CONTEXT.

---

## Stage 0.7: Web Research

**Conduct targeted web research before analysis.**

> See **Web Research Framework** in `shared_frameworks.md` for complete protocol.

**For data-pipeline template: Use Domain-focused depth (2-3 searches, max 5).**

Focus searches on:
1. **Tool/framework versions** — Current Kafka, Spark, Airflow, Dagster, Prefect versions and breaking changes
2. **Data platform patterns** — Current best practices for specific pipeline pattern (streaming, batch, CDC)
3. **Scale/cost trade-offs** — Real-world cost and performance data for mentioned cloud services or tools

Integrate findings inline. Cite version numbers and sources.

---

## IMPROVE_SYSTEM: Optimize Existing Pipeline

**Trigger:** User asks to "optimize", "harden", "scale", or "fix performance" of existing data subsystem.

**Analysis Steps:**

1. **Identify Bottleneck**
   - Ingestion lag? (producer slower than consumer)
   - Processing time? (compute bound)
   - Network I/O? (data transfer between regions/zones)
   - Warehouse cost? (ELT compute expensive)

2. **Backpressure Check**
   - Kafka consumer lag? (increase partitions, parallel consumers)
   - Spark streaming backpressure? (enable `spark.streaming.backpressure.enabled`)
   - Airflow task duration? (parallelize, split tasks)

3. **Data Quality**
   - Schema drift? (enforce schema registry, validate on write)
   - Duplicate records? (idempotent keys, dedup before join)
   - Late data? (watermarking, reprocess windows)

4. **Cost Optimization**
   - Warehouse ELT too expensive? → Move batch to Spark/Dask
   - Streaming overkill? → Fall back to batch if latency allows
   - Over-provisioned cluster? → Auto-scale based on load

5. **Orchestration**
   - Airflow DAG complexity too high? → Consider Prefect/Dagster
   - Manual triggers? → Automate with data-driven schedules
   - No observability? → Add metrics (consumer lag, task duration, data freshness)

**Output:** Specific recommendations with tooling (e.g., "Enable Spark backpressure", "Add Kafka partitions", "Switch to ELT on BigQuery").

---

## DEFAULT: New Pipeline Design

**Trigger:** New pipeline, greenfield, "how to architect data flow".

**Decision Tree:**

### Step 1: Batch vs Streaming

**Choose streaming if:**
- Latency requirement < 5 minutes
- Real-time analytics required
- High-velocity event data (clicks, sensors, logs)

**Choose batch if:**
- Daily/hourly latency acceptable
- Cost sensitivity (batch cheaper)
- Simplicity preferred

**Hybrid if:**
- Real-time dashboard + daily batch reporting

### Step 2: ETL vs ELT

**Choose ELT if:**
- Destination is Snowflake, BigQuery, Redshift, Databricks
- Large datasets (TB+)
- Transformation mostly SQL/warehouse-native

**Choose ETL if:**
- Legacy warehouse (limited compute)
- Complex transformations outside SQL
- Data quality critical before load

### Step 3: Orchestration

**Airflow:**
- Proven, large community
- Code-first DAGs
- Complex at scale (hundreds of DAGs)

**Prefect:**
- Modern, dynamic workflows
- Better DX for Python-first teams
- Simpler for small/medium scale

**Dagster:**
- Data-aware orchestration
- Built-in data quality testing
- Asset-based lineage

**No orchestration if:**
- Simple cron jobs
- Lambda/serverless functions
- Pure streaming (Kafka → Flink → sink)

### Step 4: Storage Pattern

**Medallion Architecture (recommended for analytics):**
- Bronze: Raw landing zone (append-only)
- Silver: Cleaned, typed, deduplicated
- Gold: Aggregated, BI-ready

**Immutable Data Lake:**
- Partition by date/hour
- Never overwrite (append-only new partitions)
- SCD Type 2 for dimension updates

### Step 5: Data Quality

- Schema enforcement (Schema Registry, Great Expectations)
- Idempotent processing (reprocess-safe)
- Late data handling (watermarks, reprocess windows)
- Duplicate detection (natural keys, dedup before join)

---

## Output Format

**Recommendation:** [One-sentence architecture summary]

**Rationale:**
- Volume/velocity: [x GB/day, latency y]
- Processing model: [batch/streaming/hybrid]
- Tooling: [Spark, Airflow, Kafka, warehouse]

**Architecture:**

**Key Decisions:**
1. Batch vs streaming: [justification]
2. ETL vs ELT: [justification]
3. Orchestration: [tool + rationale]

**Data Quality:**
- [Schema enforcement strategy]
- [Duplicate handling]
- [Late data handling]

**Cost Considerations:**
- [Warehouse compute vs cluster]
- [Streaming vs batch trade-off]

**Risks:**
- [Domain-specific risks]

---

## Final Output Block

**Decision:** [One sentence recommendation]

**Rationale:** [2-3 key reasons, domain-specific]

**Alternatives Considered:** [Brief list with domain trade-offs]
> Apply **Forced Alternative Quality Gate** — each alternative must differ on at least one axis.

**Risk:** [Domain-specific risks]

> Apply **Version Verification Rule** — verify all tool/framework version claims against official docs.

**Confidence:** [X]% — [evidence basis]
> Apply **Confidence Calibration Rules** from `shared_frameworks.md`.

**Adversarial Self-Review:** (Recommended)
> One-line weakest assumption + consequence per `shared_frameworks.md`.

**Persist:** Auto-save to `P:\\\\\\.claude/arch_decisions/` per **Output Persistence** protocol.

```python
# Filename format (use actual datetime, do not hardcode date)
from datetime import datetime
date = datetime.now().strftime("%Y-%m-%d")
slug = re.sub(r'[^a-z0-9]+', '-', query[:50].lower()).strip('-')
filename = f"{date}_data_pipeline_{slug}.md"

---
*End of data-pipeline template. Falls back to generic decision format.*
