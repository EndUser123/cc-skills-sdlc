---
name: design-v1
description: "Contract-driven decision synthesis. Consumes decision-request.v1 + research-result.v1, produces decision-result.v1 proposed decision."
enforcement: advisory
workflow_steps:
  - id: validate-contracts
    description: "Read and validate the decision-request.v1 and research-result.v1 artifacts."
  - id: synthesize
    description: "Run synthesize() from tools.research_run_v1.design to produce a decision-result.v1."
  - id: validate-output
    description: "Validate the output against the decision-result.v1 schema."
  - id: immutable-write
    description: "Write the result to an immutable path (exclusive create)."
  - id: authority-check
    description: "Verify approval_state is pending or not_required, never approved."
---

# `/design` v1 — Decision Synthesis

## Overview

`/design` v1 is a **thin, contract-driven decision synthesis layer**. It is NOT:

- a research engine;
- a provider router;
- an execution engine;
- an approval authority.

## Inputs

Two validated artifacts must exist before invocation:

1. **decision-request.v1** — captures the decision goal, constraints, options, priorities, and authority.
2. **research-result.v1** — evidence-only output with provenance, claims, and uncertainty.

## Output

A validated **decision-result.v1** artifact with:

- `authority.approval_state`: `pending` (or `not_required` if the request specified no approval requirements).
- `evidence.research_result_refs`: bound to the exact research run IDs and hashes.
- `provenance.hashes`: cross-checked against identity and evidence refs.

## Invocation

```python
from tools.research_run_v1.design import synthesize
from tools.research_run_v1.decision_result import write_result

# Read and validate inputs
request = json.loads(open("decision-request.json").read())
research_result = json.loads(open("research-result.json").read())

# Synthesize
result = synthesize(
    request,
    [research_result],
    request_sha256=hashlib.sha256(
        json.dumps(request, sort_keys=True).encode()
    ).hexdigest(),
)

# Write immutable output
write_result("decision-result.json", result)
```

## Responsibilities

- compare options against research evidence;
- evaluate tradeoffs;
- identify risks;
- summarize implications;
- produce a proposed decision.

## Must preserve

- research ≠ decision;
- evidence ≠ recommendation;
- recommendation ≠ approval;
- decision ≠ execution.

## Must not do

- new providers;
- search routing;
- automatic research;
- Phase 2A;
- agy;
- `/go` integration;
- implementation execution;
- hidden approval.

## Missing evidence

When evidence is insufficient for a confident decision:

- output `confidence: insufficient`;
- list unresolved evidence requirements in `unresolved_questions`;
- set `execution_boundary.blocked_items` to the unresolved questions.
- Do NOT silently run research.

## Authority model

| Field | Writer | Reader | Value |
|-------|--------|--------|-------|
| `decision.selected_option` | `/design` | Human reviewer | Proposed option, not approved |
| `authority.approval_state` | `/design` | Approval gate | `pending` or `not_required` |
| `evidence.research_result_refs` | `/design` | Reviewer | Points to immutable research runs |
| `execution_boundary` | `/design` | Planning/execution | Blocks execution when evidence is incomplete |

The decision owner is copied from the decision request. `/design` never sets `approval_state: approved`.
