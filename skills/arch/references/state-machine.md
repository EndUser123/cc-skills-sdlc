# State Machine Reference

## States

### Core States

| State | Code | Description |
|-------|------|-------------|
| `ENTRY` | `entry` | Initial state after /arch invocation |
| `PRE_FLIGHT` | `pre_flight` | Running out-of-scope and prerequisite checks |
| `CLARITY` | `clarity_gate` | Running context inference and clarity assessment |
| `CLASSIFY` | `classify_intent` | Detecting intent type, domain, and complexity |
| `CONTRACT_CHECK` | `contract_check` | Classifying contract sensitivity |
| `INVENTORY` | `boundary_inventory` | Inventorying producer/consumer boundaries |
| `CLOSURE` | `boundary_closure` | Closing boundary contracts |
| `PACKETS` | `emit_packets` | Emiting Contract Authority and Planning Handoff packets |
| `CONSISTENCY` | `consistency_check` | Running ADR closure consistency checks |
| `EXECUTE` | `execute_template` | Running the selected template |
| `OUTPUT` | `output` | Producing final ADR or recommendation |
| `PERSIST` | `persist` | Saving to arch_decisions/ |
| `REDIRECT` | `redirect` | Out-of-scope redirect |
| `AWAITING_USER` | `awaiting_user` | Waiting for user input |
| `INCOMPLETE` | `incomplete` | Design has unresolved gaps |

### Error States

| State | Code | Description |
|-------|------|-------------|
| `ERR_CONFIG` | `err_config` | Configuration error (invalid domain, missing required field) |
| `ERR_TEMPLATE` | `err_template` | Template not found or unreadable |
| `ERR_CONTRACT` | `err_contract` | Contract closure failed |
| `ERR_CONSISTENCY` | `err_consistency` | Consistency check failed |

---

## Transitions

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
                    ▼                                             │
   ENTRY ──► PRE_FLIGHT ──► CLARITY ──► CLASSIFY ──► CONTRACT_CHECK
     │            │            │            │            │
     │            │            │            │            ├──► REDIRECT (out-of-scope)
     │            │            │            │            │
     │            │            │            │            └──► INVENTORY (contract-sensitive)
     │            │            │            │                      │
     │            │            │            │                      ▼
     │            │            │            │                 CLOSURE ──► INCOMPLETE (gaps)
     │            │            │            │                      │
     │            │            │            │                      ▼ (closed)
     │            │            │            │                 PACKETS
     │            │            │            │                      │
     │            │            │            │                      ▼
     │            │            │            │                 CONSISTENCY ──► INCOMPLETE
     │            │            │            │                      │
     │            │            │            │                      ▼
     │            │            │            │                 EXECUTE
     │            │            │            │                      │
     │            │            │            │                      ▼
     │            │            │            │                 OUTPUT ──► PERSIST
     │            │            │            │
     │            │            │            └──► ERR_CONFIG (invalid template/domain)
     │            │            │
     │            │            └──► AWAITING_USER (clarification needed)
     │            │                     │
     │            │                     ▼ (user responds)
     │            │                 CLASSIFY
     │            │
     │            └──► REDIRECT (out-of-scope, offer user choice)
     │
     └──► ERR_CONFIG (startup failure)
```

---

## Transition Guards

| Transition | Guard Condition | Fallback |
|------------|----------------|----------|
| `PRE_FLIGHT → CLARITY` | No out-of-scope pattern matched, or user chose to continue | `REDIRECT` |
| `CLARITY → CLASSIFY` | Context inferred OR (purpose + success criteria present) | `AWAITING_USER` |
| `CLARITY → AWAITING_USER` | Context exhausted AND (purpose absent OR success criteria absent) | — |
| `AWAITING_USER → CLASSIFY` | User responded | — |
| `CLASSIFY → CONTRACT_CHECK` | Intent type classified | — |
| `CONTRACT_CHECK → INVENTORY` | Design touches boundary artifacts | `EXECUTE` |
| `CONTRACT_CHECK → EXECUTE` | Design is NOT contract-sensitive | — |
| `INVENTORY → CLOSURE` | All boundaries inventoried | `INCOMPLETE` |
| `CLOSURE → PACKETS` | All boundaries closed | `INCOMPLETE` |
| `PACKETS → CONSISTENCY` | Packets emitted | — |
| `CONSISTENCY → EXECUTE` | Safety policy + router precision + packet consistency pass | `INCOMPLETE` |
| `EXECUTE → OUTPUT` | Template loaded and executed | `ERR_TEMPLATE` |
| `OUTPUT → PERSIST` | Output > 2KB AND not ephemeral | Terminal state |

---

## Terminal States

| State | Description |
|-------|-------------|
| `OUTPUT` | ADR or recommendation produced |
| `REDIRECT` | User redirected to appropriate skill |
| `AWAITING_USER` | Waiting for user input (not terminal long-term) |
| `INCOMPLETE` | Design has named gaps |
| `ERR_*` | Error state with diagnostic |

---

## Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| `stages_executed` | Number of stages completed | 4-9 depending on path |
| `boundaries_invented` | Number of boundaries inventoried | 0 if not contract-sensitive |
| `boundaries_closed` | Number of boundaries fully closed | = boundaries_invented if contract-sensitive |
| `consistency_checks_passed` | Number of consistency checks that passed | 3 if contract-sensitive |
| `template_selected` | Which template was selected | fast/deep/cli/python/data-pipeline/precedent |
| `template_source` | How template was selected | parameter_override/query_override/keyword_detection/default_domain/complexity_detection |
| `clarity_gate_outcome` | Result of clarity gate | context_inferred / clarification_asked / proceeded_directly |
| `contract_sensitivity` | Was design contract-sensitive? | true/false |
| `packets_emitted` | Number of packets emitted | 0-2 (contract authority + planning handoff) |

---

## Error Diagnostics

| Error | Diagnostic Output | Recovery |
|-------|-------------------|----------|
| Config parse error | `ERR_CONFIG: Invalid domain 'X'` | Fall back to next config source |
| Template not found | `ERR_TEMPLATE: Template 'X' not found in resources/` | Block with error |
| Contract ambiguous | `INCOMPLETE: Contract sensitivity classification ambiguous` | Label as needing clarification |
| Boundary incomplete | `INCOMPLETE: Boundary 'X' missing required fields: Y, Z` | Name remaining gap |
| Consistency fail | `ERR_CONSISTENCY: Packet and summary disagree on field X` | Reject ADR draft, require repair |
