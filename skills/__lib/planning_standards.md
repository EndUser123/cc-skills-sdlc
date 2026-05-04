# Planning and Decomposition Standards

## Purpose
Ensure implementation plans are concrete, verifiable, and ready for automated execution by skills like `/go` and `/code`.

## No Placeholders (The Iron Law)
A plan is **FAILED** if it contains any of the following:
- "TBD", "TODO", "implement later", "fill in details".
- "Add appropriate error handling" (must show the code or specific rules).
- "Write tests for the above" (without specific test scenarios/code).
- Steps describing *what* to do without showing *how* (code blocks required for code changes).

## Task Granularity
**Each step should take 2-5 minutes for an agent.**
- Write failing test.
- Run test (verify failure).
- Write minimal implementation.
- Run test (verify pass).
- Commit.

## The v2 Plan Shape
Every plan MUST include:
1. **Goal**: One-sentence objective.
2. **Current State**: Concrete evidence (files/lines).
3. **Architecture**: approach summary and invariants.
4. **Implementation Changes**: Per-task blocks using `**TASK-###**`.
5. **Test Matrix**: Binding tests to changes.
6. **Contract Boundaries**: Define producer/consumer for any handoffs.

## Integration Trace (For Multi-Task Plans)
Pick one concrete example query and walk it through all TASKS:
- **What component consumes this output?**
- **Is that consumption defined in the plan?**
If a consumer is missing or undefined, the plan has an **integration gap** and is NOT ready.

## Readiness Levels
- **draft**: Initial structure, may have placeholders.
- **in-review**: Under adversarial review.
- **implementation-ready**: All blockers resolved, concrete code included, integration trace passed.
