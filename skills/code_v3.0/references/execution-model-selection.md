# Execution Model Selection

Choose the lowest-overhead model that can complete the work safely:

- **Standard implementation**: Lead session only (no delegated agents); allowed only for trivial work.
- **Subagents**: Focused delegation in one session (default for most `/build` tasks).
- **Agent team**: Cross-module collaboration with direct teammate coordination.
- **Hybrid**: Agent team for module ownership + subagents for focused verification.

Deterministic triggers:

- Use **subagents** as the default for ALL tasks regardless of scope — subagents are the baseline execution model.
- Use **agent team** when scope is `> 5 files` or `> 2 modules`, when RCA has competing hypotheses, or when ownership spans multiple bounded contexts.
- Use **hybrid** when scope is `> 8 files`, verification load is high, or parallel implementation + parallel review are both needed.
- **Standard implementation is disabled** — subagents are always used even for trivial/local tasks.
- If teams or subagents are unavailable, emulate the same roles sequentially in one session and keep the same evidence requirements.
- If multiple model triggers match, apply precedence: **hybrid > agent team > subagents**.

Routing decision table:

| Condition snapshot | Required model |
| --- | --- |
| Any task with local/sequential scope (`<= 2 files`, `1 module`) | **Subagents** (minimum baseline) |
| Cross-module ownership, competing RCA hypotheses, or scope `> 5 files` / `> 2 modules` | **Agent team** |
| Scope `> 8 files` or parallel implementation + parallel review with high verification load | **Hybrid** |

Default routing policy (speed + correctness first):
- If user passes `--fast`, force fast route unless a hard-risk blocker is detected.
- If user passes `--full`, force full ceremony route.
- If no flag is passed, auto-select the fastest route that preserves correctness:
  - Subagents are the baseline for ALL tasks; escalate to team/hybrid based on scope.
  - Escalate to full route when risk signals exist (cross-module changes, migrations/schema/daemon/core infra, ambiguous RCA, or unclear acceptance criteria).
- Do not optimize primarily for token savings; optimize for elapsed time and correctness confidence.

Phase routing defaults:

- **REQUIREMENTS**: subagents for clarity check; switch to team/hybrid once implementation work begins.
- **EXPLORE**: subagents first; escalate to team/hybrid when triggers are met.
- **TDD**: subagents for ALL tasks (parallel RED dispatch by default); team/hybrid for cross-module tasks.
- **DONE**: reviewer-heavy subagent flow by default; team reviewer only for large/risky changes.
