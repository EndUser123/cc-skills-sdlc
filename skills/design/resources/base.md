# Architecture Template - Base (Shared Stages)

> **This template contains shared stages used by both fast.md and deep.md.**
> **Templates extending this:** fast.md, deep.md, cli.md, python.md, data-pipeline.md
>
> **Usage:** Include this template's stages, then add template-specific configuration.

## Template Metadata (Override in extending templates)
- **Target Complexity:** Set by extending template
- **Target Domain:** Set by extending template
- **Expected Output Size:** Set by extending template
- **Execution Instructions:** Read steps, execute in order, do not restate.

## Common Glossary (Shared across all templates)
- **ARCHITECTURE_REVIEW:** Query asks to review/evaluate proposed design or architecture
- **IMPROVE_SYSTEM:** Query asks to optimize/harden existing subsystem
- **DEFAULT:** General architecture decision without improvement intent
- **CKS.db:** Constitutional Knowledge System

---

## [Agency Mode] — Activated when Frustrated User Protocol triggers

> **Check this section first:** Before proceeding to Stage 0, check if the Frustrated User Protocol is active.
> The dispatcher will have set `_frustrated_user_active=True` when triggered.

**You are in agency mode. The user is frustrated or uncertain.**

**DO:**
- Recommend the best default path with explicit criterion
- State: "I recommend X because [criterion]"
- Prefer useful action over perfect diagnosis
- Ask questions ONLY when the answer materially changes implementation

**DO NOT:**
- Ask "Do you want A or B?" for implementation choices
- Make the user choose between technical options
- Push decisions back when user asks for the "happy path"

**Evidence tiers:** Use inline labels when useful:
- `[VERIFIED]` — from Read/Grep/Bash output
- `[PASTED_LLM]` — from another AI (hypothesis, not authority)
- `[USER]` — user's explicit preference

**Output for skill improvement requests (when asked):**
1. What is going wrong
2. Best happy path
3. Skill changes
4. First patch to make
5. What this prevents next time

---

## Execution Instructions (Base)

**Do not:** Restate these instructions, summarize, or paraphrase.

**Do:**
1. Execute steps sequentially
2. Follow decision tree exactly
3. Apply template-specific depth (fast=concise, deep=comprehensive)
4. Stop at each decision point and evaluate

---

## Stage 0: Detect Intent Type (SHARED)

From the user query, identify:

**Is this an ARCHITECTURE_REVIEW request?**
- Keywords: review, evaluate, assess, analyze, audit, validate, critique
- Context: design, architecture, integration, proposal, theoretical
- **If YES:** Proceed to Stage 0.1, then ARCHITECTURE_REVIEW Path

**Is this an IMPROVE_SYSTEM request?**
- Keywords: improve, optimize, harden, stabilize, enhance, strengthen
- Subsystem: memory, CKS, hooks, research, retro, lesson, ingestion, validation
- **If YES:** Proceed to Stage 0.1, then IMPROVE_SYSTEM Path

**Otherwise (DEFAULT):**
- Proceed to Stage 0.1, then DEFAULT Path

---

## Stage 0.1: Constitutional Compliance Check (MANDATORY — ALL PATHS)

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

## Stage 0.1.1: Stateful Contract Closure (MANDATORY — persistence/history/provider designs)

**Trigger this stage when the query or recommended design involves any of:**
- history, archive, transcript, retention, event log
- provider or multi-provider ingest
- watermark or replay
- dedupe or normalization
- session, terminal, conversation, turn identity
- stale-data immunity, invalidation, cache freshness

**Before proceeding, close these contracts explicitly:**

1. **Identity Model**
   - Define each identifier separately: `provider_id`, `source_id`, `conversation_id`, `session_id`, `terminal_id`, `turn_id`
   - If a provider has no real terminal concept, define `provider_instance_id` or equivalent instead of overloading `terminal_id`
   - State which identifiers are authoritative vs synthesized

2. **Ordering Contract**
   - Specify one mandatory ordering rule only
   - Define replay and watermark advancement semantics precisely
   - Do NOT present multiple competing strategies as equally valid defaults

3. **Dedupe Contract**
   - State exactly what counts as the “same event”
   - Ensure schema keys/unique constraints match the prose behavior
   - If content-based dedupe is claimed, say where content hash participates in identity

4. **Freshness / Invalidation Contract**
   - Name the authority of truth
   - Name derived caches/projections
   - Define invalidation triggers, replay triggers, and stale-row behavior
   - If the design claims stale-data immunity, the invalidation algorithm cannot be deferred

5. **Event Source of Truth**
   - For tasks, opportunities, and projections, name the authoritative event source
   - Do NOT leave “emitted vs derived later” as an open implementation choice

6. **Mechanism Triggerability**
   - For each freshness, invalidation, replay, dedupe, or locking rule, name the exact event that causes it to fire
   - State which artifact changes and why that change is reachable under the other invariants
   - If another invariant makes the trigger impossible, mark the design as incomplete

7. **Contract-to-Test Coherence**
   - Every named contract must have at least one acceptance scenario that asserts the same behavior
   - Tests must not describe the opposite of the contract they are supposed to validate
   - If the contract and test matrix disagree, the design is incomplete until one is changed

8. **Decision Closure**
   - If any contract above is unresolved, mark the design as `GAP` / `needs follow-up`
   - Do NOT present the result as implementation-ready architecture

**Required output for this stage:**
- A short contract table or equivalent explicit bullets covering all named contracts above
- Trigger conditions / invalidating events for each stateful mechanism
- A short contract-to-test alignment note for each named contract
- A statement confirming whether the architecture is decision-closed or still has gaps

---

## Stage 0.2: Pre-Stage Discovery Hint (SHARED)

**Based on codebase size and query complexity, suggest additional tools:**

- If codebase has 10+ files: suggest `/review_bundle` for comprehensive file review
- If unfamiliar with codebase structure: suggest `/aid arch` for structure discovery
- Fast template: read up to **3 key files** (deep template: max 5)

---

## Stage 0.3: Codebase-Aware Analysis (SHARED)

**If query references existing code, analyze codebase first using AI Distiller (AID).**

> **Configuration variables** (set by extending template):
> - `{COMPRESSION_LEVEL}`: aid compression level (fast=moderate, deep=high)
> - `{MAX_FILES}`: Maximum files to read (fast=3, deep=5)
> - `{AI_ACTION}`: AI action for deep analysis (deep=complex-codebase-analysis, fast=none)

**PRIMARY METHOD: AI Distiller (CLI-based, no fallback)**

AID is required for codebase analysis — it provides:
- 60-90% context reduction while preserving semantic structure
- Enterprise-grade AI action prompts for deep analysis
- Layer detection and dependency direction analysis
- Multi-terminal safe (stateless, read-only)

```python
from aid_wrapper_v2 import create_aid_integrator, AIDAIAction

# Initialize AID integrator (requires aid.exe at ~/.aid/bin/aid.exe)
integrator = create_aid_integrator(config={"compression_level": "{COMPRESSION_LEVEL}"})

# Basic distillation for structure discovery
analysis = integrator.distill(
    target_path="src/",
    include_patterns=["*.py", "*.ts"],
    exclude_patterns=["*test*"]
)
# Use analysis.distilled_structure for compressed codebase overview (60-90% reduction)
# Use analysis.public_apis for interface discovery
# Use analysis.dependencies for integration planning
# Use analysis.boundaries for decomposition decisions
# Use analysis.metrics for analysis statistics

# Layer detection (controllers/services/repositories/models):
layers = integrator.detect_layers("src/")
# Use layers.layers for classified files by architectural layer
# Use layers.violations for architectural violations detected
# Use layers.confidence for classification confidence score

# Dependency direction analysis (coupling violations):
dep_dir = integrator.analyze_dependency_direction("src/")
# Use dep_dir.inbound_coupling for highly-coupled modules (many dependents)
# Use dep_dir.outbound_coupling for complex modules (many dependencies)
# Use dep_dir.violations for circular/reverse dependency violations

# DEEP TEMPLATE ONLY: AI action prompts for enterprise-grade analysis
if "{AI_ACTION}" != "none":
    ai_prompt = integrator.analyze_with_ai_action(
        target_path="src/",
        ai_action=AIDAIAction.COMPLEX_CODEBASE,  # or other AIDAIAction values
        include_patterns=["*.py", "*.ts"],
        exclude_patterns=["*test*"]
    )
    # Use ai_prompt for comprehensive analysis with:
    # - Project context inference and assumption tracking
    # - Enterprise concerns (compliance, governance, scalability)
    # - Evidence-based findings with confidence levels
    # - Coverage gaps and static analysis limitations
    # - Architectural recommendations with dependency tracking

    # Diagram generation (Mermaid):
    diagrams = integrator.generate_diagrams("src/")
    # Use diagrams for architecture visualization (10 diagrams generated)
```

**AID AVAILABILITY CHECK:**

If AID CLI is not available at `~/.aid/bin/aid.exe`, the architecture analysis proceeds without AID-dependent features. The template will use direct file analysis instead. Graceful degradation path:

```
AID NOT AVAILABLE — proceeding with direct file analysis
- AID provides: layer detection, dependency direction analysis, AI action prompts
- Fallback: manual file globbing + grep for architectural pattern detection
```

To enable AID features:
- Download: https://github.com/janreges/ai-distiller/releases
- Install: Extract aid.exe to ~/.aid/bin/ (Windows) or ~/bin/ (Unix)
- Verify: aid --version

**Skip this stage if:**
- Query is purely theoretical or greenfield (no codebase to analyze)
- User explicitly requests offline analysis without codebase context

---

## Stage 0.6: Domain Resource Inclusion (SHARED)

**Before proceeding with decision path, check if domain-specific resources should be included.**

### Detect Default Domain

Check if a default domain is set:
- Environment variable: `ARCH_DEFAULT_DOMAIN`
- Conversation context: `conversation_context.get("default_domain")`

### Domain-Specific Resource Inclusion

If a domain is detected (default or keyword-based), include domain-specific considerations:

| Domain | Include When | Resource Sections |
|--------|--------------|-------------------|
| **python** | Default=python OR keywords detected | Async assessment, type hints, GIL considerations |
| **cli** | Default=cli OR keywords detected | POSIX compliance, signal handling, exit codes |
| **data-pipeline** | Default=data-pipeline OR keywords detected | ETL patterns, streaming vs batch, data quality |
| **precedent** | Default=precedent OR keywords detected | ADR format, decision documentation, precedent tracking |

### No Domain Detected

Proceed directly with generic decision path.

---

## Stage 0.7: Web Research (SHARED - with variable depth)

**Before proceeding with either IMPROVE_SYSTEM or DEFAULT path, conduct targeted web research.**

> **Configuration variables** (set by extending template):
> - `{SEARCH_COUNT}`: Number of web searches (fast=1-2, deep=3-5)
> - `{SEARCH_DEPTH}`: Research depth (fast=targeted, deep=comprehensive)

### Research Query Generation

From user's query, generate {SEARCH_COUNT} focused searches:

1. **Current best practice** — What's the recommended approach for this specific pattern/problem right now?
2. **Version/deprecation check** — Are technologies involved current, or have breaking changes occurred?
3. **Failure modes** — What typically goes wrong with this pattern at scale? (deep template only)
4. **Alternatives** — What are the main alternatives used in production? (deep template only)
5. **Security advisories** — Any security considerations for auth/network/storage in scope? (deep template only)

### Execution

```
For each query ({SEARCH_COUNT} queries):
    1. WebSearch("[query]")
    2. WebFetch(top result) if needed for version/API details
    3. Extract: current recommendation, version info, key gotcha
```

### Integration

Weave findings into decision output — don't create a separate "research" section. Cite versions and sources inline.

### Skip Condition

Skip ONLY if: query is purely about user's internal system AND CKS has sufficient data, OR user explicitly requests offline analysis.

---

## Stage 0.4: Determine Response Mode (SHARED)

**Before proceeding to option generation or decision paths, determine the response mode.**

### Decision Tree

```
Is this a diagnostic/RCA request?
├─ Keywords: why failing, root cause, adversarial review, diagnose, investigate,
│             what's wrong, debug, failure analysis, post-mortem
├─ Intent: Understand a failure, identify root cause, verify correctness
└─ If YES → DIAGNOSTIC_MODE

Otherwise, is this a design-improvement/execution request?
├─ Keywords: improve, fix, implement, add, optimize, refactor, harden
│           (without explicit RCA keywords)
├─ Intent: Make a change, improve workflow, fix broken behavior
└─ If YES → DESIGN_IMPROVEMENT_MODE

Otherwise → DEFAULT mode (per query type)
```

### Mode Requirements

#### DIAGNOSTIC_MODE

**Use for:** Root cause analysis, failure investigation, adversarial review, correctness verification.

**Required structure:**
- Competing hypotheses (at least 2-3 distinct explanations)
- Falsification tests for each hypothesis
- Baseline comparison (what "working" looks like)
- Evidence trail for each claim

**Output format:**
```
## Diagnostic Analysis: [Problem]

### Hypotheses

| ID | Hypothesis | Falsification Test | Status |
|----|-----------|-------------------|--------|
| H1 | [explanation] | [test that would prove this false] | [untested/falsified/confirmed] |
| H2 | [explanation] | [test that would prove this false] | [untested/falsified/confirmed] |

### Baseline Comparison
[What behavior exists when the system is working correctly]

### Evidence Trail
[Cite files, logs, tests for each finding]

### Conclusion
[Which hypothesis survived, with probability estimate]
```

#### DESIGN_IMPROVEMENT_MODE

**Use for:** Practical improvements, workflow fixes, implementation tasks.

**Required structure (minimum):**
- Recommended path
- Why this path (criterion)
- Risk
- Mitigation
- First reversible step

**Do NOT require:**
- Competing hypotheses (unless genuinely uncertain)
- Falsification tests (unless dealing with failure mode)
- Baseline comparison (unless comparing before/after)

**Output format:**
```
## Recommended Path: [Action]

**Criterion:** [why this path is the best choice]

**Risk:** [what could go wrong]

**Mitigation:** [how to handle the risk]

**First reversible step:**
1. [Concrete action with file path and code/pseudocode]
2. [How to verify the step worked]
3. [How to undo if needed]
```

### Mode Flags

Add mode flag to output headers to indicate which mode was used:

| Mode | Use For |
|------|---------|
| `[DIAGNOSTIC MODE]` | RCA, adversarial review, failure investigation |
| `[DESIGN-IMPROVEMENT MODE]` | Practical fixes, improvements, implementation |

### Mode Selection Examples

| Query | Mode | Reason |
|-------|------|--------|
| "Why is authentication failing?" | DIAGNOSTIC | RCA keywords present |
| "Review this ADR for contradictions" | DIAGNOSTIC | Adversarial review request |
| "Improve this workflow" | DESIGN_IMPROVEMENT | Practical improvement |
| "Fix the hook registration bug" | DESIGN_IMPROVEMENT | Implementation task |
| "Implement a new feature" | DESIGN_IMPROVEMENT | New functionality |
| "Design a new component" | DEFAULT | Greenfield design (use existing path) |

---

## Stage 0.8: Verbalized Sampling Option Generation (SHARED)

**For DEFAULT path: Generate diverse architecture options using Verbalized Sampling pattern.**

### What is Verbalized Sampling?

Verbalized Sampling (VS) is a technique where the model explicitly generates multiple candidate options with internal probability estimates, enforcing diversity constraints rather than returning a single "most likely" answer.

**Research shows**: VS produces 2x more diversity and better human preference ratings compared to standard prompting.

### VS Protocol

**Generate K=3-4 candidate architectures** with the following structure for each:

```
Option <ID>:
  <text>: [5-10 sentence outline of the design]
  <lens>: Primary optimization lens from:
         [value_optimization, consolidation, dependency_pruning,
          contract_first, multi_terminal_safety, evidence_based,
          systems_thinking, alternative_quality]
  <changes>: Concrete structural changes (dependencies, state locations, boundaries)
  <probability>: Numeric estimate in [0,1] of how likely this is to be a good solution
```

### Diversity Constraints (MANDATORY)

1. **Lens Separation**: Options must differ in primary lens OR structural changes
   - No two options should optimize the same lens with similar change sets
   - Example: One option optimizes value, another optimizes safety, another optimizes consolidation

2. **Structural Distance**: Each option must have at least one concrete graph-level delta:
   - Different dependency pattern (e.g., reduces shared module vs introduces adapter)
   - Different state model (e.g., push/pull boundaries, caching strategy)
   - Different operational pattern (within Windows/CLI constraints)

3. **Probability Banding**: Enforce distribution across probability bands:
   - **Fast template**: At least 2 options with probability ≥ 0.3
   - **Deep template**: At least 1 option with probability ≤ 0.25 (tail exploration)
   - All options must have probability ≥ 0.05 (no nonsense)

### Quality Filters

**Before presenting options, apply these filters:**

1. **Hard Invariants Check**: Any option violating multi-terminal safety or constitutional invariants is discarded
2. **Feasibility Check**: Option must be technically plausible (no magic, no impossible requirements)
3. **Complexity Cap**: Options that would exceed complexity thresholds are omitted with explanation

### Output Format

Present survivors in a compact comparison table:

| Option | Lens | Probability | Key Changes | Tradeoff |
|--------|------|-------------|-------------|----------|
| A | [lens] | [prob] | [changes] | [favors]/[sacrifices] |
| B | [lens] | [prob] | [changes] | [favors]/[sacrifices] |
| C | [lens] | [prob] | [changes] | [favors]/[sacrifices] |

**Mark RECOMMENDED option** with clear rationale.

### Integration Note

This stage feeds into the DEFAULT decision path. The VS-generated options become the "Options" section in the DEFAULT output structure, with probabilities and lenses explicitly stated.

---

## ARCHITECTURE_REVIEW Path (SHARED)

**Purpose**: Evaluate proposed architecture/design WITHOUT recommending alternatives or suggesting implementation first.

**Default mode:** DIAGNOSTIC_MODE (adversarial review, gap analysis, risk assessment)

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

> **Configuration variables** (set by extending template):
> - `{OUTPUT_SIZE_GUIDANCE}`: Output size target (fast=~5 KB, deep=~15-30 KB)

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
- Multi-terminal: [safe / single-terminal only / needs investigation]
- [Document how design handles multi-terminal concurrency]

### Edge Case Considerations
**Internal self-reflection**: Ask yourself "Are there other issues, conditions, or edge cases we should consider?" and document your findings here. Consider:
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

## IMPROVE_SYSTEM Path (SHARED)

**Default mode:** DESIGN_IMPROVEMENT_MODE (practical changes, reversible steps)

### Your Definition of "Improve" Is Authoritative

No discovery phase. No clarifying questions.

**Your definition (final):**
- Improve = prevents repeated problems OR makes things faster
- System = named subsystem (memory, hooks, research, etc.)
- Source of truth = CKS.db memory entries (492 entries available)

### Stage 1: Query CKS for Failures (2–3 min)

**Check CKS availability:**

```python
# Import and check availability
try:
    from cks_query_templates import cks_search
    cks_available = True
except ImportError:
    cks_available = False
```

**If CKS IS available, query for memory entries:**

```python
# Extract subsystem from query
subsystem = "<extract from query: memory, hooks, CKS, research, retro, lesson, ingestion, validation, etc.>"

# Use semantic search to find failure history
failures = cks_search(f"{subsystem} failures problems bugs", limit=10)

# If no failures found, acknowledge and proceed
if not failures:
    print("Note: No CKS memory entries found for this subsystem.")
    print("Proceeding with generic best practices analysis.")
```

**For each result, extract:**
1. What question was (the failure scenario)
2. What answer was (the fix or diagnosis)
3. Pattern type (detection, recovery, prevention, visibility gap)

### Stage 2: Extract Pattern (1 min)

From those 2–3 failures, identify:

**What class of problem repeats?**
- Detection gap (we didn't see it coming)?
- Recovery gap (saw it but took forever to fix)?
- Prevention gap (could have blocked it)?
- Visibility gap (failure is silent)?

One sentence max.

### Stage 3: Determine Action (2–3 min)

**Three possible outcomes:**

**A) NO CHANGES NEEDED** (if system is already optimal)
- Document why current implementation is sufficient
- Cite evidence of existing optimizations
- Skip to Stage 4 with "No Action Recommended" output

**B) PROPOSE CHANGES** (if repeating pattern found)
For EACH repeating pattern, propose ONE concrete change that:
1. Would have prevented or caught that failure, OR
2. Would have shortened diagnosis/fix time by >=50%

**Keep it small, testable, implementation-ready.**

**Required for each change:**

1. **What file(s) to create or edit**
   - Path (e.g., `/.claude/hooks/pre-delete-validator.ps1`)
   - New? Modify existing?

2. **Exact change (pseudocode or code)**
   - Hook logic, schema field, validation rule, script, etc.
   - Keep to 5–20 lines
   - Use `.ps1` or `.bat` for Windows (no `.sh`)

3. **How to test it**
   - One concrete scenario that triggers old failure
   - What new system should do differently
   - How to verify success

4. **Success metric**
   - "Caught before breaking research"
   - "Diagnosis < 5 min instead of 30 min"
   - "Automated suggestion instead of manual excavation"

**C) INSUFFICIENT DATA** (if CKS unavailable + no obvious issues)
- Acknowledge limitation
- Recommend monitoring or data collection
- Skip to Stage 4 with "Insufficient Data" output

### Stage 4: Return Output

**Format for NO CHANGES NEEDED:**
```
## Analysis: Improve [Subsystem Name]

### Findings
[Evidence that current implementation is already optimal]
[Cite specific optimizations already in place]

### Recommendation
NO ACTION RECOMMENDED

System is already well-optimized:
- [Optimization A] already implemented (file:line)
- [Optimization B] already implemented (file:line)
- No repeating failure patterns detected

### Optional Future Work (LOW priority)
[Any minor optimizations that are NOT recommended unless profiling shows bottleneck]
```

**Format for PROPOSE CHANGES:**
```
## Analysis: Improve [Subsystem Name]

### Failures Identified (from CKS)
[List 2–3 failures with what happened, fix/solution, pattern type]

### Pattern
[One sentence: class of repeating problem]

### Proposed Changes

**Change A:** [Name]
- File(s): [path]
- Logic: [pseudocode/exact lines]
- Test: [scenario]
- Success: [metric]

**Change B:** [Name] (optional)
- File(s): [path]
- Logic: [pseudocode/exact lines]
- Test: [scenario]
- Success: [metric]

### Implementation Order
1. Change [X] — easiest, highest payoff
2. Change [Y] — enables Change Z
3. Change [Z] — final hardening

Estimated effort: X hours total
```

**Format for INSUFFICIENT DATA:**
```
## Analysis: Improve [Subsystem Name]

### Limitations
[Why analysis couldn't determine optimization needs]
- CKS unavailable
- No obvious failure patterns in codebase
- Need performance profiling data

### Recommendation
COLLECT MORE DATA

Suggested next steps:
1. [Monitoring/data collection action]
2. [Profiling approach]
3. [When to revisit]
```

---

## DEFAULT Decision Path (SHARED)

**IMPORTANT: ADR format is the DEFAULT output.**

**Default mode:** Use DESIGN_IMPROVEMENT_MODE unless RCA keywords present (see Stage 0.4).

**CHECK FOR VERBOSE FLAG FIRST:**

**IF user query contains `--verbose` or `-v` flag:**
- Proceed to "VERBOSE OUTPUT MODE" section below
- Show full analysis with intermediate stages

**ELSE (default mode, no verbose flag):**
- Proceed to "DEFAULT OUTPUT MODE (ADR ONLY)" section below
- Show ONLY the ADR format
- DO NOT show any verbose sections
- STOP after "Persist Output" step in ADR section

Your job: Answer "What's smallest change that solves this?"

**CONSTRAINTS:**
- Prefer local reordering, parameter changes, conditions
- Do NOT propose new services, modules, or layers
- Do NOT generate fake alternatives (2 real options max)
- Keep output tight: {OUTPUT_SIZE_GUIDANCE} maximum

---

## DEFAULT OUTPUT MODE (ADR ONLY)

**Use this mode when: NO `--verbose` or `-v` flag is present**

**CRITICAL: In this mode, output ONLY the ADR format below. DO NOT add any additional sections, explanations, or analysis.**

```markdown
# ADR-YYYYMMDD-[slug]: [Decision Title]

**Status:** Accepted
**Date:** YYYY-MM-DD
**Context:** [What problem does this solve?]

### Decision
[One-line decision statement]

### Rationale
[Why this approach - brief, 2-3 sentences]

### Alternatives Considered
| Option | Description | Pros | Cons | Why Rejected |
|--------|-------------|------|------|--------------|
| **Chosen** | [Description] | [Benefit] | [Cost] | N/A |
| Alternative | [Description] | [Benefit] | [Cost] | [Reason] |

### Tradeoffs
| Quality | Improved | Degraded |
|---------|----------|----------|
| [ISO 25010 quality] | [Benefit] | [Cost] |

### Friction Budget Quality Attribute

**Minimize cognitive load on the user:**

| Metric | Target (fast) | Target (deep) |
|--------|--------------|--------------|
| Clarification count | ≤ 1 | ≤ 3 |
| Permission push count | 0 (routine tasks) | ≤ 2 |
| Implementation choice burden | ≤ 1 | ≤ 2 |
| Internal failures exposed | 0 | 0 |
| Time to first action | < 5 min | < 10 min |
| Safe default available | Yes | Yes |

**Fail if:**
- Clarification count exceeds threshold without justification
- No safe default for non-preference choices
- Time to first action exceeds threshold

**Warn if:**
- Permission push count exceeds threshold for routine tasks
- Internal tool failures exposed to user

See `resources/friction_budget.md` for full guidance.

### Multi-Terminal Safety
- [Safe / Single-terminal only / Needs investigation]
- [How concurrent terminals are handled]

### Implementation
- [What changes: files, APIs, structures]
- [Testing approach]
- [Rollback: how to undo]

### Consequences
- **Positive:** [Benefits]
- **Negative:** [Costs/risks with mitigations]
```

**Persist Output:**
Auto-save to `P://.claude/arch_decisions/` unless output is under 2KB or user requests ephemeral.

```python
# Filename format (use actual datetime, do not hardcode date)
from datetime import datetime
date = datetime.now().strftime("%Y-%m-%d")
slug = re.sub(r'[^a-z0-9]+', '-', query[:50].lower()).strip('-')
filename = f"{date}_{TEMPLATE_TYPE}_{slug}.md"
```

**STOP HERE. Do not proceed to VERBOSE OUTPUT MODE.**

---

## VERBOSE OUTPUT MODE

**Use this mode ONLY when: `--verbose` or `-v` flag IS present**

**In verbose mode, show the ADR format above PLUS the following sections:**

#### 1. Decision Statement (1 paragraph)
What's changing, why, goal. Tight.

#### 2. Options (from Stage 0.8 Verbalized Sampling)

Use the VS-generated options from Stage 0.8. If Stage 0.8 was skipped (e.g., ephemeral query), generate 2-3 real options:

Each option must differ on at least one axis (technology, approach, coupling, etc.). Include a **Differs on:** line.

**Option A:** [VS-generated or Proposed change]
- **Lens:** [primary lens optimized]
- **Probability:** [estimated quality if VS used]
- Pro: [real benefit]
- Con: [real cost]
- **Differs on:** [axis]
- **Changes:** [structural changes if VS used]

**Option B:** [VS-generated or Status quo/variant]
- **Lens:** [primary lens optimized]
- **Probability:** [estimated quality if VS used]
- Pro: [real benefit]
- Con: [real cost]
- **Differs on:** [axis]
- **Changes:** [structural changes if VS used]

#### 3. Recommendation
One sentence: why A is better than B. Ground in research findings where available.

#### 4. Implementation
Before/after code or pseudocode.
Rollback: how to undo.

#### 5. Quick Ramifications
- Break anything? (state if yes)
- Edge cases? (mention if subtle)
- Constraints? (quota, perf, UX?)

#### 6. API Surface Consistency Check

Before the ADR is finalized, verify every concrete claim about the target system's API against the confirmed API surface. Flag contradictions before the document leaves drafting.

**What to check:**
- Any claim about what a hook CAN or CANNOT do (append-only, transform, block, etc.)
- Version-gated capabilities (`AskUserQuestion` requires 2.0.22+)
- Field names or return shapes (`additionalContext`, `EnhancementResult`, etc.)
- Latency or sync/async guarantees

**Format:**
```
| Claim | Evidence | Status |
|-------|-----------|--------|
| Hooks can append `additionalContext` | code.claude.com/docs/en/hooks | VERIFIED |
| Hooks can strip/mutate prompt text | code.claude.com/docs/en/hooks | CONTRADICTS-API |
```

**If CONTRADICTS-API entries exist:** fix the claim before the ADR proceeds. Do not publish with contradictions.

#### 7. Confidence

One-line confidence with evidence basis:
```
Confidence: [X]% — [evidence summary]
```

#### 8. Adversarial Self-Review (Recommended)

One-line weakest assumption check:
```
Weakest assumption: [assumption]. If wrong: [consequence]. Mitigation: [action].
```

#### 9. Persist Output

Auto-save to `P://.claude/arch_decisions/` unless output is under 2KB or user requests ephemeral.

```python
# Filename format (use actual datetime, do not hardcode date)
from datetime import datetime
date = datetime.now().strftime("%Y-%m-%d")
slug = re.sub(r'[^a-z0-9]+', '-', query[:50].lower()).strip('-')
filename = f"{date}_{TEMPLATE_TYPE}_{slug}.md"
```

---

## Resilience Considerations (SHARED)

**For I/O-bound operations:** Consider using `@with_resilience(profile='aggressive')` to handle transient errors
- Location: `P://__csf/src/lib/resilience_patterns.py`
- Retry on: `ConnectionError`, `TimeoutError`, `TransientLLMError`, `QuotaError`
- No retry on: `InvalidUserInputError` (user errors should fail fast)

**For write operations:** Use `@with_resilience(profile='write_path', idempotent=False)`
- Minimal retries (max 1) to avoid duplicate side effects
- Circuit breaker prevents cascade failures

**Feature flags available:**
- `RESILIENCE_DISABLED_FOR=<skill_names>` — disable resilience for specific skills
- `RESILIENCE_OBSERVE_ONLY=true` — log without applying resilience patterns

**Import:**
```python
from src.lib.resilience_patterns import with_resilience, TransientLLMError, QuotaError
```

---
*End of base template. Extending templates should override configuration variables and add template-specific guidance.*
