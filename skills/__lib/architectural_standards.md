# Architectural and Design Standards

## 1. Constitutional Principles
All architectural decisions MUST evaluate:
- **Multi-Terminal Safety**: Concurrency safety across isolated terminal sessions.
- **Stale Data Immunity**: Mechanisms to detect and invalidate out-of-date state/artifacts.
- **Hook Constraints**: Hooks must be standalone (no external API calls during execution).

## 2. Structured Authority (Schema-First)
Structured artifacts carry authority over prose.
- **Contract Authority Packet (CAP)**: Authoritative source for boundary semantics and closure status.
- **Planning Handoff Packet (PHP)**: Authoritative extraction surface for `/planning`.
- **Precedence**: Structured Artifact > Validator Result > Prose ADR.

### Contract Boundary Closure
A boundary is **CLOSED** only when:
1. Producer and Consumer are named.
2. Canonical Schema ID and Version are chosen.
3. Freshness Authority and Invalidation Triggers are explicit.
4. Failure Behavior (Block/Reject/Degrade) is defined.
5. Test/Proof Binding is assigned.

## 3. Architectural Lenses
Apply these lenses through **Lean System Design** and **Graph-of-Thought (GoT)**:
- **Value Optimization**: Identify unique contributions; avoid adding guidance with low marginal value.
- **Dependency Pruning**: MUST vs SHOULD vs MAY.
- **ISO 25010 Mapping**: Explicitly articulate tradeoffs (Reliability vs Flexibility).

## 4. Verification Gates
### Claim Verification
Before inclusion in an ADR, every technical claim must be verified:
- **Source Analysis**: Read the actual files, do not reason from names alone.
- **API Existence**: Verify prescribed APIs exist in the target framework (e.g., Selenium vs Playwright).
- **Fallback Chains**: Estimate % of requests reaching the component.
- **Timing Constants**: Identify sleep/timeout intervals.

### Temporal Claim Trace
Claims like "before X" or "never called" require a control flow trace:
- Trace to natural boundaries (finally/with/defer blocks).
- Distinguish between normal-path and crash-path bugs.

## 5. ADR Consistency & Critic Rubric
### Safety Policy
- Contract-sensitive boundaries must NOT default to FAIL-OPEN.
- Degraded mode requires a named blast radius and safety justification.

### Critic Checklist
- **Safety Contradictions**: Conflicting timeouts or failure behaviors.
- **Router Defects**: Missing activation/bypass/ambiguity criteria.
- **Packet Drift**: Summary matrix drifting from the CAP/PHP.
- **Downstream Alignment**: Claims about `/planning` or `/code` contradicting their actual skill definitions.

## 6. Strategic Reasoning Patterns
- **GoT (Graph-of-Thought)**: Map nodes and edges for constraint analysis.
- **Strategic Questioning**: Internal blind-spot check before convergence.
- **Weighted Decision Matrix**: Score alternatives against weighted criteria.
