# Execution Flow Reference

## Full Execution Flow for `/arch`

### Phase 0: Entry

```
User invokes /arch with query
    │
    ▼
Check for preset expansion
(multi-term, multi-terminal, terminal-isolation
 → expand to standard query)
    │
    ▼
Check for prerequisite gates
(only if gap indicators present)
    │
    ├── Gap detected → suggest prerequisite skill
    │       ↓
    │   Offer: (1) Run suggested skill, (2) Continue with /arch
    │       ↓
    │   WAIT for user selection
    │
    └── No gap → proceed to Stage 0
```

### Phase 1: Pre-Flight and Clarity

```
Stage 0: Pre-Flight Checks
    │
    ├── Self-verification: has gap been confirmed?
    │   └── If ordinal/skill reference → rewrite query with context
    │
    ├── Out-of-scope pattern matching
    │   └── Match detected → redirect to appropriate skill
    │
    └── If out-of-scope detected → offer user choice, WAIT
    │
    ▼ (pass)
Stage 0.5: Clarity Gate
    │
    ├── Step 1: Context Inference
    │   ├── Recent skill invocations? → use as subject
    │   ├── Recent file modifications? → use as subject
    │   ├── Prior architectural discussions? → use as subject
    │   └── Outstanding issues from prior turns? → use as subject
    │       ↓
    │   If context found → infer subject → proceed to Stage 1
    │   If no context → Step 2
    │
    ├── Step 2: Clarification (only when context exhausted)
    │   ├── Purpose present? ✓
    │   ├── Success criteria present? ✓
    │   │   → Both present → proceed to Stage 1
    │   │
    │   └── Either absent → ask ONE clarifying question
    │       → WAIT for answer → proceed to Stage 1
    │
    ▼ (pass)
```

### Phase 2: Classification

```
Stage 1: Classify Intent
    │
    ├── 1. Template override? (template=<name>)
    │   └── Yes → use override, skip detection
    │
    ├── 2. ADF delegation? (extraction/justification queries)
    │   └── Yes → offer /adf vs continue
    │
    ├── 3. Intent type detection
    │   ├── ARCHITECTURE_REVIEW: review + architecture keywords
    │   ├── IMPROVE_SYSTEM: improve + subsystem keywords
    │   └── DEFAULT: everything else
    │
    ├── 4. Domain detection
    │   ├── Config: project → user → env → keywords → complexity
    │   └── Multiple domains → template chaining (max 2)
    │
    └── 5. Complexity detection
        ├── High indicators → deep template
        └── Default → fast template
    │
    ▼
```

### Phase 3: Contract Closure

```
Stage 1.4: Contract Sensitivity Classification
    │
    ├── Touches boundary artifacts? → contract-sensitive
    ├── Pure internal refactor? → NOT contract-sensitive
    ├── Documentation only? → NOT contract-sensitive
    └── Ambiguous → label as needing clarification
    │
    ▼ (if contract-sensitive)
Stage 1.5: Contract Boundary Inventory
    │
    ├── For each boundary:
    │   ├── Name the handoff
    │   ├── Name producer and consumer
    │   ├── Define input/output schemas
    │   ├── Define required vs optional fields
    │   ├── Define freshness authority
    │   ├── Define invalidation trigger
    │   ├── Define isolation boundary
    │   ├── Define failure behavior
    │   └── Define verification/test binding
    │
    ▼
Stage 1.6: Contract Boundary Closure
    │
    ├── For each boundary, close:
    │   ├── Schema id and version chosen
    │   ├── Freshness authority explicit
    │   ├── Invalidation trigger explicit
    │   ├── Transcript-vs-artifact precedence explicit
    │   ├── Failure behavior explicit
    │   ├── Validator owner assigned
    │   ├── Proof owner assigned
    │   └── Contract-to-test binding named
    │
    └── Any boundary incomplete → label design as incomplete
    │
    ▼ (all closed)
Stage 1.7: Contract Authority Packet
    │
    ├── Emit machine-readable packet
    │   └── YAML or JSON, complete shape
    │
    ▼ (if feeding /planning)
Stage 1.7b: Planning Handoff Packet
    │
    ├── Emit planning handoff
    │   └── Tasks already mapped to planning units
    │
    ▼
```

### Phase 4: Consistency and Validation

```
Stage 1.8: ADR Closure Consistency Check
    │
    ├── Safety Policy Gate
    │   └── Contract-sensitive must not default fail-open
    │
    ├── Router Precision Gate
    │   └── Routers must specify activation, bypass, fail behavior
    │
    ├── Packet-to-Summary Consistency Gate
    │   └── Summary tables must derive from authoritative packets
    │
    └── Validator Alignment Gate
        └── Packets must match canonical shapes
    │
    ▼ (pass)
Stage 2: Execute Template
    │
    ├── Template selected (fast/deep/cli/python/data-pipeline/precedent)
    ├── Template loaded from resources/
    ├── Template-specific stages executed
    ├── ADR or recommendation produced
    │
    ▼
Stage 3: Output
    │
    ├── Standard mode: ADR with context/consequences
    ├── Verbose mode (--verbose): Full ADR with all sections
    └── Persistence: Auto-save to arch_decisions/ if > 2KB
```

---

## State Transitions

| From State | To State | Trigger |
|------------|----------|---------|
| `entry` | `pre_flight` | User invokes /arch |
| `pre_flight` | `clarity_gate` | Pre-flight passes |
| `pre_flight` | `redirect` | Out-of-scope detected |
| `clarity_gate` | `classify_intent` | Clarity sufficient or context inferred |
| `clarity_gate` | `awaiting_user` | Clarification needed |
| `awaiting_user` | `classify_intent` | User responds |
| `classify_intent` | `contract_check` | Intent classified |
| `contract_check` | `boundary_inventory` | Contract-sensitive |
| `contract_check` | `execute_template` | NOT contract-sensitive |
| `boundary_inventory` | `boundary_closure` | Inventory complete |
| `boundary_closure` | `emit_packets` | All boundaries closed |
| `boundary_closure` | `incomplete` | Any boundary open |
| `emit_packets` | `consistency_check` | Packets emitted |
| `consistency_check` | `execute_template` | Consistency passes |
| `consistency_check` | `incomplete` | Consistency fails |
| `execute_template` | `output` | Template executed |
| `output` | `persist` | Output > 2KB |

---

## Error Handling by Stage

| Stage | Error | Behavior |
|-------|-------|----------|
| Pre-flight | Config parse error | Fall back to next config source |
| Pre-flight | CKS unavailable | Continue, log warning |
| Clarity gate | Transcript unavailable | Skip context inference, ask clarifying question |
| Classification | Invalid template override | Fall back to complexity detection |
| Contract closure | Ambiguous sensitivity | Label as needing clarification |
| Boundary closure | Incomplete boundary | Label design as incomplete |
| Consistency | Packet shape mismatch | Reject ADR draft |
| Template execution | Template not found | Block with error |
| Persistence | Cannot write to arch_decisions/ | Log warning, continue |
