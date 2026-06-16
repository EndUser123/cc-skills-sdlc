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

## Test Quality (Plan Shape v2)
Every plan that touches testable code MUST include a **Test Quality** subsection. The
[Test Matrix] alone answers "what is tested"; Test Quality answers "is the testing
strong enough to catch real bugs?"

### Required Test Quality fields

1. **Coverage vs Mutation Score** — state explicitly whether the plan targets
   line/branch coverage OR mutation score (or both). Default: both, with mutation
   score as the binding gate.
2. **Mutation score target** — read from `P:/.claude/quality_gates.json` (v1
   schema). Tier `critical` → 80%, tier `standard` → 60%. Do not invent
   thresholds; the JSON file is the single source of truth.
3. **Tool selection** — name the tool (default: `mutmut 3.x`) and the runner
   command. Justify deviations.
4. **Equivalent-mutant budget** — 15% of total mutants per module. Plans touching
   modules with high equivalent-mutant ratios MUST explain how they will be
   resolved (mark as `skipped` with reason, or refactor to remove the equivalence).
5. **Critical-path modules** — list the module IDs from `quality_gates.json` that
   the plan touches. Each gets a binding score target.

### Test Quality template (append to v2 plan)

```markdown
## Test Quality

- **Coverage target:** ≥90% line, ≥85% branch (binding on every changed module)
- **Mutation score target:** 80% for `critical` tier modules, 60% otherwise
  (sourced from `P:/.claude/quality_gates.json`)
- **Tool:** mutmut 3.x with coverage-guided mode, runner `pytest -x --no-header -q`
- **Equivalent-mutant budget:** 15% of total mutants per module
- **Critical-path modules touched:**
  - `skill_guard.breadcrumb.inference` (tier=critical, target=80)
  - `skill_guard.skill_enforcer` (tier=critical, target=80)
- **Waiver policy:** sub-target scores on critical modules require an explicit
  waiver entry in the plan's `Reversal Criteria` section
```

### Failure modes to flag in plan review

- Plan targets coverage but not mutation score → weak testing, flag for revision
- Plan invents a threshold that disagrees with `quality_gates.json` → flag
- Plan touches a critical module but lists no Test Quality section → block
- Plan uses mock-heavy tests as the mutation strategy → flag; mocks are scope-
  limiting by design, they may not exercise the real failure path
