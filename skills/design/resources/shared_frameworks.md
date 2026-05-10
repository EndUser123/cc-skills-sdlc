# Shared Decision Frameworks

**These frameworks are available to all templates.**

## First Principles Thinking

When stuck:
1. What's the assumption I'm making?
2. Is it true? (or just conventional wisdom?)
3. What if I invert it?

Example: "Caching always helps" → "When does caching hurt?"

## Simplicity-First

Evaluating options:
1. Does this add ESSENTIAL complexity? (required by problem)
2. Or ACCIDENTAL complexity? (introduced by solution)
ALWAYS prefer less accidental complexity.

## Systems Thinking

Trace ripple effects:
1. What component changes?
2. What depends on it?
3. What depends on those?
4. Are there feedback loops? (amplification?)

## Theory of Constraints

Optimizing:
1. What's the actual bottleneck?
2. Can I optimize AT the bottleneck?
3. What's the NEXT bottleneck after this one?

---

## Lean System Design

**Purpose:** Generate lean, high-leverage system designs that advance core goals without maximal feature lists.

### Core Principles

**1. Optimize for value, not coverage**

Treat the user's stated goals as the objective function. For this ecosystem, the primary goals are:
- Cross-file/codebase-level understanding and validation
- Consolidation and simplification of skills/tools
- Runtime safety and correctness

For every major subsystem proposed:
- Explicitly justify how it advances one or more of these goals
- Any component that does not meaningfully move these goals must be cut or marked "optional / future enhancement"

Before finalizing any design:
> "For each major subsystem I proposed, here is how (or if) it directly advances the core goals. Here are at least 3 parts of my own plan that are over-engineered or premature; here is a strictly smaller but equally effective design."

**2. Prefer merging to duplicating mechanisms**

The user already has:
- A hook system (PreToolUse, PostToolUse, Stop, SessionStart) with fail-open vs fail-closed semantics

Before creating any new enforcement or rule engine:
- First compare it to the existing hooks/policies
- If they overlap in responsibility, design a merged system and delete or avoid the weaker one
- Must not leave two parallel, overlapping rule systems without strong, explicit justification

Add an explicit section to any design:
> "Potential duplicate mechanisms I introduced vs existing hooks/policies, and how I will merge or remove them."

**3. Be ruthless about external dependencies and complexity**

Constraints:
- Solo dev, Windows 11, Python 3.14, no ops team, no DB, standard library only for hooks/skills

For every external dependency (SCIP, MCP servers, extra LLM providers, heavy infra):
- Classify as MUST / SHOULD / MAY
- Design a v1 that uses only MUST-level dependencies
- Move SHOULD/MAY items into "Optional Enhancements" with clear triggers (e.g., "add this only if false positive rate > 20% after initial rollout")

Add a section:
> "Dependency audit: which dependencies are absolutely required for v1, which are optional later, and what is the minimal v1 without them?"

Avoid multi-model consensus / Star Chamber patterns, complex A/B infra, or SDLC ceremony unless essential.

**4. Contract-first: define core schemas and APIs before task lists**

Before listing tasks:
- Define the core data contracts that everything will use (e.g., AnalysisUnit/manifest JSON schema, key function signatures)
- Use concrete field names, types, and at least one realistic example instance
- All later tasks must build on these contracts; do not invent ad-hoc structures per task

Add a section before any implementation plan:
> "Core Contracts: Manifest schema(s), key API signatures, and an example manifest instance. All tasks below assume and reuse these contracts."

If tasks require data structures not previously defined: stop, define/extend the schema, then continue.

**5. Shorten the critical path; separate core from ceremony**

Produce two plans:

**Core Plan (v1, small):** The smallest set of tasks that delivers ~80% of the user's value
- Aim for 5-10 tasks
- Focus on: the context/manifest engine, the key analyzers, the main orchestrator skill, minimal policy hooks or gates
- Assume the user can flip a feature flag and live with a sharp cutover if needed

**Extended Plan (optional):** Additional ceremony/features (shadow/canary/parallel modes, dashboards, multi-model, training docs)
- Clearly marked as optional
- Only execute if/when needed

Add explicit sections:
> "Core Plan (minimal v1 to achieve goals)"
> "Extended Plan (optional, only if/when needed)"

**6. Hunt for double systems and missing glue**

As designing:
- Scan for pairs of components that appear to solve similar problems (e.g., two reasoning frameworks, two rule engines) and either merge or remove one
- Scan for integration gaps: components that claim to exist but lack defined contracts (data shape, prompt template, or function signature)
- Fill these gaps before expanding the plan

Add a section:
> "Consolidation & Gaps: Duplicate or overlapping systems I removed or merged. Missing contracts/glue I filled in."

**7. Align tightly with this user's environment and preferences**

Assume:
- Claude Code skills/hooks, terminal-scoped JSON state, no DB, Python and TypeScript code, 50K+ LOC monorepo
- The user is comfortable deleting old skills and aggressively refactoring toward fewer, more powerful components
- Prefer "one powerful engine + slim adapters" over "many overlapping skills"

Add a short "fit check":
> "Environment & Preference Fit: How this design respects solo-dev constraints, Windows 11 + Claude Code hooks, stdlib-only, and aggressive consolidation."

**8. Lean output expectations**

Produce (in order):
1. A concise architecture section
2. Core Contracts (schemas/APIs with examples)
3. Core Plan (minimal v1 tasks)
4. Extended Plan (optional extras, clearly marked)
5. Consolidation & Gaps analysis
6. Environment & Preference Fit note

Do NOT optimize for number of tasks, diagrams, or phases. Optimize for leverage per unit of complexity.

### Usage Guidance

**When to apply:**
- All system design and implementation planning tasks
- Architecture evaluations (ARCHITECTURE_REVIEW path)
- Feature development with architectural implications
- Skill/agent/hook development

**Integration notes:**
- Referenced by all templates during design/planning stages
- Applied in deep.md (Stage 5: Forced Alternatives), fast.md (DEFAULT path)
- Used by /code, /refactor, /cwo when they need architecture guidance

**Key questions this framework answers:**
- Does this design advance the core goals?
- Am I creating duplicate mechanisms?
- What's the minimal v1 without optional dependencies?
- Are my contracts defined before tasks?
- What's the critical path vs ceremony?

---

## CKS Availability Check

**Purpose:** Verify Constitutional Knowledge System (CKS) is accessible before querying.

**Usage:** Include this check in any template that needs to query CKS for historical data.

```python
import sys
from pathlib import Path

# Import cross-platform path resolution
from arch.cross_platform_paths import resolve_cks_db_path

# CKS availability check
CKS_AVAILABLE = False
cks_error_msg = None

try:
    # Verify CKS module exists - use cross-platform path resolution
    cks_src_path = resolve_cks_db_path().parent / "src"
    if not cks_src_path.exists():
        raise ImportError(f"CKS source path not found: {cks_src_path}")

    sys.path.insert(0, str(cks_src_path))
    from csf.cks.unified import CKS

    # Verify CKS database exists - use cross-platform path resolution
    cks_db_path = resolve_cks_db_path()
    if not cks_db_path.exists():
        raise FileNotFoundError(f"CKS database not found: {cks_db_path}")

    # Initialize CKS
    cks = CKS(str(cks_db_path))
    CKS_AVAILABLE = True

except (ImportError, FileNotFoundError, Exception) as e:
    cks_error_msg = str(e)
    CKS_AVAILABLE = False
```

**When CKS is NOT available, display:**

```
CKS_UNAVAILABLE_WARNING

Constitutional Knowledge System (CKS) is not accessible:
{cks_error_msg}

Proceeding with generic analysis without CKS historical data.

Recommendation:
1. Verify CKS installation (check cross_platform_paths.resolve_cks_db_path())
2. Ensure CKS source and database paths exist for your platform
3. Consider installing CKS for evidence-based improvements

Continue with generic analysis? [Y/n]
```

**Integration Note:** This code block is referenced by:
- `fast.md` (Stage 1: Query CKS for Failures)
- `deep.md` (Stage 1: Query CKS for Failures)

---

## Codebase-Aware Analysis (Stage 0.3)

**Purpose:** Before making architectural recommendations, read the actual code being discussed. Prevents recommendations that ignore existing patterns, constraints, or complexity.

**When to Activate:** ANY query that references concrete code, files, modules, or subsystems by name.

### Detection

```
codebase_reference_patterns = [
    # Direct file/module references
    r"(?:improve|optimize|redesign|refactor|harden)\s+(?:the\s+)?(\w+(?:\.\w+)*)",
    # Path references
    r"(?:in|at|from)\s+[/\\]?[\w./\\]+\.\w+",
    # Module/class references
    r"(?:the|our|my)\s+(\w+)\s+(?:system|module|service|class|component|hook|pipeline|router)",
]
```

### Protocol

**Step 1: Identify targets**
From the query, extract file/module/system names.

**Step 2: Discover structure**
```
For each identified target:
    1. Glob("**/[target]*") to find matching files
    2. Read top-level files (first 50 lines each, max 5 files)
    3. Extract: imports, class/function signatures, architectural patterns in use
```

**Step 3: Build context summary**
Before proceeding to analysis stages, create an internal context block:

```
CODEBASE CONTEXT:
- Files examined: [list]
- Current patterns: [e.g., "uses asyncio event loop", "hook-based architecture", "singleton CKS instance"]
- Dependencies: [key imports]
- Constraints: [e.g., "Python 3.14", "Windows paths", "no external HTTP calls"]
- Size: [approximate LOC, file count]
```

**Step 4: Carry forward**
This context MUST inform all subsequent stages. Recommendations that contradict discovered patterns must explicitly justify the deviation.

### Skip Conditions

- Query is purely theoretical ("should I use microservices vs monolith")
- Query is about a greenfield project with no existing code
- User says "hypothetical" or "in general"

**Integration Note:** Referenced by all templates at Stage 0.3 (before Domain Inclusion).

---

## Forced Alternative Quality Gate

**Purpose:** Prevent the common failure mode where "3 alternatives" are actually 3 variations of the same idea.

### Distinctiveness Axes

Each alternative MUST differ from every other alternative on at least ONE of these axes:

| Axis | Examples |
|------|----------|
| **Technology choice** | Kafka vs RabbitMQ vs direct HTTP |
| **Data flow direction** | Push vs Pull vs Event-sourced |
| **Deployment model** | Monolith vs Microservices vs Serverless |
| **Consistency model** | Strong vs Eventual vs CRDT |
| **Communication pattern** | Sync vs Async vs Batch |
| **State management** | Stateful vs Stateless vs Externalized |
| **Scaling strategy** | Vertical vs Horizontal vs Sharded |
| **Coupling approach** | Tight integration vs Loose coupling vs Complete isolation |

### Validation Check

After generating alternatives, verify:

```
For each pair (A, B) of alternatives:
    differences = count axes where A and B differ
    if differences == 0:
        REJECT: "Alternatives A and B are not distinct. They differ only in surface details."
        Regenerate B with a genuinely different approach.
```

### Output Format

Each alternative MUST include a **Differs from others on:** line:

```
### Option B: Event-Driven with Message Queue
**Differs from others on:** Communication pattern (async), State management (externalized), Technology (RabbitMQ)
```

**Integration Note:** Referenced by `deep.md` Stage 5, `fast.md` DEFAULT path, `precedent.md` Part 1.

---

## Confidence Calibration Rules

**Purpose:** Tie confidence scores to evidence quality, preventing unjustified high-confidence recommendations.

### Evidence Tiers

| Confidence Range | Required Evidence | Example |
|-----------------|-------------------|---------|
| **90-100%** | Official documentation + production case study from a named organization | "Kafka handles this at LinkedIn scale (source: engineering blog)" |
| **80-89%** | 2+ web sources confirming the recommendation | "Both AWS docs and Confluent recommend this pattern" |
| **70-79%** | 1 web source OR strong CKS historical evidence | "Our CKS shows this pattern succeeded 3 times internally" |
| **60-69%** | Training knowledge only, but pattern is well-established | "Standard microservices decomposition pattern" |
| **40-59%** | Training knowledge, pattern has known trade-offs | "This could work but has documented failure modes" |
| **Below 40%** | Speculative or novel combination | "Untested in production at this scale" |

### Calibration Rules

1. **No unsupported >80%:** Confidence above 80% without web sources triggers: `⚠️ CONFIDENCE ADJUSTMENT: Downgrading from [X]% to [Y]% — no external evidence found to support this confidence level.`

2. **Research-boosted confidence:** If web research found confirming evidence, confidence MAY increase: `📈 Evidence-boosted: [original]% → [new]% based on [source]`

3. **Conflicting evidence penalty:** If sources disagree, cap confidence at 65% and note: `⚠️ CONFLICTING EVIDENCE: Sources disagree on [topic]. Confidence capped.`

4. **Below 60% warning:** Confidence below 60% triggers: `🔍 CONSIDER DEEPER RESEARCH: Low confidence suggests more investigation before committing to this architecture.`

### Output Format

```
## Confidence: 78%

Evidence basis:
- Web: Python 3.13 docs confirm free-threaded mode is experimental [python.org]
- CKS: 2 prior hook system improvements succeeded with this pattern
- Gap: No production case studies for free-threaded Python at scale

Key assumptions:
1. Team has Python 3.13+ available
2. GIL removal won't introduce race conditions in existing code
```

**Integration Note:** Referenced by `deep.md` Stage 10, `fast.md` confidence output, `precedent.md` confidence section.

---

## Version Verification Rule

**Purpose:** Prevent hallucinated version numbers, API signatures, and deprecation claims. LLMs frequently confabulate specific versions.

### Rule

**ANY of the following claims in /arch output MUST be verified by WebFetch against official documentation before inclusion:**

| Claim Type | Examples | Verification Source |
|------------|----------|---------------------|
| **Version numbers** | "FastAPI 0.115", "Python 3.13", "Kafka 3.7" | Official release notes / PyPI / GitHub releases |
| **API signatures** | "asyncio.Runner()", "click.option()" | Official API docs |
| **Deprecation claims** | "get_event_loop() deprecated in 3.12" | PEP or changelog |
| **Feature availability** | "KRaft mode is default since Kafka 3.7" | Official docs |
| **Performance numbers** | "10x faster than X" | Benchmark source |

### Protocol

```
When about to include a specific version/API claim:
    1. Check: Was this verified during Stage 0.7 (Web Research)?
    2. If YES: Include with source citation
    3. If NO: Either
       a) Run a quick WebSearch to verify, OR
       b) Qualify the claim: "As of training data, [claim] — verify current status"
```

### Never Do

- State a specific version number without source
- Claim an API exists/is deprecated without verification
- Quote performance benchmarks from training data without caveat

**Integration Note:** Applies to ALL templates during output generation. Referenced by Web Research Framework.

---

## Template Chaining

**Purpose:** Allow queries that span multiple domains to benefit from multiple template perspectives.

### Detection

```
chain_patterns = [
    # Explicit: "template=python+data-pipeline"
    r"template=(\w+)\+(\w+)",
    # Implicit: query contains keywords from 2+ domains
    # (detected during Stage 1 domain detection when multiple domains match)
]
```

### When Multiple Domains Match

Instead of using "first match in priority order" (current behavior), when 2+ domains have keyword matches:

1. **Primary template:** The domain with the most keyword matches
2. **Secondary template:** The domain with the next most matches
3. **Merge strategy:** Execute primary template fully, then augment with secondary template's domain-specific concerns

### Merge Protocol

```
1. Load primary template
2. Load secondary template's domain-specific sections ONLY:
   - Domain Resource Inclusion items
   - Stage 0.7 research focus areas (merge search queries)
   - Domain-specific anti-patterns / gotchas
3. Do NOT duplicate: prerequisite checks, IMPROVE_SYSTEM/DEFAULT routing, output format
4. Add header: "Analysis combines [primary] + [secondary] domain expertise"
```

### Explicit Override

```
/arch "build Python ETL pipeline" template=python+data-pipeline
```

This loads `python.md` as primary and injects `data-pipeline.md` domain concerns.

### Limits

- Maximum 2 templates chained (3+ creates incoherent output)
- `precedent` template cannot be secondary (it has unique output format)
- `fast` and `deep` are complexity selectors, not chainable domains

**Integration Note:** Referenced by `SKILL.md` Stage 1 (Classify Intent) and Stage 2 (Select Template).

---

## Output Persistence

**Purpose:** Auto-save /arch outputs so they become searchable by CKS for future architecture decisions, creating a feedback loop.

### Storage Location

```
P:\\\\\\.claude/arch_decisions/
├── YYYY-MM-DD_[template]_[slug].md    # Individual decisions
└── index.jsonl                         # Machine-readable index
```

### Auto-Save Protocol

After the final stage of ANY template execution:

**Step 1: Generate filename**
```python
from datetime import datetime
import re

date = datetime.now().strftime("%Y-%m-%d")
template = selected_template  # e.g., "deep", "fast", "python"
# Slug from first 50 chars of query, sanitized
slug = re.sub(r'[^a-z0-9]+', '-', query[:50].lower()).strip('-')
filename = f"{date}_{template}_{slug}.md"
```

**Step 2: Write decision file**
```markdown
---
date: YYYY-MM-DD
template: [template name]
query: "[original query]"
domain: [detected domain or "generic"]
confidence: [0-100]
research_sources: [list of URLs consulted]
---

[Full /arch output]
```

**Step 3: Append to index**
```jsonl
{"date": "YYYY-MM-DD", "template": "deep", "query": "...", "domain": "python", "confidence": 82, "file": "2026-02-06_deep_improve-hook-system.md"}
```

### CKS Integration

When `/arch` queries CKS during IMPROVE_SYSTEM (Stage 1), it should ALSO search `arch_decisions/index.jsonl` for prior architecture decisions about the same subsystem. This provides:
- What was previously decided and why
- What confidence level the prior decision had
- Whether the prior decision's assumptions still hold

### Skip Conditions

- User says "don't save" or "ephemeral"
- Query was out-of-scope (redirected to another skill)
- Analysis was trivially short (fast template, <2KB output)

**Integration Note:** Referenced by all templates at final output stage.

---

## Adversarial Self-Review (Final Stage)

**Purpose:** After completing the main analysis, systematically challenge the output's weakest points. This is the architectural equivalent of the speculation gate.

### Protocol

After the main analysis is complete but BEFORE presenting to the user:

**Step 1: Identify assumptions**
Re-read the output and list every assumption made (explicit or implicit).

**Step 2: Find the weakest assumption**
Which assumption am I MOST confident about that I HAVEN'T verified? This is the highest-risk blind spot.

**Step 3: Challenge it**
```
For the weakest assumption:
    1. What would happen if this assumption is wrong?
    2. Does the recommendation still hold?
    3. Can I quickly verify it? (WebSearch if possible)
    4. If unverifiable, what's the mitigation?
```

**Step 4: Output**

Add to the end of the analysis:

```
## Adversarial Self-Review

**Weakest assumption:** [the assumption]
**If wrong:** [consequence]
**Mitigation:** [what to do if this turns out to be false]
**Verification status:** [verified by source / unverifiable / partially confirmed]
```

### Review Checklist

| Check | Question |
|-------|----------|
| **Recency bias** | Am I recommending this because it's trendy, or because it's right? |
| **Survivorship bias** | Am I only seeing success stories for this pattern? |
| **Anchoring** | Am I anchored on the first solution that came to mind? |
| **Complexity bias** | Am I recommending something complex because it feels more thorough? |
| **Training data staleness** | Am I citing something that may have changed since training? |

### Skip Conditions

- `fast` template with IMPROVE_SYSTEM path (already CKS-grounded, low risk)
- User explicitly requests speed over thoroughness

**Integration Note:** Referenced by `deep.md` (mandatory), `precedent.md` (mandatory), `fast.md` DEFAULT path (recommended), domain templates (recommended).

**Purpose:** Use WebSearch and WebFetch tools to ground architecture decisions in current best practices, real-world adoption data, and up-to-date library/framework information — rather than relying solely on training data which may be stale.

**When to Research:** ALL architecture queries benefit from research. The depth varies by template:

| Template | Research Depth | Max Searches | Focus |
|----------|---------------|--------------|-------|
| fast | Targeted (1-2 searches) | 3 | Current best practice for the specific pattern/library |
| deep | Comprehensive (3-5 searches) | 8 | Alternatives, trade-offs, real-world post-mortems |
| cli/python/data-pipeline | Domain-focused (2-3 searches) | 5 | Framework versions, breaking changes, migration guides |
| precedent | Evidence-gathering (3-5 searches) | 8 | Industry adoption, case studies, failure reports |

### Research Protocol

**Step 1: Extract Research Queries**

From the user's architecture question, extract 1-5 search queries targeting:

| Query Type | Example | Why |
|------------|---------|-----|
| **Current best practice** | `"[pattern] best practices 2025"` | Training data may reflect outdated consensus |
| **Framework/library status** | `"[library] latest version breaking changes"` | Versions evolve; deprecated APIs cause tech debt |
| **Alternative approaches** | `"[problem] vs [alternative] comparison"` | Forced alternatives are stronger when grounded in real trade-off data |
| **Real-world failures** | `"[pattern] production issues postmortem"` | Pre-mortems are better when informed by actual incidents |
| **Migration/adoption** | `"[technology] migration guide from [old]"` | Realistic effort estimates require real migration stories |

**Step 2: Execute Searches**

```
For each query:
    1. Use WebSearch("[query]") to find relevant results
    2. For the top 1-2 most relevant results, use WebFetch(url) to get full content
    3. Extract: version numbers, trade-offs, gotchas, recommendations
    4. Note the source URL for citation
```

**Step 3: Synthesize into Architecture Context**

Integrate findings into the template's analysis stages. Do NOT dump raw search results. Instead:

- **Cite specific versions** — "FastAPI 0.115+ supports Pydantic v2 natively" not "FastAPI is fast"
- **Cite real trade-offs** — "Team X migrated from monolith to microservices and reported 3x deployment complexity increase (source)"
- **Cite deprecations/changes** — "asyncio.get_event_loop() is deprecated in Python 3.12+; use asyncio.Runner instead"
- **Flag stale assumptions** — If training data suggests X but research shows the landscape has shifted, explicitly flag it

### Research Skip Conditions

Skip web research ONLY when:
- Query is purely about the user's internal system (IMPROVE_SYSTEM + CKS has data)
- User explicitly says "no research" or "offline"
- Query is about architecture of files/code already loaded in context

### Output Integration

Research findings should appear inline in the template output, not as a separate section. Example:

```
## Stage 5: Forced Alternatives

### Option A: Event-driven with Kafka
- Current status: Kafka 3.7 (Jan 2025) added KRaft mode as default,
  eliminating ZooKeeper dependency [source: apache.org]
- Adoption: Used by 80%+ of Fortune 100 for event streaming [source: Confluent 2024 report]
- Gotcha: Consumer group rebalancing still causes latency spikes during scaling events
  [source: Uber engineering blog post-mortem]
```

**Integration Note:** This framework is referenced by:
- `fast.md` (Stage 0.7: Research)
- `deep.md` (Stage 0.7: Research / Stage 5: Forced Alternatives)
- All domain templates via shared framework inclusion

---

## Architecture Graph (Adjacency View)

**Purpose:** Model components, invariants, and decisions as a graph to enable impact analysis, dependency tracing, and multi-terminal safety verification.

**When to Activate:** For non-trivial architecture changes involving multiple components or touching invariants.

### Core Concepts

The architecture graph treats the system as nodes (components, invariants, artifacts) connected by edges (dependencies, affects, implements).

**Node Types:**
- **Modules:** Python files (config.py, routing.py, persistence.py, etc.)
- **Templates:** Markdown templates (fast.md, deep.md, python.md, etc.)
- **Invariants:** Safety constraints (multi_terminal_isolation, no_shared_mutable_state, etc.)
- **Artifacts:** Generated files (arch_decisions/*.md, index.jsonl)
- **External Systems:** CKS, AID_CLI_BINARY

**Edge Types:**
- `depends_on`: Required imports or data flow
- `affects`: Runtime or behavioral impact
- `enforced_by`: What validates/protects this invariant
- `affected_by`: What can violate this invariant

### Current Architecture Graph

```text
# Core modules → dependencies

node: config.py
  depends_on: .archconfig.json, env.VARS
  affects: routing.py, invariant.config_cascade_correctness

node: routing.py
  depends_on: config.py, prerequisite_analyzer.py, persistence.py, CKS, resources/*.md
  affects: template_selection, invariant.multi_terminal_isolation, invariant.template_chaining_rules

node: persistence.py
  depends_on: filesystem.arch_decisions, filesystem.index_jsonl, CKS
  affects: arch_decisions/*.md, .claude/arch_decisions/index.jsonl, invariant.learning_loop_integrity

node: prerequisite_analyzer.py
  depends_on: user_query
  affects: routing.py (gate_decision), invariant.correct_prerequisite_gating

node: aid_wrapper_v2.py
  depends_on: AID_CLI_BINARY, filesystem.codebase
  affects: aid_integration.py, invariant.multi_terminal_isolation  # read-only, must remain safe

node: aid_integration.py
  depends_on: aid_wrapper_v2.py, AID_CONFIG
  affects: template_execution_context, analysis_depth

# Templates and resources

node: resources/fast.md
  depends_on: template_contracts.yaml, evidence_system.md, domain_inclusions.md
  affects: arch_decisions/*.md, invariant.evidence_based_guidance

node: resources/deep.md
  depends_on: template_contracts.yaml, evidence_system.md, domain_inclusions.md
  affects: arch_decisions/*.md, invariant.evidence_based_guidance

node: resources/cli.md
  depends_on: template_contracts.yaml, domain_inclusions.md
  affects: cli_architecture_guidance

node: resources/python.md
  depends_on: template_contracts.yaml, domain_inclusions.md
  affects: python_architecture_guidance

node: resources/data-pipeline.md
  depends_on: template_contracts.yaml, domain_inclusions.md
  affects: data_pipeline_guidance

node: resources/precedent.md
  depends_on: template_contracts.yaml, evidence_system.md
  affects: precedent_based_guidance

# Persistence artifacts

node: arch_decisions/*.md
  depends_on: routing.py, templates, user_query
  affects: index_jsonl, CKS, invariant.decision_auditability

node: .claude/arch_decisions/index.jsonl
  depends_on: arch_decisions/*.md
  affects: search_decisions(), invariant.decision_discoverability

node: .claude/arch_decisions/chaining_usage.jsonl
  depends_on: routing.py (template_chaining)
  affects: chaining_usage_monitoring, invariant.feature_adoption_visibility

# Invariants as nodes

node: invariant.multi_terminal_isolation
  enforced_by: CLAUDE.md, routing_stage_0_1, global_design
  affected_by: routing.py, persistence.py, aid_wrapper_v2.py

node: invariant.no_shared_mutable_state
  enforced_by: module_design, absence_of_globals
  affected_by: config_cache, template_validation_cache

node: invariant.template_chaining_rules
  enforced_by: routing.py (SEC-002)
  affected_by: select_template(), extract_template_override()

node: invariant.config_cascade_correctness
  enforced_by: config.py
  affected_by: .archconfig.json, env.VARS

node: invariant.learning_loop_integrity
  enforced_by: persistence.py, CKS_ingest
  affected_by: save_arch_decision(), _ingest_into_cks()

node: invariant.correct_prerequisite_gating
  enforced_by: prerequisite_analyzer.py
  affected_by: pattern_sets_PRD_DISCOVER_DEBUG

node: invariant.evidence_based_guidance
  enforced_by: templates, evidence_system.md
  affected_by: research_sources, confidence_calculation

# External systems

node: CKS
  depends_on: cks.db
  affects: routing.py (semantic_search), persistence.py (_ingest_into_cks), output_quality

node: AID_CLI_BINARY
  affects: aid_wrapper_v2.py, aid_integration.py, codebase-aware_analysis
```

### Usage Protocol

**For any non-trivial architecture change:**

1. **List touched nodes** - Which components, templates, invariants are involved?
2. **Trace 1-2 hop neighbors** - What else gets affected? (especially invariants)
3. **Propose graph edits** - What new nodes/edges are created? What's removed?

**Example impact analysis:**
```
CHANGE: Add new template domain "go"
TOUCHED: resources/go.md (NEW), routing.py (VALID_TEMPLATES), index.jsonl

1-2 HOP NEIGHBORS:
- routing.py → affects: invariant.template_chaining_rules
- resources/go.md → depends_on: template_contracts.yaml, domain_inclusions.md

INVARIANT CHECK:
- New template must follow SEC-002 (template chaining validation)
- New domain keywords must not conflict with existing domains
```

### Output Format

When recommending architecture changes, include a graph impact section:

```
## Graph Impact

**Nodes Modified:**
- NEW: resources/go.md
- MODIFIED: routing.py (VALID_TEMPLATES set)

**Edges Added:**
- resources/go.md → depends_on: template_contracts.yaml, domain_inclusions.md
- routing.py → affects: resources/go.md (template selection)

**Invariant Check:**
- ✅ multi_terminal_isolation: No shared state introduced
- ✅ template_chaining_rules: "precedent" cannot be secondary, "go" follows same rules
```

**Integration Note:** This framework is referenced by:
- `deep.md` (comprehensive analysis)
- All domain templates (for consistency checks)

---

## Context Contract (Scope Boundaries)

**Purpose:** Explicitly define /arch's context constraints to enable proper rejection/adjustment when the fit is wrong.

### Hard Context Constraints

**Context constraints (hard):**
- Solo developer (not multi-team governance)
- Windows 11 host platform
- CLI-centric workflow (not web application)
- Multi-terminal safety required (constitutional requirement)

**Non-goals (out of scope):**
- Multi-team governance/compliance
- Cloud-native infrastructure design
- Web UX concerns
- Enterprise SLA requirements
- Mobile application architecture

### Input Contract

**What /arch expects as minimal inputs:**

1. **Current repo/workspace description** - What system are we architecting?
2. **Primary value goal(s)** - What matters most for this iteration? (e.g., "speed of iteration", "reliability", "maintainability")
3. **Known constraints** - Hardware, tools, time, budget, technical stack
4. **Risk tolerance** - Mapped loosely to ISO 25010 qualities:
   - Prefer robustness vs speed?
   - Accept experimental approaches?
   - What failure modes are unacceptable?

### When to Reject / Adjust

**Out-of-scope indicators:**
- Query involves multi-team coordination/handoffs
- Architecture dominated by managed cloud services (AWS Lambda, etc.)
- UX and web app concerns dominate over CLI ergonomics
- Enterprise governance/compliance is primary concern

**When out-of-scope detected:**
```
"Your query appears to be outside /arch's optimal scope: [detected pattern]

/arch specializes in: solo-dev, Windows 11, CLI-centric architecture with multi-terminal safety.

Your query suggests: [multi-team governance | cloud-native infra | web UX focus]

Consider:
- [Alternative tool] for cloud-native architecture
- [Alternative tool] for enterprise governance
- Continue with /arch anyway (may produce suboptimal results)

Response: "1" to use suggested alternative, "2" to continue anyway"
```

### Quality Model Mapping

**ISO 25010 Characteristics (solo-dev context):**

| ISO 25010 Quality | /arch Application | Notes |
|-------------------|------------------|-------|
| Maintainability | Clarity of module boundaries, invariants | Not enterprise deployment complexity |
| Reliability | Multi-terminal safety, graceful degradation | Not 99.999% uptime SLAs |
| Performance Efficiency | Routing/validation performance, local ops | Not distributed system latency |
| Security | Local file permissions, CKS access control | Not cloud security, identity management |
| Usability | CLI ergonomics, scriptability | Not GUI/UX, end-user training |

**Cloud Frameworks (analogical use only):**

| Cloud Pillar | /arch Analogical Mapping |
|--------------|-------------------------|
| Operational Excellence | Local ops ergonomics, script repeatability |
| Cost Optimization | Time/complexity/cognitive load reduction |
| Reliability | Multi-terminal isolation, graceful failure |
| Performance Efficiency | Command execution speed, I/O efficiency |
| Security | File permissions, terminal isolation |
| Sustainability | Cognitive load, long-term maintainability |

**Note:** Cloud frameworks are used purely as *analogical lenses* for architectural thinking, not as prescriptive guidance. /arch operates in a local-first, solo-dev context.

**Integration Note:** This framework is referenced by:
- All templates (for scope validation)
- `base.md` (Stage 0: Pre-flight checks)
- `routing.py` (out-of-scope detection)

---

## Tradeoff Clarity Lens (Ninth Lens)

**Purpose:** Every major design choice must explicitly state what it optimizes, what it sacrifices, and under what conditions it might fail.

### Required Output Format

For each major design option, include:

```
### Option [A/B/C]: [Name]

**Primary Lens:** [e.g., Value Optimization | Consolidation | Multi-Terminal Safety Margin]

**Favored Quality/Goal:**
- [Specific quality being optimized]
- [Concrete benefit expected]

**Degraded Quality/Goal:**
- [What's being traded away]
- [Concrete cost/risk]

**Risk Level:** [Low | Medium | High]
**Sensitivity Point:** [Conditions under which this choice fails]

**ISO 25010 Impact:**
- Improved: [Maintainability | Performance | Reliability | etc.]
- Degraded: [Specify which characteristics suffer]
```

### Example

```
### Option A: Shared Memory Cache

**Primary Lens:** Performance Efficiency

**Favored Quality/Goal:**
- Reduced latency (no IPC overhead)
- Simpler deployment (no separate cache service)

**Degraded Quality/Goal:**
- Multi-terminal safety risk (shared state requires careful synchronization)
- Reduced modularity (tight coupling between components)

**Risk Level:** High
**Sensitivity Point:** Fails when concurrent terminals access shared state without proper locking

**ISO 25010 Impact:**
- Improved: Performance Efficiency
- Degraded: Reliability (multi-terminal scenarios), Maintainability (shared state increases complexity)
```

### Enforcement Rules

1. **Every** major option MUST include tradeoff analysis
2. Options that don't differ meaningfully in tradeoffs are rejected (Alternative Quality lens)
3. Risk level must be justified (not just "Low/Medium/High" without reasoning)
4. ISO 25010 mapping must be explicit (not assumed)

**Integration Note:** This framework is referenced by:
- All templates (Stage 5: Forced Alternatives)
- `base.md` (decision path outputs)

---

## When NOT to Use /arch

**Purpose:** Clarify domain boundaries and reinforce that /arch is intentionally lean and focused.

**/arch is NOT appropriate when:**

1. **Multi-team governance/compliance** - Primary concerns involve team coordination, approval workflows, or organizational compliance beyond solo-dev scope
2. **Cloud-native infrastructure** - Architecture dominated by managed cloud services (AWS Lambda, Azure Functions, GCP Cloud Run, etc.) where local-first patterns don't apply
3. **Web UX concerns dominate** - Primary architecture questions are about web application UX, frontend frameworks, or browser-based interactions (vs CLI ergonomics)

**Use /arch FOR:**
- CLI tool architecture and design
- Local Python/Windows application structure
- Multi-terminal safety and state isolation
- Script automation and workflow design
- File system and persistence architecture
- Codebase refactoring and module boundaries
- Local-first data processing (ETL, batch scripts)

**Alternative tools to consider:**
- Cloud architecture: AWS Well-Architected Tool, Azure Advisor
- Enterprise governance: Architecture Decision Record frameworks for teams
- Web UX: Frontend-specific architecture resources

**Integration Note:** This framework is referenced by:
- `SKILL.md` (Usage section)
- All templates (scope validation)

---

## Architectural Lenses (Explicit)

**Purpose:** Make the 8 constitutional lenses explicit and traceable in the codebase and documentation.

### The Eight Lenses

1. **Value Optimization** - Eliminate waste, focus on core goals
   - Primary subsystems: routing.py (template selection), prerequisite_analyzer.py
   - Key invariants: Don't over-engineer for hypothetical future needs

2. **Consolidation** - Merge duplicate mechanisms, avoid parallel rule systems
   - Primary subsystems: routing.py, config.py
   - Key invariants: One authoritative source per concern

3. **Dependency Pruning** - MUST/SHOULD/MAY classification
   - Primary subsystems: config.py, template selection
   - Key invariants: v1 uses only MUST dependencies

4. **Contract-First** - Define schemas before implementation
   - Primary subsystems: persistence.py (decision schema), routing.py (template contracts)
   - Key invariants: All tasks build on shared contracts

5. **Multi-Terminal Isolation** - State safety across concurrent sessions
   - Primary subsystems: ALL (constitutional requirement)
   - Key invariants: No shared mutable state without explicit synchronization

6. **Evidence-Based** - Confidence calibrated to evidence tier
   - Primary subsystems: templates (research integration), persistence.py (CKS integration)
   - Key invariants: Confidence scores require evidence justification

7. **Systems Thinking** - Cross-file understanding, dependency detection
   - Primary subsystems: prerequisite_analyzer.py, routing.py
   - Key invariants: Consider 1-2 hop neighbors before deciding

8. **Alternative Quality** - Options must differ meaningfully
   - Primary subsystems: template validation (SEC-002)
   - Key invariants: No trivial rephrasings as distinct options

### Lens Enforcement in Code

Each subsystem documents which lenses it enforces:

- **config.py**: Lenses [Value Optimization, Dependency Pruning, Contract-First]
- **routing.py**: Lenses [Consolidation, Multi-Terminal Isolation, Systems Thinking, Alternative Quality]
- **persistence.py**: Lenses [Evidence-Based, Multi-Terminal Isolation, Consolidation]
- **prerequisite_analyzer.py**: Lenses [Systems Thinking, Value Optimization]

**Integration Note:** This framework is referenced by:
- This module (shared_frameworks.md)
- Component documentation in review bundle
- SKILL.md architecture overview section
