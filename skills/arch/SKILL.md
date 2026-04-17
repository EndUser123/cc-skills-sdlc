---
name: arch
description: "Adaptive architecture advisor with template-based variants. Auto-routes to appropriate template based on domain and complexity. Supports: fast, deep, cli, python, data-pipeline, precedent. Configuration: .archconfig.json (project) → ~/.archconfig.json (user) → ARCH_DEFAULT_DOMAIN (env var). Override with template=<name> parameter. Enhanced with Graph-of-Thought (GoT) for architecture alternatives analysis (v2.5), Hook Registration Consistency Checking (v5.1)."
version: "5.3"
status: stable
enforcement: advisory
depends_on:
  - sdlc: ">=0.1.0"
category: architecture
triggers:
  - arch
  - architecture
  - architectural decision
  - adf
suggest:
  - /planning
follow_up_offer:
  - /ai-gemini
workflow_steps:
  - preflight_checks
  - classify_intent
  - contract_sensitivity_classification
  - select_template
  - load_template
  - execute_template_analysis
  - contract_boundary_inventory
  - contract_boundary_closure
  - emit_contract_authority_packet
  - adr_closure_consistency_check
  - adr_critic_review
  - generate_architecture_review

governance:
  layer1_enforcement: true
  usage_markers:
    - "Stage 0:"
    - "Stage 1:"
    - "PREREQUISITE DETECTED"
    - "Classify Intent"
    - "Template:"
    - "Out-of-Scope"
    - "Architecture Template"
    - "ARCHITECTURE_REVIEW"
  evidence_requirements:
    - value_assessment: Identify UNIQUE contribution before adding guidance — if existing skills cover ~70%+ with equivalent rigor, marginal value is low
    - codebase_reading: Read relevant files before suggesting changes
    - web_research: Use WebSearch + WebFetch for current best practices
    - framework_docs: Verify framework-specific patterns via /context7 (Next.js App Router, Django 5+, etc.)
    - confidence_scoring: Evidence-tiered confidence calibration
    - adversarial_review: Challenge weakest assumptions
  output_persistence: Auto-save to arch_decisions/
  cross_template_validation: Validate template chaining syntax before execution

---

# Architecture Advisor (Resource Router)

## Overview

This skill routes architecture queries to specialized templates based on domain and complexity. Templates are loaded from `./resources/{template}.md` (relative to project root) and executed inline.

**No Skill() tool calls to arch-* skills.** Templates are read and executed directly.

---

## Context & Scope

`/arch` targets **solo development on Windows 11 with CLI-centric workflows**. Multi-terminal safety is always evaluated. Out-of-scope queries (multi-team governance, cloud infra, web UX, deployment) are redirected.

See `references/scope-and-contract.md` for full scope constraints, input contract, and "when not to use" routing.

---

## Compliance Indicator

**MANDATORY**: When you execute, always start your response with:

`/arch [STANDARD enforcement]`

---

## Constitutional Principles

All architectural decisions MUST evaluate multi-terminal concurrency safety and stale data immunity. Hook design constraints prohibit external API calls and require standalone operation.

For persistence, history, archive, provider, transcript, watermark, multi-terminal, or event-driven designs, `/arch` must also close the stateful contracts explicitly before presenting an implementation-ready recommendation:
- identity model
- ordering contract
- dedupe contract
- freshness/invalidation contract
- event source of truth
- decision-closure status

For any producer/consumer boundary, `/arch` must also close the handoff contract explicitly before presenting an implementation-ready recommendation:
- boundary name
- producer
- consumer
- input schema
- output schema
- required vs optional fields
- freshness authority
- invalidation trigger
- failure behavior
- verification/test binding

For any contract-sensitive design, `/arch` must emit a **Contract Authority Packet** for downstream phases instead of relying on prose alone. The packet is the authoritative closure artifact for `/planning`, `/code`, `/verify`, and `/sqa`.

When `/arch` produces an ADR that is intended to feed `/planning`, it must also emit a **Planning Handoff Packet**. The ADR remains the architecture record, but the planning handoff packet is the authoritative extraction surface for `/planning` so the planner does not have to infer canonical plan sections from ADR prose headings.

When `/arch` writes or revises an ADR, it must also make the packet machine-parseable enough for `arch_validate.py` and downstream validators. If the validator and prose disagree, the validator failure is authoritative until the ADR is repaired.

Authority rules:
- the Contract Authority Packet is authoritative for boundary semantics and closure status
- ADR prose and recommendation prose are explanatory only
- if prose and packet disagree, the packet wins for downstream consumers
- if packet and live source state disagree at runtime, the packet's named freshness authority decides the winner

The packet must contain, per boundary:
- boundary id
- producer
- consumer
- canonical schema id and version
- required fields
- optional fields
- freshness authority
- invalidation trigger
- transcript-vs-artifact precedence
- failure behavior
- validator owner
- proof owner
- downstream consumers

### Schema-First Authority

Structured artifacts (Contract Authority Packets, `.cap.json`,
`.contract-authority-packet.json`, packet sidecar files, explicit schemas) carry
authority. Prose in plans, ADRs, or SKILL.md files is **explanatory and rendered
output only**.

**Rule:** When a structured artifact exists for a boundary, it is the source of
truth. Prose may restate or organize the semantics, but it must not weaken,
replace, or contradict the structured artifact.

**Drift detection:** If prose and a structured artifact disagree, the structured
artifact wins. Update the prose to match, never the artifact.

**Rationale:** Prose can diverge silently across sessions and LLM context resets.
Structured artifacts have machine-checkable schemas. Placing authority in prose
creates invisible drift that `/planning` cannot detect automatically.

`/arch` must also close conflict semantics explicitly before handoff:
- what wins if transcript and artifact disagree
- what happens if freshness is unknown
- what happens on schema mismatch
- what happens on validator timeout
- whether failure is block, reject, degrade, or escalate

Default safety policy for contract-sensitive work:
- unknown freshness -> block and reconstruct from authoritative source
- schema mismatch -> reject and surface incompatibility
- validator timeout -> block or escalate, not fail-open by default
- degrade/fail-open is allowed only when `/arch` names the bounded blast radius and why the degraded path is safe

No contract-sensitive design may be handed to `/planning` without a closed Contract Authority Packet.

If any of those remain ambiguous or intentionally deferred, `/arch` must label the design as incomplete and name the remaining gap instead of presenting it as settled architecture.

When `/arch` is invoked by `/planning` to remediate blockers, `/arch` must return a decision packet rather than editing the plan. That packet should contain:
- chosen identity model
- chosen ordering contract
- chosen dedupe contract
- chosen freshness/invalidation contract
- chosen event source of truth
- chosen isolation boundary
- trigger conditions and invalidating events for each stateful mechanism
- contract-to-test alignment notes for each named contract
- unreachable mechanisms or invariant collisions, if any
- rejected alternatives and why they were rejected

When the caller is `/planning`, `/arch` must treat the call as a nested remediation substep. It must not ask the user whether `/planning` should continue, and it must not tell the user to rerun `/planning`. Its job is to return closure artifacts to the caller.

If `/arch` is nested under `/planning` and architecture closure succeeds, `/arch` should assume automatic return-to-caller. Asking the user whether planning should continue is a workflow error unless `/arch` genuinely cannot close the architecture without new user input.

If the resulting architecture is still intended to flow back into `/planning`, `/arch` must pair that decision packet with a Planning Handoff Packet so `/planning` can rewrite the plan without re-interpreting ADR prose.

`/arch` closes the architecture. `/planning` remains the only writer of the plan artifact.

See `references/constitutional-principles.md` for full evaluation criteria, red flags, and hook design constraints.

## Downstream-Closure Prompts

Before closing an ADR or emitting handoff packets, `/arch` should ask itself:

- What downstream execution semantics must be explicit so `/planning` does not invent them?
- What boundaries here are still named but not operationally closed?
- What would a planner need to know that the ADR currently leaves implicit?
- Where could rollout notes or examples be mistaken for contract authority?
- What packet field would a downstream consumer need in order to avoid guesswork?
- What existing mechanism already overlaps with this proposal, and does the new design replace it, coexist with it, or route around it?
- If a new discriminator or state field is absent in older state, what exact fallback/default behavior occurs?
- Who writes each new hook-visible field, who reads it, and what is the field's provenance and shape?
- What unhappy-path tests prove interruption, malformed state, TTL expiry, backward compatibility, or fallback behavior?
- What prior architecture decision, blocker, or correction most changed what this ADR now needs to close? (`trace`)
- What is the strongest counter-argument, contradictory precedent, or simpler alternative to this design? (`challenge`)

These prompts exist to improve downstream closure, not to reopen settled architecture for its own sake.

These are internal self-check prompts. They are not default prompts to ask the user.

## Trace And Challenge Passes

For architecture-heavy work, `/arch` should treat `trace` and `challenge` as first-class internal passes:

- `trace`: reconstruct the evolution of the design problem across prior plans, ADRs, blockers, and corrections so the final packet closes the actual current problem, not an older version
- `challenge`: pressure-test the preferred design against contradictory evidence, existing mechanisms, simpler alternatives, and downstream ownership conflicts

Use `trace` whenever `/arch` is inheriting unresolved planning blockers or conflicting prior guidance.
Use `challenge` whenever the architecture introduces a new boundary, state mechanism, gate, packet, or fallback contract.

Reference: `P:/.claude/skills/__lib/sdlc_internal_modes.md`

## Strategic Reasoning

This skill uses strategic reasoning patterns from `P:/.claude/skills/__lib/strategic_reasoning.md`:

- **GoT+ToT**: For constraint analysis and branching scenario exploration on architecture alternatives (enabled by default v2.5)
- **Strategic Questioning**: For blind-spot detection before emitting Contract Authority Packets or ADRs
- **Technology Fit**: For validating technology choices against problem domain requirements

Internal blind-spot checks are run before final recommendations.

**When activated:**
- GoT+ToT: All architecture work with multiple viable options or competing constraints
- Strategic Questioning: Contract-sensitive designs, stateful systems, multi-terminal considerations
- Technology Fit: Architecture decisions involving framework/language selection or migration

**Opt-out:** `--no-got-tot` flag to skip Graph-of-Thought and Tree-of-Thought analysis.

## Critique-Agent Review Policy

`/arch` should use a critique agent whenever the architecture closure depends on subtle contract semantics, downstream ownership, or ambiguous fallback behavior.

Critique-agent review is mandatory for:
- contract-sensitive boundaries
- stateful, resumable, multi-terminal, or stale-data-sensitive designs
- routers, classifiers, gates, activation layers, or phased workflows
- ADRs that emit a Contract Authority Packet or Planning Handoff Packet

The critique agent should explicitly challenge:
- whether the packet actually closes the downstream ambiguity
- whether overlap with existing live mechanisms is resolved cleanly
- whether fallback/default behavior is explicit and safe
- whether the proposed test/proof bindings would catch the dangerous failure modes

The critic’s job is to find the hidden contradiction or edge case before `/planning` or `/code` inherit it.

---

## Architectural Lenses & Quality Model

`/arch` applies 8 architectural lenses through the Lean System Design and GoT frameworks. Every option must differ meaningfully from alternatives and articulate tradeoffs explicitly (favored quality, degraded quality, failure conditions, ISO 25010 mapping).

See `references/quality-model.md` for full lens descriptions, ISO 25010 analogical mapping, and Cloud Framework Pillar lenses.

---

## Graph-of-Thought (GoT) Integration (v2.5)

GoT enhancement is **enabled by default** -- extracts architecture nodes, analyzes edge relationships (supports/contradicts/depends), detects circular dependencies, and provides multi-alternative comparison.

**Opt-out**: `export ARCH_NO_GOT=true` or `--no-got` flag.

See `references/got-integration.md` for node types, edge analysis, controller operations, scoring dimensions, and workflow details.

---

## Lean System Design Integration (v4.0)

Lean principles are **applied automatically**: value optimization, extension over creation, dependency pruning (MUST/SHOULD/MAY), contract-first design, core vs extended plans (v1 = 5-10 tasks for ~80% value), environment alignment.

**Opt-out**: `--no-lean` flag.

Full framework: `./resources/shared_frameworks.md`

See `references/lean-system-design.md` for detailed principles and integration notes.

---

## Stage 0: Pre-Flight Checks (Out-of-Scope Detection)

Before routing, check if query is out-of-scope.

### Step 0.1: Quick Preset Expansion

Available presets: `multi-term`, `multi-terminal`, `terminal-isolation` -- all expand to "what's the optimal long term fix in our multi terminal isolation and immune to stale data environment?"

Expansion happens BEFORE out-of-scope checks, intent classification, and template selection.

### Step 0.2: Self-Verification Check

Before suggesting architectural changes, verify the gap actually exists. Required evidence:
1. **Current architecture analyzed** -- Read relevant files
2. **Dependencies mapped** -- Grep for existing patterns
3. **Gap confirmed** -- Evidence that X is actually missing
4. **Data format validated** (MANDATORY when proposed solution will read/process existing data)

   **Trigger condition**: This requirement applies when the proposed architectural solution involves reading, parsing, transforming, or validating ANY existing data format (JSON, YAML, database schemas, API responses, file formats, packet structures, handoff envelopes, resume/restore state, transcripts, etc.).

   **Validation steps**:
   a. **Identify the input data format** — Name the exact data format the solution will read/process.
   b. **Find real examples** — Read at least ONE actual file/database/schema to establish ground truth.
   c. **Map schema/structure** — Document what fields actually exist and their population rates (optional vs mandatory, null vs present).
   d. **Validate assumptions** — Verify each assumption about the data format against real examples.
   e. **Block on assumption mismatch** — If an assumption about the data format is contradicted by real examples, STOP and surface the mismatch explicitly:
      ```
      ASSUMPTION MISMATCH:
      Assumed: {assumed format}
      Actual: {observed format in file:line}
      Impact: {what breaks if we proceed}
      Recommendation: {corrected approach}
      ```

   **Evidence requirement**: At least one file must be read (Read tool or equivalent) to establish ground truth about the data format. Prose alone is insufficient — design decisions based on assumed data formats without verification are prohibited.

   **Output format**: When this requirement applies, output a brief validation summary:
   ```
   Data format validation:
   - Input: {format name}
   - Sample: {file/db examined}
   - Schema: {key fields and their optionality}
   - Assumptions verified: {list}
   - Mismatches found: {list or "none"}
   ```

5. **Hook registration consistency** (MANDATORY when query involves hooks, skills, or workflow systems)

   **Trigger condition**: This requirement applies when the architectural query involves hook systems, skill integration, workflow modifications, or registration patterns.

   **Validation steps**:
   a. **Scan registration sources** — Check `settings.json`, router files (`*_router.py`, `PreToolUse.py`), and modular registries (`UserPromptSubmit_modules/registry.py`)
   b. **Group by event type** — Categorize hooks by event (UserPromptSubmit, PreToolUse, PostToolUse, Stop, SessionStart, SessionEnd)
   c. **Detect pattern violations** — Identify hooks using non-preferred registration patterns:
   - UserPromptSubmit hooks in `settings.json` (should use modular `@register_hook` decorator)
   - PreToolUse/PostToolUse/Stop hooks in `settings.json` (should use router UNIVERSAL/TOOL_HOOKS lists)
   d. **Report inconsistencies** — Surface architectural violations with severity and remediation guidance

   **Registration pattern preferences**:
   ```
   Event Type              | Preferred Pattern      | Allowed Alternative
   ------------------------|-----------------------|----------------------
   UserPromptSubmit        | Modular registry       | None (settings.json deprecated)
   PreToolUse              | Router (UNIVERSAL)     | settings.json for legacy
   PostToolUse             | Router                 | settings.json for legacy
   Stop                    | Router                 | settings.json for legacy
   SessionStart            | settings.json          | None
   SessionEnd              | settings.json          | None
   ```

   **Output format**: When inconsistencies are detected, output a structured report:
   ```
   HOOK REGISTRATION INCONSISTENCY DETECTED

   Event: {event_name}
   Severity: {warning|error}
   Issue: {description of inconsistency}
     • {hook_file_1}
     • {hook_file_2}

   Current registration:
   {current_registration_method}

   Architectural inconsistency:
   • {why this is a problem}

   Recommendation:
   1. {step_1}
   2. {step_2}
   3. {step_3}

   Benefits:
   • {benefit_1}
   • {benefit_2}
   ```

   **Evidence requirement**: Must read actual registration files to verify inconsistencies. Prose claims about registration patterns without file evidence are prohibited.

   **Reference**: See `resources/hook_registration_consistency.md` for detailed detection logic and examples.

**Follow-up Query Rewrite (conditional — only when triggered):**

**IF** the query contains an **ordinal reference** or **skill reference**, rewrite it to be self-contained BEFORE doing any gap detection:

- **Ordinal reference patterns**: "these ideas", "the 5-point list", "idea 2", "points 1 and 3", "that suggestion"
- **Skill reference patterns**: "add to /X", "worth adding to /Y", "does /X already have", "apply to /X"
- **Catch-all** (when in doubt): If the query references something that might have appeared in a prior turn, retrieve and include it

**THEN:**
1. **Retrieve** the prior turn content from the conversation transcript
2. **Rewrite** the query as a fully self-contained prompt: `{current_query}\n\nPrior context: {retrieved_content}`
3. **Verify** the retrieved content actually contains the referenced ideas/skills — if not, revert to original query
4. **Run gap detection on the rewritten query**, not the original

**ELSE** (no ordinal or skill reference detected): Proceed directly to gap detection without rewrite.

**Note**: A query referencing prior conversation content is a retrieval signal, NOT a gap. "I don't have X" is only valid when NO prior turn addressed the referenced skill or ideas.

### Out-of-Scope Patterns

| Pattern | Detected When | Suggest |
|---------|---------------|---------|
| Missing requirements | "from requirements", "no specs loaded", "PRD needed" | `/prd "<source>"` |
| Unknown codebase | First-time context, "how is X structured" | `/discover "<area>"` |
| Debug/diagnosis focus | "why failing", "broken", "error", "crash", "bug in" | `/debug` or `/rca` |
| Planning phase | "how to build", "steps for", "plan to implement" | `/plan` or `/breakdown` |
| Verification focus | "verify", "check my work", "is this correct" | `/verify` |
| Research needed | "how does X work", "learn about", "research" | `/research` |
| Deployment/ship | "deploy", "ship", "release", "production ready" | `/qa` |

### False Positive Prevention

**Do NOT trigger prerequisite gates for:** optimization queries, improvement queries with clear context, architecture decision requests, design pattern questions, **architecture/design REVIEW queries** (reviews are valid even for theoretical designs), **follow-up queries with preceding context** (never reject if preceding turn presented architectural options).

**Rule**: A query referencing prior conversation content (ordinal or skill references) is NOT a gap — it is a retrieval signal. Run the Follow-up Query Rewrite step first.

### If Out-of-Scope Detected

Offer user choice: (1) Run suggested skill, or (2) Continue with /arch anyway. **WAIT for user selection.**

### Step 0.3: Scope Check — Is This an Architecture Decision?

**Before routing to templates, determine if the proposal actually needs architectural analysis.**

This is the ADF pre-flight gate — absorbed from the deprecated `/adf` skill. It prevents over-engineering by distinguishing structural extraction from capability reuse.

**Key question:** Does this proposal **ADD** new boundaries/abstractions, or does it **SHARE/REUSE** existing ones?

| Proposal Type | ADF Applies? | Instead |
|---------------|--------------|---------|
| Extract/split/separate code into new boundaries | ✅ Yes | Continue to Stage 1 |
| Reorganize/restructure existing code | ✅ Yes | Continue to Stage 1 |
| Share existing capabilities more broadly | ❌ No | Evaluate integration ROI directly |
| Give module Y access to module X's tools | ❌ No | This reduces duplication — evaluate ROI directly |
| Add abstraction layer | ✅ Yes | Continue to Stage 1 |
| Remove/consolidate existing code | ❌ No | This reduces complexity — proceed |

**If capability sharing detected:** State `Scope check: This is capability reuse, not structural extraction. Skipping architectural analysis. Proceeding with integration evaluation.` and route to a lightweight integration assessment instead of full ADR workflow.

**If structural extraction detected:** Continue to Stage 1 with the scope confirmed.

---

## Stage 0.5: Clarity Gate

After out-of-scope check passes, call `detect_follow_up_query(query)` and `retrieve_context_hint()` from `routing.py` and apply the decision rule:

```
follow_up = detect_follow_up_query(query)
context_hint = retrieve_context_hint()

IF follow_up.is_follow_up OR context_hint.last_file:
    → Rewrite: "{query}\n\n{context_hint.hint_text}\n\nPrior context: {retrieve_prior_turn_content()}"
    → Proceed to Stage 1 with inferred subject
ELIF recent_turn_has_clear_subject():
    → Infer subject from most recent substantive work
    → Phrase query as self-contained with inferred context
    → Proceed to Stage 1
ELIF purpose_present(query) AND success_criteria_present(query):
    → Proceed to Stage 1
ELSE:
    → Ask ONE clarifying question (not multiple):
      "I want to understand the goal before architecting:
       what's the specific problem you're trying to solve,
       and how will you know it's working?"
    → WAIT for answer → Proceed to Stage 1
```

**Where `detect_follow_up_query()` detects:**
- `ordinal_ref`: "option N", "point N", "idea N", "these/those ideas", "that suggestion"
- `skill_ref`: "add to /X", "does /X already have", "apply to /X"

**Where `retrieve_context_hint()` provides:**
- `last_file`: The most recently read or edited file path
- `last_hook`: The most recently mentioned hook logic
- `recent_paths`: A list of the last 5 paths seen in tool calls

See `routing.py` for the full implementation of these functions.

**Critical constraints:**
- **Context Inference is Mandatory**: You MUST use `context_hint` and the transcript to identify "it", "this", or "that" before asking a question.
- **Evidence-Based Clarity**: If `context_hint` provides a path, assume that is the subject of the architecture query.
- **Follow-up Grace**: A query referencing prior conversation content is a retrieval signal, NOT a gap.
- **Optimization Follow-up Grace**: Short prompts like "what's the optimal solution?", "what's the best approach?", or "what should we do?" inherit the most recent substantive subject by default when the session already contains a live architecture topic, review, or file-reading context.
- **False positive prevention**: NEVER reject a follow-up query where a preceding turn presented architectural options or read a file.

If the immediately preceding substantive work clearly established the subject, asking the user to restate that subject is a workflow error. Infer the active subject, rewrite the query to be self-contained, and continue.

## Stage 1: Classify Intent

### 1. Template Override

If query contains `template=<name>`: use specified template, skip domain detection.

Valid templates: `fast`, `deep`, `cli`, `python`, `data-pipeline`, `precedent`

**Template chaining**: `template=X+Y+Z` -- primary template determines structure, chained templates provide domain context. Validation: all parts must be in allowlist, `precedent` cannot be secondary, `fast`/`deep` are complexity selectors not chainable.

### 2. ADF Delegation

Route to `/adf` when query asks about extraction/justification: "should i extract", "new boundary", "over-engineering", "is X worth it", etc. Offer choice between `/adf` and continuing with `/arch`.

### 3. Detect Intent Type

- **ARCHITECTURE_REVIEW**: review_keyword + (design_keyword or "integration")
- **IMPROVE_SYSTEM**: improve_keyword + subsystem_keyword
- **DEFAULT**: everything else

### 4. Detect Domain

**Priority**: Project config -> User config -> Environment variable -> Keywords -> Complexity

Keyword domains: `cli`, `python`, `data-pipeline`, `precedent` (each with trigger keywords). Multiple matches = template chaining (max 2, no precedent as secondary).

### 5. Detect Complexity

High complexity indicators: "redesign", "overhaul", "architecture", "microservices", "from scratch", "rewrite", "replace", "multi-system", "service boundary", "schema migration", "breaking change"

## Stage 1.4: Contract Sensitivity Classification

Before template execution is considered sufficient, classify whether the target is **contract-sensitive**.

Mark the design as contract-sensitive if it touches any of:

- handoff envelopes
- restore/resume flows
- plan or evidence artifacts
- hook/router payloads
- subagent outputs
- cross-skill outputs
- multi-terminal state
- stale-data invalidation behavior
- ledgers, transcripts, projections, or restore state

Do **not** mark the design as contract-sensitive by default for:

- pure internal refactors with no boundary change
- single-module logic cleanup with no persisted or shared artifact
- isolated test-only changes
- documentation-only changes
- presentational/UI-only changes with no state contract impact
- read-only architectural review that does not propose a new boundary contract

Classification rule:

- default to **not** contract-sensitive unless the design introduces, changes, restores, routes, persists, or relies on a cross-boundary artifact or shared state contract
- if classification is ambiguous, `/arch` must not silently escalate to full packet mode; instead mark the design as needing clarification before calling it implementation-ready

When contract-sensitive:

- Stage 1.5 inventory is mandatory
- Stage 1.6 closure is mandatory
- Contract Authority Packet emission is mandatory
- `/arch` may not present the result as implementation-ready until all required boundaries are closed

When not contract-sensitive:

- `/arch` may still inventory boundaries if helpful, but Contract Authority Packet emission is optional

## Stage 1.5: Contract Boundary Inventory

After selecting the architectural path but before presenting the recommendation, inventory every producer/consumer boundary the design depends on.

This is mandatory for:

- hooks
- handoff envelopes
- restore/resume flows
- plan or evidence artifacts
- subagent result files
- ledgers, transcripts, or projections
- provider-facing state

For each boundary, record:

| Field | Question |
|-------|----------|
| Boundary | What exact handoff is crossing a boundary? |
| Producer | Who emits or writes it? |
| Consumer | Who reads, restores, routes, or executes from it? |
| Input schema | What must exist before the producer runs? |
| Output schema | What does the consumer expect to receive? |
| Required fields | Which fields are mandatory? |
| Freshness authority | Which source wins if data disagrees? |
| Invalidation trigger | What exact event makes this output stale? |
| Isolation boundary | Terminal-private, session-private, or workspace-shared? |
| Failure behavior | What happens when required data is missing or stale? |
| Verification | Which test or trace proves this boundary works end-to-end? |

`/arch` must not accept "the consumer probably has this field" as a valid design assumption.

## Stage 1.6: Contract Boundary Closure

Inventory is not enough. For each contract-sensitive boundary, `/arch` must close the design.

Closure requires:

- producer and consumer are named concretely
- canonical schema id and version are chosen
- required vs optional fields are explicit
- freshness authority is explicit
- invalidation trigger is explicit
- transcript-vs-artifact precedence is explicit
- failure behavior is explicit
- validator owner is assigned
- proof owner is assigned
- contract-to-test/proof binding is named

If any boundary still depends on implied fields, implied freshness, "verified later", or consumer assumptions not backed by a named validator, the architecture remains incomplete.

`/arch` should prefer the smallest contract that closes the boundary safely. Do not add fields, packet sections, or validator requirements that are not necessary for the named boundary to function correctly.

## Stage 1.7: Contract Authority Packet

For contract-sensitive work, `/arch` must emit a Contract Authority Packet as part of the architecture output.

The packet must stay minimal:

- include only fields required for downstream enforcement
- prefer stable identifiers over narrative commentary
- do not duplicate ADR rationale inside the packet
- do not include speculative future boundaries

Minimum shape:

```yaml
contract_authority_packet:
  packet_version: "1"
  contract_sensitive: true
  authority:
    closure_source: "contract_authority_packet"
    prose_role: "explanatory_only"
  boundaries:
    - boundary_id: "resume-envelope"
      producer: "/handoff pre-compact capture"
      consumer: "/handoff restore"
      schema:
        id: "handoff-envelope"
        version: "2"
      required_fields: ["transcript_path", "goal", "current_task"]
      optional_fields: ["active_files"]
      freshness_authority: "transcript_path"
      invalidation_trigger: "new envelope emitted for same scope"
      precedence_rule: "transcript beats stale envelope summary"
      failure_behavior: "reject and surface gap"
      validator_owner: "/handoff"
      proof_owner: "/verify --contracts"
      downstream_consumers: ["/planning", "/code", "/verify", "/sqa"]
```

The packet may be rendered in YAML or JSON, but it must be machine-readable and complete enough for downstream validators to consume directly.

If the work is not contract-sensitive, `/arch` should explicitly say so and omit the packet unless the user requests a contract artifact anyway.

## Stage 1.7b: Planning Handoff Packet

When the output ADR is meant to feed `/planning` for implementation work, `/arch` must also emit a Planning Handoff Packet.

Purpose:

- bridge ADR structure to `/planning`'s canonical v2 plan shape
- prevent `/planning` from shallow-copying ADR headings into legacy plan sections
- make schema rewrite local to `/planning` and architecture closure local to `/arch`

Minimum shape:

```yaml
planning_handoff_packet:
  packet_version: "1"
  source_adr: "P:/packages/example/arch_decisions/ADR-001-example.md"
  plan_title: "Example implementation"
  goal: "What the implementation must achieve."
  current_state_with_evidence:
    - "file.py: current behavior and why it must change"
  design_decisions_and_invariants:
    - id: "DEC-001"
      decision: "Use per-terminal namespace keys"
      rationale: "Prevents cross-terminal cache bleed"
  implementation_changes:
    - task_id: "TASK-001"
      title: "Introduce terminal-scoped cache key"
      scope:
        files: ["cache.py"]
        dependencies: []
      acceptance:
        - "Cache keys differ across terminals for the same query"
  test_matrix:
    - task_id: "TASK-001"
      test_binding: "pytest tests/test_cache.py::test_terminal_isolation"
  contract_authority_reference:
    contract_sensitive: true
    packet_ref: "contract_authority_packet.packet_version=1"
  contract_boundary_matrix_seed:
    source: "contract_authority_packet"
    mode: "derive_from_packet"
  assumptions_defaults:
    - "Windows 11 environment"
  open_questions: []
```

Rules:

- The packet is required whenever `/arch` recommends `INSTRUCTION: Execute skill planning` for implementation work.
- `implementation_changes` must already be mapped into planning task units; do not make `/planning` infer tasks from ADR section names.
- If the design is not contract-sensitive, `contract_authority_reference` must explicitly say `contract_sensitive: false` rather than omitting the field.
- If `/arch` chooses to defer questions, those questions must be emitted in `open_questions`; they must not be hidden only in ADR prose.
- `/arch` must not leave `/planning` to infer whether `Context`, `Design`, or `Consequences` prose should become `Goal`, `Current state`, or `Implementation changes`.
- If `/arch` was invoked by `/planning` during blocker remediation, the packet must be returned in a form the caller can consume immediately, and `/arch` must assume automatic return-to-caller behavior rather than requiring a new user command.
- If the design extends an existing mode, phase, or workflow system, the packet must explicitly state whether the new flow replaces, coexists with, or routes around the existing flow.
- If the design adds a selector or discriminator such as `hypothesis_mode`, the packet must name the discriminator, the selection rule, and the default behavior when the field is absent or false.
- If the design adds or repurposes hook-visible fields, the packet must name who writes them, who reads them, the expected shape, and where the data comes from.
- If downstream logic reads a field like `hypothesis_details`, `/arch` must close its provenance explicitly instead of leaving `/planning` to infer it from prose.
- If the design parses LLM output or free-form text into structured state, the packet must name the minimum valid output, malformed/incomplete-output behavior, and any retry, fallback, or abort rule.
- For stateful or hook-driven extensions, the packet and test matrix must include at least one unhappy-path proof covering interruption, malformed state, TTL expiry, backward compatibility, or fallback behavior.

## Stage 1.8: ADR Closure Consistency Check

Before `/arch` presents an ADR or architecture recommendation as closed, it must run a final consistency pass over the output.

This pass is mandatory for any contract-sensitive design and any ADR that defines routing, validators, packets, or downstream ownership.

`/arch` must reject its own draft ADR if any of these checks fail:

### 1. Safety Policy Gate

- contract-sensitive boundaries must not default to `FAIL-OPEN`
- if degraded or fail-open behavior is allowed, the ADR must name:
  - the exact boundary
  - the bounded blast radius
  - the condition under which degraded mode is entered
  - why the degraded path is safe enough
- vague phrases like "warn only" or "fail-open with warning" are invalid unless explicitly justified as bounded degraded mode

### 2. Router Precision Gate

If the ADR introduces a router, gate, classifier, or activation layer, it must specify:

- activation criteria
- explicit non-activation / bypass criteria
- behavior when classification is ambiguous
- fail behavior when routing cannot determine the correct path

Phrases like "detects patterns" or "routes to validators" are not sufficient closure by themselves.

### 3. Packet-to-Summary Consistency Gate

If a `Contract Authority Packet` or `Planning Handoff Packet` exists, all summary tables, boundary matrices, handoff summaries, and prose summaries must derive from the authoritative packet(s).

`/arch` must reject the ADR as inconsistent if:

- the packet itself does not match the canonical shape required by `/arch`
- required packet sections are emitted at the wrong nesting level
- the packet and summary matrix name different required fields
- the packet and summary matrix name different freshness authorities
- the planning handoff packet and the ADR disagree on task order, named decisions, or whether the work is contract-sensitive
- the planning handoff packet leaves `/planning` to infer canonical plan sections from ADR headings alone
- the packet and summary matrix name different failure behavior
- the packet and summary matrix disagree on producer, consumer, or validator owner
- prose weakens the packet's authority or closure status

When a summary is intentionally compressed, it must still preserve packet truth. Compression is allowed; contradiction is not.

Packet shape validation is mandatory:

- `contract_authority_packet` must be the root packet object
- `packet_version`, `contract_sensitive`, `authority`, and `boundaries` must be nested under it
- each boundary entry must be machine-readable and structurally complete enough for downstream validators to consume directly

### 4. Downstream Contract Alignment Gate

If the ADR assigns blocking/advisory behavior or ownership to downstream skills, `/arch` must verify those claims match the current skill contracts.

At minimum, check alignment against:

- `/planning`
- `/code`
- `/verify`
- `/sqa`

`/arch` must reject the ADR as not closed if it says a downstream rule is advisory, blocking, optional, or owned by a skill in a way that contradicts the actual skill definition.

Evidence freshness is part of downstream alignment:

- if the ADR cites a current file or line as proof of downstream behavior, `/arch` must reread that file state before treating the citation as valid evidence
- stale evidence cannot be used to justify closure
- if the cited line no longer says what the ADR claims, the ADR must be updated or the evidence removed

### Output Rule

If any gate fails, `/arch` must not present the ADR as settled architecture. It must instead:

- mark the ADR draft as inconsistent or incomplete
- name the failing gate explicitly
- repair the ADR before recommending downstream execution

## Stage 1.9: ADR Critic Review

After Stage 1.8 passes, `/arch` should run a narrow critic review before saving or presenting the ADR.

This critic is not a second architecture designer. It is a closure auditor for the defect classes `/arch` is most likely to miss in its own ADR output.

Run `adr_critic_review` automatically when the ADR includes any of:

- a `Contract Authority Packet`
- a `Planning Handoff Packet`
- a router, gate, hook-activation layer, classifier, or routing phase
- multi-terminal, resume, restore, stale-data, transcript, or handoff contracts
- downstream ownership, blocking, advisory, validator, or proof claims

Skip this step for lightweight architecture notes that do not define boundary contracts or downstream enforcement behavior.

### Critic Rubric

The critic must check and block on concrete closure failures only:

1. Safety contradictions
   - conflicting timeout behavior
   - conflicting stale-data behavior
   - conflicting failure behavior between tables, packet, prose, or conflict sections

2. Router closure defects
   - missing activation criteria
   - missing bypass / non-activation criteria
   - missing ambiguous-classification behavior
   - missing failure behavior when routing cannot determine the correct path

3. Packet consistency defects
   - packet shape does not match the canonical schema required by `/arch`
   - required packet sections appear at the wrong nesting level
   - summary matrix drifts from the `Contract Authority Packet`
   - prose weakens packet authority
    - packet and summary disagree on producer, consumer, schema, freshness, invalidation, failure behavior, or owner
    - boundary_id, producer, consumer, and schema id are semantically inconsistent with each other
   - a single boundary merges two different handoff directions or lifecycle stages
   - the Planning Handoff Packet does not map cleanly onto `/planning`'s canonical sections
   - the Planning Handoff Packet forces `/planning` to infer tasks from ADR heading names instead of explicit task units

4. Downstream alignment defects
   - ADR claims about `/planning`, `/code`, `/verify`, or `/sqa` contradict current skill contracts
   - ADR says blocking/advisory/ownership behavior that the owning skill does not actually declare
   - ADR relies on stale file/line evidence to describe current downstream behavior

5. Unresolved closure fields
   - required fields left as `TBD`, `unknown`, `not yet specified`, or equivalent
   - validator owner or proof owner missing on contract-sensitive boundaries
   - boundary listed as in-scope but not actually closed

### Critic Output Rule

If the critic finds a closure defect, `/arch` must not save or present the ADR as settled.

It must:

- identify the failing rubric item
- repair the ADR or mark it as incomplete
- rerun the critic before downstream recommendation

The critic should not block on stylistic preference, alternative architecture taste, or non-material phrasing differences.

### Invoking the Critic

Stage 1.9 invokes `adr_critic` with conditional dispatch:

```bash
python -c "import os; print(os.environ.get('SDLC_MULTI_LLM', '0'))"
```

**If `SDLC_MULTI_LLM=1`** — dispatch via Gemini for a second-model perspective:

```bash
python "P:/packages/ai-cli/skills/ai-cli/ai_cli.py" "You are an ADR closure auditor. Review the ADR provided in the context file against 5 defect classes. Apply the rubric strictly — block only on concrete closure failures, not stylistic preference. The 5 defect classes are: 1) Safety Contradictions (conflicting timeout/stale-data/failure behavior), 2) Router Closure Defects (missing activation/bypass/ambiguous/failure criteria), 3) Packet Consistency Defects (summary drifts from Contract Authority Packet, prose weakens packet), 4) Downstream Alignment Defects (ADR claims contradict current skill contracts), 5) Unresolved Closure Fields (TBD/unknown/missing validators). Output: {review_metadata: {skill, adr_path, defects_found, defects_suppressed, scope}, findings: [{defect_class, severity, location, description, evidence, remediation}], passed_defect_classes, summary}" --context "<adr_path>" --context "P:/.claude/skills/arch/references/gemini-adr-critic-prompt.md" --gemini-only --output-format json --no-critic --timeout 120
```

Parse the JSON output. If valid, use it as the critic result. Write to `P:/.claude/state/adr_critic.json`.

**If `SDLC_MULTI_LLM` is not `"1"` or Gemini dispatch fails** — fall back to Claude haiku:

```python
Agent(
  subagent_type="general-purpose",
  model="haiku",
  prompt=f"""Run adr_critic on {adr_path}

adr_critic is at P:/.claude/agents/adr_critic.md
Read the agent definition first, then execute the review workflow.
Output: P:/.claude/state/adr_critic.json"""
)
```

**Model selection**: Haiku for the fallback — the critic applies a fixed rubric to a known structure; Opus reasoning depth is not required and slows parallelization.

**Blocking behavior**: If `adr_critic` returns `status: "blocked"`, `/arch` must repair the ADR's HIGH severity defects before saving or presenting it.

---

## Stage 1.10: Intelligent Quality Check

After ADR passes critic review, `/arch` automatically triggers `/qr --strategic-only` to validate the architectural decision:

```python
# After ADR is saved and passes critic
Agent(
  subagent_type="general-purpose",
  prompt=f"""Run /qr --strategic-only on the ADR at {adr_path}

This validates the strategic quality of the architecture decision:
- Architecture soundness
- Design pattern appropriateness
- Technology fit
- Engineering balance

Return /rns-formatted findings if any issues are found."""
)
```

**Routing behavior after /qr:**
- If `/qr` returns `Sound` → proceed to Stage 2 (Select Template)
- If `/qr` returns `Concerning` → loop back to architecture revision
- If `/qr` returns `Critical` → recommend `/planning` re-think

**Why automatic?** Architecture decisions deserve strategic quality validation before being presented as settled. This catches issues that the critic (focused on closure) might miss.

---

## Stage 2: Select Template

```
if template_override → use it
elif domain == "cli" → cli
elif domain == "python" → python
elif domain == "data-pipeline" → data-pipeline
elif domain == "precedent" → precedent
elif complexity == "deep" → deep
else → fast
```

## Downstream Routing

When architecture decisions are closed, `/arch` may suggest the next owning skill using **INSTRUCTION format** so the Skill Enforcement Layer recognizes user approval:

- When the design is settled and every contract-sensitive boundary is closed with a Contract Authority Packet:

  ```
  INSTRUCTION: Execute skill planning

  Step 1: Call Skill("planning") to load the planning workflow
  Step 2: Proceed with implementation planning using the closed architecture

  Do NOT treat this as a conversational question — the INSTRUCTION format signals routing approval.
  ```

When `/arch` is nested inside an active `/planning` workflow, do **not** emit the above as a user-facing next step. Instead, return the packet plus a brief caller note such as:

```text
RETURN TO CALLER: /planning
Resume policy: automatic
Caller action: consume packet, rewrite plan, rerun auto_verify
```

- When the user is asking whether an existing design already holds in implementation:

  ```
  INSTRUCTION: Execute skill verify

  Step 1: Call Skill("verify") to load the verification workflow
  Step 2: Verify the implementation against the architecture

  Do NOT treat this as a conversational question — the INSTRUCTION format signals routing approval.
  ```

**Critical format requirement**: Use the INSTRUCTION block format above. The Skill Enforcement Enhancement Layer (v3.5) in UserPromptSubmit.py detects this format and routes user "yes" approval to the specified skill instead of answering as conversational text.

**After presenting an ADR (or closing architecture), always offer any `follow_up_offer` targets from frontmatter as optional review steps.**
`follow_up_offer` is advisory-only and does not change routing or skill ownership.

If a follow-up review finds gaps, ask the user: "Should I update the reviewed document with fixes to address the findings?"

`/arch` closes architecture. It does not write plan artifacts or implementation code.

| Template | Type | Complexity | Output Size | Extends |
|----------|------|------------|-------------|---------|
| base | Shared | N/A | N/A | None |
| fast | Extends base | LOW | ~5 KB | base + minimal |
| deep | Extends base | HIGH | ~15-30 KB | base + GoT + Lean |
| cli | Domain | Any | ~8 KB | base + CLI |
| python | Domain | Any | ~10 KB | base + Python |
| data-pipeline | Domain | Any | ~12 KB | base + ETL |
| precedent | Domain | Any | ~20 KB | base + ADR |

---

## Stage 3: Load and Execute Template

### Template Validation

Validate template name against allowlist. For chains: validate each part, enforce chaining rules (max 2, no precedent as secondary, no fast/deep as chained). Validate file exists and is readable at `./resources/{template}.md`.

### Template Loading

Use Read tool to load template content. Do NOT use Skill() tool.

### Template Execution

1. **Read and understand** the template's execution instructions
2. **Follow** the template's decision tree exactly
3. **Execute** the appropriate path (ARCHITECTURE_REVIEW, IMPROVE_SYSTEM, or DEFAULT)
4. **Return** output in the template's specified format

---

## Execution Flow Summary

See `references/execution-flow.md` for the full execution flow diagram.

See `references/state-machine.md` for full state definitions, transitions, error handling, and metrics.

---

## Routing Contract Table

See `references/routing-contract.md` for input-to-template routing with expected time and output size.

---

## Quick Reference Table

### Domain-Specific Templates

| Domain | Template | Trigger Keywords |
|--------|----------|------------------|
| CLI/POSIX | cli | cli, command line, terminal, shell, posix, exit code |
| Python | python | python, asyncio, type hint, pydantic, fastapi, async |
| Data Pipeline | data-pipeline | etl, pipeline, streaming, kafka, spark, airflow |
| ADR | precedent | adr, decision record, precedent |

### Complexity-Based Templates

| Template | Trigger Keywords |
|----------|------------------|
| fast | Default for simple decisions |
| deep | redesign, overhaul, architecture, microservices, rewrite, multi-system |

---

## Philosophy

- **Constitutional first:** All architecture decisions MUST evaluate multi-terminal isolation (no exceptions)
- **Contract closure, not inventory:** For contract-sensitive work, `/arch` must close boundaries and emit a Contract Authority Packet
- **Domain-first routing:** Domain-specific expertise beats generic complexity
- **Three intent paths:** ARCHITECTURE_REVIEW, IMPROVE_SYSTEM, DEFAULT
- **Review-first:** Architecture reviews valid for theoretical designs -- never gate behind implementation
- **Evidence-grounded:** WebSearch + WebFetch + CKS for current best practices
- **Template-based execution:** Read and execute, don't delegate
- **ADR-first output:** Default output is concise ADR format; `--verbose` for full analysis
- **Edge case awareness:** Every output must document edge cases
- **Compaction resilience:** If a session is compacted mid-ADR, the draft ADR must be saved to `P:/.claude/arch_decisions/` before the compact window closes, so the next session can resume without loss. Auto-save is mandatory for any ADR longer than one exchange.

---

## Template File Locations

```
./resources/
  fast.md, deep.md, cli.md, python.md,
  data-pipeline.md, precedent.md,
  shared_frameworks.md, cks_query_templates.md, evidence_system.md
```

---

## CLI Quick Reference

- **Default output**: ADR format (concise)
- **Verbose mode**: `--verbose` or `-v` for full analysis
- **Template override**: `/arch "query" template=<name>`
- **Template chaining**: `/arch "query" template=deep+python+cli`
- **Quick presets**: `multi-term`, `multi-terminal`, `terminal-isolation`
- **Config**: `.archconfig.json` (project) or `~/.archconfig.json` (user)

See `references/cli-help.md` for full usage examples, configuration options, template chaining examples, and error recovery playbooks.

See `references/adr-and-enhancements.md` for ADR templates, ARCHITECTURE.md guidance, graph-aware reasoning prompts, and version history.

## Decision Sensitivity Analysis

After scoring architecture options, check decision stability:

1. For each adjacent pair (rank N and rank N+1), compute score delta
2. If delta < 2: flag lower-ranked option as `FRAGILE-RANK` (could swap with N+1)
3. Report: `"Option A score 18 vs Option B score 17 (delta=1). If reliability weight shifts ±1, ranking inverts."`

**Red flags:**
- Top 2 options within delta < 2 → decision is noisy, treat as a cluster
- Top option is FRAGILE → note "leading by narrow margin, consider both"

Inspired by decision-matrix sensitivity analysis (weighted criteria close calls).

## Decision Policy Modes

Adjust evaluation weights by decision policy:

| Policy | Reliability Wt | Flexibility Wt | Use When |
|--------|----------------|-----------------|----------|
| `balanced` (default) | 1.0x | 1.0x | General architecture decisions |
| `risk_averse` | 2.0x | 0.5x | After critical incident, before release cut, multi-terminal data safety |
| `exploratory` | 0.5x | 2.0x | During prototyping, exploring alternatives, when stuck on large problems |

Override with: `/arch "query" --policy=risk_averse`

Score formula: `(reliability_score * rel_wt) * (flexibility_score * flex_wt) * GoT_multiplier`

**When to use each:**
- `risk_averse`: Before release, after data corruption incident, when evaluating shared-state changes
- `exploratory`: During backlog grooming, looking for architectural quick wins, evaluating new patterns
- `balanced`: Default for periodic architecture review

---

**Version:** 5.3 | **Architecture:** Template-based router with GoT, ADR-first output, verbose mode, one-page ADR template, graph-aware reasoning, three-path execution (REVIEW / IMPROVE / DEFAULT), Edge Case Integration, Contract Boundary Inventory, Contract Boundary Closure, Contract Authority Packet emission, Planning Handoff Packet emission, Sensitivity Analysis, Decision Policy Modes, Hook Registration Consistency Checking
