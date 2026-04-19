# Scope and Contract Reference

## Scope Definition

`/arch` targets **solo development on Windows 11 with CLI-centric workflows**. Multi-terminal safety is always evaluated. Queries focused on multi-team governance, cloud infrastructure, web UX, or deployment are out-of-scope and redirected.

---

## Input Contract

Every `/arch` invocation receives:

| Field | Source | Description |
|-------|--------|-------------|
| `query` | User input | The architecture question or request |
| `transcript` | Conversation history | Prior turns for context inference |
| `cwd` | Environment | Current working directory for path resolution |
| `template` | Optional override | `template=<name>` syntax |
| `config` | `.archconfig.json` → `~/.archconfig.json` → env vars | Domain, output_size, evidence_level |

---

## Out-of-Scope Routing Table

| Pattern | Detected When | Suggest | Rationale |
|---------|---------------|---------|-----------|
| Missing requirements | "from requirements", "no specs loaded", "PRD needed" | `/prd "<source>"` | Architecture without requirements is speculative |
| Unknown codebase | First-time context, "how is X structured" | `/discover "<area>"` | Need codebase understanding before architecture |
| Debug/diagnosis focus | "why failing", "broken", "error", "crash", "bug in" | `/debug` or `/rca` | This is diagnosis, not architecture |
| Planning phase | "how to build", "steps for", "plan to implement" | `/plan` or `/breakdown` | Architecture decided; now needs implementation plan |
| Verification focus | "verify", "check my work", "is this correct" | `/verify` | Implementation exists; needs validation |
| Research needed | "how does X work", "learn about", "research" | `/research` | Knowledge gap, not architecture gap |
| Deployment/ship | "deploy", "ship", "release", "production ready" | `/qa` | Architecture decided; needs release validation |

### If Out-of-Scope Detected

Offer user choice: (1) Run suggested skill, or (2) Continue with `/arch` anyway. **WAIT for user selection.**

---

## When NOT to Use `/arch`

| Scenario | Why Not | Better Alternative |
|----------|---------|-------------------|
| You need a plan with tasks and timelines | `/arch` makes decisions, not plans | `/plan` |
| You need to debug a failure | `/arch` is for design, not diagnosis | `/debug`, `/rca` |
| You need to verify existing code works | `/arch` proposes new architecture | `/verify` |
| You need product requirements | `/arch` assumes requirements exist | `/prd` |
| You need to learn a technology | `/arch` applies technology, doesn't teach it | `/research` |
| You need to ship/release | `/arch` doesn't handle deployment | `/qa` |

---

## False Positive Prevention

**Do NOT trigger prerequisite gates for:**

- Optimization queries with clear context
- Improvement queries with clear scope
- Architecture decision requests
- Design pattern questions
- Architecture/design REVIEW queries (reviews are valid even for theoretical designs)
- **Follow-up queries with preceding context** (never reject if preceding turn presented architectural options)

**Rule**: A query referencing prior conversation content (ordinal references like "option 2", skill references like "add to /plan") is NOT a gap — it is a retrieval signal. Run the Follow-up Query Rewrite step before any gate detection.

---

## Contract Sensitivity Criteria

A design is **contract-sensitive** if it touches any of:

- Handoff envelopes (data passed between skills/phases)
- Restore/resume flows (state recovery after interruption)
- Plan or evidence artifacts (structured outputs consumed by other skills)
- Hook/router payloads (data passed through hook execution chain)
- Subagent outputs (results from Agent tool calls)
- Cross-skill outputs (files read by other skills)
- Multi-terminal state (state shared across terminal sessions)
- Stale-data invalidation behavior (how stale data is detected and handled)
- Ledgers, transcripts, projections, or restore state

**Do NOT mark as contract-sensitive by default for:**

- Pure internal refactors with no boundary change
- Single-module logic cleanup with no persisted or shared artifact
- Isolated test-only changes
- Documentation-only changes
- Presentational/UI-only changes with no state contract impact
- Read-only architectural review that does not propose a new boundary contract

**If ambiguous**: Do NOT silently escalate to full packet mode. Mark the design as needing clarification before calling it implementation-ready.

---

## Contract Authority Packet Rules

When contract-sensitive:

1. **Stage 1.5 inventory** — mandatory: list every producer/consumer boundary
2. **Stage 1.6 closure** — mandatory: close each boundary with explicit field values
3. **Contract Authority Packet emission** — mandatory: machine-readable YAML/JSON block
4. **Implementation-ready gate** — may NOT present result as implementation-ready until all boundaries are closed

When NOT contract-sensitive:

- Boundary inventory is optional (but helpful)
- Contract Authority Packet is optional (emit if user requests)
- State explicitly: "This design is not contract-sensitive" and omit the packet

### Authority Hierarchy

| Artifact | Authority Level | Description |
|----------|----------------|-------------|
| Contract Authority Packet | Authoritative | Definitive boundary semantics |
| Planning Handoff Packet | Authoritative | Definitive planning handoff for `/planning` |
| ADR prose | Explanatory | Context and rationale |
| Recommendation prose | Explanatory | Opinion and reasoning |
| Live source state | Runtime truth | What actually exists on disk |

**Disagreement rules:**
- If prose and packet disagree → **packet wins** for downstream consumers
- If packet and live source disagree at runtime → **packet's named freshness authority** decides the winner
