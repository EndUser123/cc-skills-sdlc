---
name: planning
description: "Build and verify implementation plans with strict readiness gating. Produces separate artifacts: plan, review results, and findings. A plan cannot be marked implementation-ready while containing placeholders, unresolved blockers, raw review output, implied producer/consumer contracts, or missing required Contract Authority Packet consumption."
enforcement: strict
workflow_steps: ["draft", "verify", "review", "synthesize"]
---
# Plan Workflow v2

## Purpose

Create and verify implementation plans with strict readiness gating.

**Mandatory Standards:** See `__lib/planning_standards.md` for the v2 Plan Shape, No-Placeholder rule, and Integration Trace protocol.

## Implicit-Decision Prompts

Before accepting a draft, `/planning` must challenge itself on:
- Execution ambiguity
- Stale evidence
- Implicit consumer contracts
- Unhappy-path test coverage

See `__lib/planning_standards.md` for the full list of internal prompts.

## Integration Trace (Mandatory for Multi-TASK Plans)

**Purpose**: Catch integration gaps between tasks before coding begins.
**Protocol**: See `__lib/planning_standards.md#integration-trace`.


## Trace, Challenge, And Graduate

`/planning` should use three internal helper passes when the plan is nontrivial:

- `trace`: reconstruct which prior architecture decisions, blockers, or user corrections materially changed the current plan
- `challenge`: pressure-test the plan for hidden execution ambiguity, weak fallback behavior, or downstream guesswork
- `graduate`: identify repeated planning failures that should become durable verifier rules instead of review folklore

Use `trace` when the plan depends on `/design` packets, prior blocker closure, or evolving contract decisions.
Use `challenge` whenever the plan is layered, stateful, hook-driven, or overlap-sensitive.
Use `graduate` when the same class of plan defect appears repeatedly across reviews or verifier failures.

Reference: `P://.claude/skills/__lib/sdlc_internal_modes.md`

## Strategic Reasoning

This skill uses strategic reasoning patterns from `P://.claude/skills/__lib/strategic_reasoning.md`:

- **GoT+ToT**: For constraint analysis and branching scenario exploration when plan has competing alternatives or unresolved blockers
- **Strategic Questioning**: For blind-spot detection before accepting plans as implementation-ready
- **Technology Fit**: For validating technology choices when plan involves framework/language selection

Internal blind-spot checks are run before final recommendations.

**When activated:**
- GoT+ToT: Multi-alternative decisions, constraint-heavy plans, architecture blocker resolution
- Strategic Questioning: All nontrivial plans (stateful, hook-driven, multi-terminal)
- Technology Fit: Plans involving technology stack decisions

**Opt-out:** `--no-got-tot` flag to skip Graph-of-Thought and Tree-of-Thought analysis.

## Orchestration Model

```
Claude assembles draft -> Claude calls auto_verify.py -> if architecture blockers exist, Claude invokes /design
-> Claude rewrites the plan -> Claude dispatches adversarial agents
-> Claude synthesizes changes -> Claude runs Integration Trace -> Claude presents results (plan path + status only)
```

**Claude's responsibilities:**
- Generate initial draft with concrete content (no placeholder scaffolding)
- Call verification scripts when needed
- Invoke `/design` automatically when verification reports architecture-class blockers
- Rewrite the plan itself after consuming `/design` decisions; `/design` must not directly edit the plan
- Treat `/design` as a nested substep of the same `/planning` invocation; after `/design` returns a usable packet, resume `/planning` automatically without asking the user to rerun `/planning`
- Treat any "would you like me to continue /planning?" question after a successful nested `/design` call as a workflow violation; the default is to continue automatically until the plan is rewritten and re-verified
- Dispatch adversarial subagents via Task tool in a single message
- Synthesize accepted findings into a rewritten plan
- Present only the plan path and status -- NOT raw findings

**Tool responsibilities:**
- `auto_verify.py`: Placeholder detection, contradiction checks, disposition checks, plan-purity checks
- `auto_fix.py`: Non-semantic repairs only (header normalization, frontmatter metadata updates, and section ordering only when explicitly requested)
- Custom subagents: Adversarial agents defined in `.claude/agents/`

## Critique-Agent Review Policy

`/planning` should use critique/adversarial agents whenever the draft includes ambiguity classes that are expensive to catch after implementation.

Critique-agent review is mandatory for:
- stateful, hook-driven, multi-terminal, resumable, or stale-data-sensitive plans
- contract-sensitive producer/consumer boundaries
- layered execution policies with selectors, fallback paths, or conditional activation
- plans that extend an existing live workflow or mode system

The critique agents should explicitly challenge:
- overlap with existing mechanisms
- selector/default behavior
- producer/consumer/provenance of new state or artifact fields
- unhappy-path test completeness

Do not treat critique-agent review as optional polish on these plan classes; it is part of closing the execution design before `/code` or `/tdd` consume the plan.

**Remediation boundary:**
- `/design` owns architecture decision closure
- `/planning` owns the plan artifact and all plan rewrites
- `auto_verify.py` decides when the blocker set requires `/design`

**Authoritative precedence:**
- The latest `auto_verify.py` result is authoritative for current blocker state
- The latest `Contract Authority Packet` from `/design` is authoritative for closed boundary semantics on contract-sensitive work
- The latest `Planning Handoff Packet` from `/design` is authoritative for ADR-to-plan extraction when an ADR is the source artifact
- The latest `Planning Source Packet` from a non-ADR source artifact is authoritative for source-to-plan extraction when present
- Current workspace files are authoritative over notes embedded in the plan
- Older review notes, “false positive” commentary, or stale summaries are non-authoritative once verification has been rerun

Readiness is computed, not asserted by prose. If frontmatter, review artifacts, the contract matrix, or the active packet disagree, the validator result wins and the plan must be downgraded until rewritten.

If `next_action.type` is `invoke_arch_then_rewrite_plan`, `/planning` must not debate whether those architecture blockers are “real enough.” It must invoke `/design` with the listed blocker IDs and rewrite the plan from the returned decision packet.

If `next_action.type` is `invoke_arch_then_rewrite_plan`, the `/design` call is a nested remediation subworkflow, not a user-visible handoff. `/planning` remains the active owning workflow and must continue automatically after `/design` returns unless `/design` explicitly leaves the architecture incomplete or requests clarification that cannot be derived locally.

If `/design` emits a `Contract Authority Packet`, `/planning` must consume it as authoritative for boundary semantics. The plan may restate or organize those semantics, but it must not weaken, replace, or contradict them.

If `/design` emits a `Planning Handoff Packet`, `/planning` must consume it as authoritative for canonical section mapping. `/planning` must not shallow-copy ADR headings like `Context`, `Design`, or `Consequences` into the plan. It must rewrite the plan into the v2 plan shape using the packet's mapped fields.

If the source is not an ADR but does include a `Planning Source Packet`, `/planning` must consume that packet as authoritative for intake normalization. Unstructured notes, transcripts, solution writeups, and similar source material must be normalized into the v2 plan shape from the packet or from an explicit extraction map before readiness checks are interpreted as architecture blockers.

For stateful/history/provider/multi-terminal plans, `/planning` must reject drafts that leave identity, ordering, dedupe, invalidation, event-source, or isolation-boundary decisions ambiguous. It must also reject plans whose tests contradict those contracts or whose freshness/replay/invalidation mechanics cannot actually fire under the stated invariants. Those are readiness gates, not polish issues.

For extensions to existing stateful or hook-driven systems, `/planning` must also reject drafts that:

- add new modes/phases/flags without stating how they coexist with or replace overlapping existing flows
- add new persistent or hook-visible fields without naming who writes them, who reads them, and what happens when the field is absent in older state
- change selector logic (mode/phase/iteration routing) without naming the discriminator and fallback/default behavior
- bury logic for one component inside a different component's change block
- reference helper functions, formatters, or parsers without stating whether they already exist or will be implemented
- rely on parsing model output into structured state without defining validation, retry, or fallback behavior
- let assumptions/defaults contradict the declared schema or data shape
- cover only happy-path tests and omit interruption, malformed-state, TTL, backward-compatibility, or fallback scenarios

For plans with hooks, handoff envelopes, restore artifacts, ledgers, evidence files, subagent outputs, or any other producer/consumer boundary, `/planning` must also reject drafts that leave these ambiguous:

- producer
- consumer
- input schema
- output schema
- required fields
- freshness authority
- invalidation trigger
- failure behavior
- contract-to-test mapping
- contract authority source when `/design` marked the boundary contract-sensitive

Those are readiness gates, not polish issues.

`/planning` must also reject drafts that:

- cite explicit file or line evidence that does not exist in the current workspace
- introduce numbered layers/tiers without stating whether each layer is blocking, advisory, optional, fallback-only, or always-on
- use conditional phrases like `only if needed`, `if insufficient`, or `when necessary` without defining the trigger signal or threshold

Those are architecture/execution-semantics blockers, not reviewer preference.

## Routing Behavior

`/planning` auto-invokes `/design` for architecture-class blockers because that is a hard gate.

`/planning` may suggest:

- `/pre-mortem` when the plan is risky, stateful, or hard to reverse
- `/code` only when the plan is actually implementation-ready and any required `Contract Authority Packet` has been consumed

`/planning` owns the plan artifact and must not offload plan writing to downstream skills.

When routing or remediation is required, `/planning` must emit a numbered `✅ RECOMMENDED NEXT STEPS` section instead of leaving the user with a generic "go use `/design`" handoff. The section must name the owning skill, the reason, the exact apply action, the proof action, and a `0` option for applying the full set in dependency order.

## Quick Start

```
/planning "implement X"
```

Claude will:
1. Generate a concrete plan draft (no placeholder content)
2. Run deterministic verification
3. If architecture blockers are found, invoke `/design`, then rewrite the plan and re-verify
4. Launch adversarial review agents automatically
5. Synthesize findings into a rewritten plan
6. Present the plan path and status

If the final result is still blocked, routed, or below `implementation-ready`, `/planning` must also present numbered Recommended Next Steps so the user can choose `1`, `2`, etc., or `0` to apply all.

## Commands

| Command | What It Does |
|---------|--------------|
| `/planning "do X"` | Create draft, run verification, adversarial review, synthesize, present results |
| `/planning <path>` | Create plan from ADR/topic, run full workflow |
| `/planning build "do X"` | Create draft only, skip verification (manual control) |
| `/planning review` | Re-verify existing plan (path inferred from context) |
| `/planning review <path>` | Re-verify specific plan |

## Context-Aware Behavior (When No Topic Provided)

When invoked without a topic argument (e.g., just `/planning`):

1. **Read pre-injected conversational context** -- The `[CONVERSATIONAL CONTEXT]` block at the top of the prompt (injected by the UserPromptSubmit hook) provides detected skills and topics from prior conversation.
2. **Check for existing plans related to inferred topic** -- if a plan exists that matches the detected context, use it
3. **If exactly one candidate** -- use it automatically
4. **If multiple candidates OR no conversational context** -- ask user to specify
5. **Resume from appropriate phase**:
   - If plan exists and `draft` -> continue from verification
   - If plan exists and `in-review` -> continue from adversarial review
   - If plan exists and `implementation-ready` -> offer to proceed to implementation

**Context inference (for /planning without arguments):**
- Context is pre-injected by the UserPromptSubmit hook via `[CONVERSATIONAL CONTEXT]` block
- Detected skills and topics come from the hook's transcript analysis
- The hook computes context before skill execution, so no direct transcript reading needed

## ADR-Aware Behavior

When invoked with an **ADR file path** (e.g., `/planning path/to/ADR-002-chs-consolidation.md`):

1. **Detect ADR format** -- filename patterns: `ADR-XXX`, `XXX-title`, `arch_decisions/` directory
2. **Load planning handoff first** -- if the ADR contains a `Planning Handoff Packet`, use it as the authoritative extraction surface
3. **Generate draft** -- map ADR or handoff content into canonical plan format, but mark as `draft` until concrete tasks replace scaffolding
4. **Never mirror ADR headings directly** -- `Context`, `Design`, `Consequences`, `Dependencies`, or `Implementation Sequence` are source material, not valid plan section names
5. **Create separate plan file** -- `~/.claude/plans/plan-adr-XXX-title.md`
6. **DO NOT merge findings into the plan artifact**

## Source-Aware Behavior

When invoked with a non-ADR source artifact such as solution notes, a transcript, a design memo, or an unstructured writeup:

1. Detect whether the source contains a `Planning Source Packet`
2. If present, use it as the authoritative extraction surface
3. If absent, build an explicit extraction map first, then write the plan from that map
4. Never mirror arbitrary source headings directly into the plan
5. Treat malformed first-draft normalization as local `/planning` rewrite work, not as `/design` proof

### Source-to-Plan Mapping Contract

For non-ADR sources, preferred input is:

- `Planning Source Packet` embedded in the source artifact

Fallback input when no packet exists:

- build an explicit extraction map first, then write the plan from that map

The extraction map must cover:

- `Goal`
- `Current state with evidence`
- `Design decisions and invariants`
- `Implementation changes`
- `Test matrix`
- `Contract authority reference`
- `Contract boundary matrix`
- `Assumptions/defaults`
- `Open questions`

### ADR-to-Plan Mapping Contract

For ADR-sourced plans, `/planning` must produce the v2 plan shape from a stable mapping, not from heading copy-through.

Preferred input:

- `Planning Handoff Packet` from `/design`

Fallback input when no packet exists:

- build an explicit extraction map first, then write the plan from that map

The extraction map must cover:

- `Goal`
- `Current state with evidence`
- `Design decisions and invariants`
- `Implementation changes`
- `Test matrix`
- `Contract authority reference`
- `Contract boundary matrix`
- `Assumptions/defaults`
- `Open questions`

`/planning` must not treat a malformed first draft as an `/design` problem merely because the source was an ADR. If the issue is that the draft does not match the canonical plan schema, `/planning` must repair the draft locally before deciding whether any remaining blockers truly belong to `/design`.

## Verification Workflow (Steps 1-4)

Steps 1-4 cover draft generation, discovery, auto_verify checks, and auto_fix scope.

**Step 1**: Generate a concrete draft with actual content, NOT placeholder scaffolding.
**Step 1.5 (Discovery)**: Search codebase for existing implementations of proposed components to catch duplicates before expensive verification. Extract class names from Implementation Changes and search for existing definitions.
**Step 2**: Run `auto_verify.py` for deterministic checks (placeholders, contradictions, dispositions, plan-purity, explicit file/line evidence, execution semantics, and state-model contract closure for applicable plans). Includes DUPLICATE-001 check for redundant component proposals.
**Step 2.5**: Run contract boundary check for producer/consumer artifacts and handoffs.
**Step 3**: Run `auto_fix.py` for non-semantic repairs only (headers, metadata, and ordering only when explicitly requested).

See `references/verification-workflow.md` for full details on each check and what auto_fix does/does not do.

### Graduated Validation Modes

Not every plan edit requires a full verification pass. `/planning` uses three graduated modes:

| Mode | Trigger | What Runs |
|------|---------|-----------|
| **Light** | Normal prose/task edit (no status change) | Structural checks only: malformed frontmatter, missing required sections, unresolved `[TODO]`/`[TBD]` markers |
| **Readiness** | Status set to `implementation-ready`, or explicit `/planning review` | Full `auto_verify.py`: placeholders, contradictions, dispositions, plan-purity, explicit file/line evidence, execution semantics |
| **Contract** | Plan contains CAP or contract boundary matrix markers | All Readiness checks + per-row packet refs, test bindings, authority drift detection |

**Rules:**
- Light mode never produces a `READY` verdict — it may flag structural issues but cannot advance status.
- Readiness mode is the minimum gate for advancing to `implementation-ready`.
- Contract mode activates **automatically** when the plan references any `Contract Authority Packet` or contains a contract boundary matrix. It is not opt-in.
- `/planning review` always runs at Readiness mode at minimum, regardless of plan content.

`auto_verify.py` also treats stale sibling review artifacts as non-authoritative. If an existing `.review.summary.md` contradicts the latest verification result, `/planning` must treat it as stale and regenerate it rather than debating which artifact is true.

### Nested `/design` Resume Contract

When `/planning` invokes `/design` because `next_action.type == invoke_arch_then_rewrite_plan`:

1. `/planning` stays the owning workflow.
2. `/design` is a nested closure substep, not a terminal handoff.
3. User re-entry is not required.
4. `/planning` must resume automatically after `/design` returns a usable packet.
5. **DO NOT ASK the user whether to continue** — Immediately consume the packets and rewrite the plan. Only ask if `/design` returned an unresolved clarification need or an incomplete architecture state.
6. The transition from `/design` back to `/planning` is automatic. Do not treat it as a user-visible handoff.

## Blocker Remediation Loop

When `auto_verify.py` returns architecture-class blockers, `/planning` must:
1. Extract the blocking findings and relevant plan excerpts
2. Invoke `/design` automatically to close the architecture decisions
3. Require `/design` to return a decision packet, not plan edits
4. Resume `/planning` automatically in the same workflow after `/design` returns
5. Rewrite the plan itself using that decision packet
6. Remove any now-resolved open questions
7. Re-run `auto_verify.py`

**Architecture-class blockers that should route to `/design`:**
- `contract_ambiguity`
- `state_model`
- `schema_consistency`
- `identity_boundary`
- `contract_test_coherence`
- `mechanism_triggerability`
- state-model `open_questions` findings that leave source-of-truth, ordering, dedupe, invalidation, or event-source decisions unresolved
- `boundary_contract_ambiguity`
- `artifact_schema_gap`
- `consumer_validation_gap`

**Do NOT invoke `/design` for:**
- placeholders
- missing sections
- malformed frontmatter
- RTM/acceptance-criteria gaps
- raw review output merged into the plan
- shallow ADR-to-plan transcription errors
- shallow source-to-plan transcription errors
- legacy ADR headings copied directly into the plan
- arbitrary source headings copied directly into the plan
- reduced contract matrix shape caused by planner extraction instead of architecture ambiguity

**Execution rules for simpler LLMs:**
- Always rerun `auto_verify.py` before reasoning about blocker state
- Treat `next_action` as the workflow controller, not as advisory commentary
- If `next_action.resume_policy` is `automatic_return_to_caller`, do not ask the user to rerun `/planning`; continue the same workflow automatically
- If the plan or sibling artifacts changed since the last verification run, discard the previous blocker model and rerun verification
- When both architecture blockers and artifact/status blockers exist, resolve the architecture blockers first, then rerun verification, then clean up the remaining artifact/status blockers
- Do not create workaround notes arguing a verifier finding is a false positive; either satisfy the contract or escalate to `/design`

## Adversarial Review (Step 4)

### Step 4a: Pre-create per-plan findings directory with terminal isolation

```bash
# Create the per-plan adversarial workspace and emit explicit resolved paths.
# Do NOT dispatch agents until you have a concrete findings_dir and concrete
# findings_path values for each agent. Raw {sanitized_plan_name} placeholders are unsafe.
python -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(r'P://packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/planning/__lib')))
from adversarial_review import prepare_adversarial_review_context

context = prepare_adversarial_review_context(sys.argv[1])
print(json.dumps(context.as_dict(), indent=2))
" '${PLAN_PATH}'
```

**Note**: Adversarial root defaults to the project artifacts tree (`P:/.claude/.artifacts/adversarial/<plan_name>/<terminal_id>/`), or the `CLAUDE_ADVERSARIAL_ROOT` env var if set. Findings stay out of `~/.claude/plans/` and out of the repo root. `auto_verify.py` searches this same tree, so verification and resume/retry continue to find the findings.

**Dispatch contract**:
- Step 4a must produce a concrete `findings_dir` and concrete `findings_paths[agent]` values
- Step 4b must build prompts from the canonical helper in `__lib/adversarial_review.py`, not from handwritten prompt assembly
- If any prompt still contains `{sanitized_plan_name}`, `<findings_dir>`, or `<findings_path>`, stop and fix the prompt instead of dispatching

### Step 4b: Dispatch adversarial agents in TWO phases

**CRITICAL**: Use the canonical dispatcher helper instead of hand-built prompts:

```python
from adversarial_review import build_dispatch_specs

phase1_specs = build_dispatch_specs(context, phase="phase1")
critic_spec = build_dispatch_specs(context, phase="critic")[0]
```

`build_dispatch_specs(...)` is the only supported path because it:
- loads the prompts from `references/adversarial-agent-prompts.md`
- applies only the allowed substitutions (`<plan_path>`, `<findings_dir>`, `<findings_path>`)
- rejects unresolved tokens before dispatch
- binds each agent to the exact per-plan, per-terminal findings path expected for retry/resume

Do not paraphrase or improvise the prompts. The idempotency checks, explicit paths, and field names must stay intact for the retry protocol to work.

**Phase 1 — Parallel dispatch (5 agents)**:
Dispatch all 5 non-critic agents in ONE message using the canonical specs from `build_dispatch_specs(context, phase="phase1")`.

Each agent writes findings to file and returns ONLY the path. Each agent checks: if output file exists, skip and return path immediately.

The 5 phase-1 agents are: `adversarial-compliance`, `adversarial-logic`, `adversarial-testing`, `adversarial-security`, `adversarial-failure-modes`.

**IMPORTANT — File naming**: The reference prompts write to `{agent}-findings.json` (e.g., `compliance-findings.json`, `logic-findings.json`). Do NOT use `adversarial-{agent}.json` naming.
**IMPORTANT — Path safety**: Never dispatch a prompt that still contains `{sanitized_plan_name}`. That means Step 4a output was not consumed, and agents may write into the shared root or stale plan directory.
**IMPORTANT — Return-path safety**: If an agent returns any path other than its exact `findings_paths[agent]` value from Step 4a, reject it as invalid. Do not accept root-level `P://.claude/plans/adversarial/*.json` outputs as valid idempotent results.

**Phase 1 Slot 5 — External LLM (conditional)**:

After dispatching the 5 Claude agents, check `SDLC_MULTI_LLM`:

```bash
python -c "import os; print(os.environ.get('SDLC_MULTI_LLM', '0'))"
```

If `"1"`, dispatch DeepSeek adversarial via Bash (not Agent tool). Follow the Slot 5 instructions in `references/adversarial-agent-prompts.md` (Section: "Slot 5: External LLM Adversarial"). The critic agent reads all `*-findings.json` from `findings_dir`, so `deepseek-adversarial-findings.json` is automatically ingested.

If not `"1"` or the dispatch fails, skip — the 5 Claude agents provide full adversarial coverage.

**After Phase 1 completes**: Record stage checkpoint:
```python
# Write stage file: adversarial-findings-complete
base / 'workflow_stage.json' → {"stage": "step_4b_phase1_done", "agents": [...]}
```

**Phase 2 — Series dispatch (critic agent)**:
After Phase 1 agents complete and their findings are available, dispatch the critic agent using `build_dispatch_specs(context, phase="critic")`.

The critic's role is to evaluate the consensus from the 5 phase-1 agents. Running the critic in series (after the others) allows it to review all findings and identify blind spots, consensus gaps, and contradictions.

**After critic completes**: Record stage checkpoint:
```python
base / 'workflow_stage.json' → {"stage": "step_4b_critic_done"}
```

**Stage checkpoint on compaction**: If session compacts during dispatch, read `workflow_stage.json` to determine where to resume:
- `step_4a`: re-run step 4a, then dispatch agents
- `step_4b_phase1_done`: validate canonical findings files under `findings_dir`, then re-run Phase 1 only for missing/invalid agents
- `step_4b_critic_done`: skip to synthesize

### Step 4c: Synthesize

After collecting findings, Claude must:
1. Read all findings files
2. Produce a consolidated change list -- NOT content to paste into the plan
3. Rewrite the plan incorporating accepted findings
4. Remove stale steps flagged by reviewers
5. Rerun auto_verify to confirm `implementation-ready` or identify remaining blockers
6. Write findings to `*.review.findings.json`
7. Write summary to `*.review.summary.md`

**Scaffolding isolation:** Adversarial findings are evidence about the plan, not plan content. Never merge raw findings, reviewer scaffolding, or diagnostic output directly into the plan artifact. The plan body must contain only assistant-authored implementation content validated against the v2 plan schema. Scaffolding blocks (ownership checks, test strategy headers, cognitive guardrails) that appear in findings or reviewer output are not findings and must not appear in the plan.

See `references/artifact-contract.md` for disposition table format required in `*.review.summary.md`.

## Step 5: Present Results

If the plan is `implementation-ready`, present ONLY:
- Plan artifact path
- Status: `draft` | `in-review` | `implementation-ready`
- Unresolved blocker count
- Summary of changes made (not raw findings)

```
plan: C:\Users\brsth\.claude\plans\plan-name.md
status: implementation-ready
unresolved_blockers: 0

Changes incorporated: 4 findings accepted, 2 rejected with rationale, 1 deferred to follow-up.
```

**After presenting results, always offer any `follow_up_offer` targets from frontmatter as optional review steps.**
`follow_up_offer` is advisory-only and does not change routing or skill ownership.

If the plan is blocked, routed to `/design`, or otherwise below `implementation-ready`, present the same summary plus:

```md
## ✅ RECOMMENDED NEXT STEPS

1 (/design|/planning|/code|/verify) - Short action title
  Owner: `/design` | `/planning` | `/code` | `/verify`
  Why: Concrete reason this step is needed.
  Apply: Exact change or command to perform.
  Proof: Exact validation that confirms the step worked.

2 (...) - ...

0 - Apply ALL Recommended Next Steps
```

Example:

```md
plan: C:\Users\brsth\.claude\plans\plan-name.md
status: in-review
unresolved_blockers: 3

## ✅ RECOMMENDED NEXT STEPS

1 (/design) - Close stale CAP semantics for `plan-artifact`
  Owner: `/design`
  Why: The active packet drifts from current `/planning` readiness semantics.
  Apply: Reinvoke `/design` to revise the `plan-artifact` boundary and return an updated Contract Authority Packet.
  Proof: Re-run `/planning review` and confirm packet alignment is `Exact match to CAP`.

2 (/planning) - Repair matrix schema
  Owner: `/planning`
  Why: Required contract-boundary fields are missing from the plan artifact.
  Apply: Add per-row `Contract authority packet` and `Test binding` entries to the matrix.
  Proof: `auto_verify.py` returns no matrix-schema findings.

3 (/planning) - Downgrade invalid readiness claim
  Owner: `/planning`
  Why: The plan cannot remain `implementation-ready` while blockers remain unresolved.
  Apply: Rewrite status/frontmatter to the validator-supported readiness level.
  Proof: `verify_status = READY` and `claimed_status` matches the validator result.

0 - Apply ALL Recommended Next Steps
```

## Status Lifecycle

```
draft -> in-review -> implementation-ready
                   \-> (if blockers found) -> draft (with updated blocker count)
```

| Status | Meaning | Can advance to |
|--------|---------|----------------|
| `draft` | Contains placeholders or missing content | `in-review` |
| `in-review` | Under adversarial review | `implementation-ready` or back to `draft` |
| `implementation-ready` | Concrete content, all blockers resolved or deferred | -- |

A plan cannot be marked `implementation-ready` while:
- Any placeholder text remains
- Any blocker/high finding is unresolved
- Raw adversarial findings are merged into the plan
- Any required contract boundary matrix entry is missing
- Contract-sensitive work lacks a required `Contract Authority Packet` reference
- Any producer/consumer boundary relies on implied fields or unstated freshness rules
- Any plan statement contradicts the active `Contract Authority Packet`
- Phase-precondition metadata is used without recognized readiness vocabulary

Optional frontmatter for phased rollout planning:
- `phase_ready_through: <integer>` — only valid when the plan intentionally models phased rollout readiness
- `next_phase_blockers: <count or ids>` — explanatory only until validator support confirms the shape

Unrecognized ad hoc readiness fields do not weaken the blocking rules above.

## Required Plan Sections (v2 Shape)

Each implementation change must specify:
- **Goal**: What this change aims to achieve
- **Current state with evidence**: Concrete description with file/symbol references
- **Design decisions and invariants**: Named decisions with rationale; explicit concurrency/lifecycle/containment for stateful work
- **Implementation changes**: Per-change scope -- touched files/components, ordering/dependencies, failure handling, cleanup/lifecycle, acceptance checks. Use `**TASK-###**`, `**CHANGE-###**`, or heading-style `### TASK-###:` / `### CHANGE-###:` blocks.
- **Test matrix**: What tests cover this change and how they are run
- **Contract authority reference**: Required for contract-sensitive work; cite the active `Contract Authority Packet` version/path or explicitly state `not contract-sensitive`
- **Contract boundary matrix**: Each producer/consumer boundary with schema, required fields, freshness/invalidation, and consumer validation. Structural plans that do not change boundaries may explicitly mark this section `Not applicable`.
- **Assumptions/defaults**: What is assumed to be true; what defaults apply if unspecified
- **Open questions**: What is unknown that could affect the plan

When the source is an ADR, `/planning` must still emit the same v2 plan shape. ADR headings are never an allowed excuse for a non-canonical plan artifact.

### Contract Boundary Matrix (Required for Artifact or Handoff Work)

If the plan includes hooks, handoff envelopes, restore artifacts, ledgers, evidence files, subagent outputs, or any cross-phase file/payload, the plan must include a contract boundary matrix.

If `/design` produced a `Contract Authority Packet` for those boundaries, the matrix must derive from that packet rather than planner inference.

Minimum fields:

| Field | Requirement |
|-------|-------------|
| Boundary | Name the exact handoff or artifact |
| Contract authority packet | Cite the packet id/version/path when required |
| Producer | Name the writer/emitter |
| Consumer | Name the reader/restorer/router |
| Input schema | Preconditions before production |
| Output schema | Fields/types delivered to consumer |
| Required fields | Mandatory fields only |
| Freshness authority | Which source is authoritative |
| Invalidation trigger | What makes this stale |
| Failure behavior | Stop, retry, reconstruct, or reject |
| Packet alignment | State whether the row matches the packet exactly or explain why `/design` must be reinvoked |
| Test binding | Which test/trace proves the contract |

Plans that say "consumer will use this" without naming the expected fields are not implementation-ready.
Plans that omit a required `Contract Authority Packet` reference or drift from packet semantics are not implementation-ready.
Plans that hand-author stale boundary semantics copied from an older packet are not implementation-ready; `/design` must be reinvoked when the active packet drifts from the current skill contract.

## Recommended Next Steps (RNS)

When `/planning` ends with blockers, routing, or non-ready status, it must emit a numbered RNS section.

Rules:

- Number every actionable step.
- Every item must include `Owner`, `Why`, `Apply`, and `Proof`.
- Use `/design` as the owner for CAP drift, state-model closure, identity/ordering/dedupe/invalidation gaps, and stale boundary semantics.
- Use `/planning` as the owner for plan rewrites, status corrections, matrix completion, and disposition cleanup.
- Use `/code` or `/verify` only when the plan is already ready enough for those skills to act without first routing back through `/planning` or `/design`.
- `0` means "apply the entire recommended set in dependency order."
- If an action depends on a prior one, order it later rather than hiding the dependency in prose.
- Do not emit freeform prose recommendations when RNS is required.

### Additional Required Contracts For Stateful / History / Provider / Multi-Terminal Plans

If the plan touches persistence, retention, ingest, providers, transcripts, event logs, replay, multi-terminal state, or stale-data immunity, it must also make these decisions explicit in the plan body:
- **Identity model**: `provider_id`, `source_id`, `conversation_id`, `session_id`, `terminal_id`, `turn_id`, and `provider_instance_id` if no real terminal exists
- **Ordering contract**: one mandatory ordering/watermark rule only
- **Dedupe contract**: exact event identity semantics and matching schema constraints
- **Freshness / invalidation contract**: authority of truth, invalidation trigger, replay trigger, stale-row behavior
- **Event source of truth**: authoritative source for task/opportunity projections
- **Isolation boundary**: terminal-private vs workspace-shared state boundaries
- **Contract-to-test alignment**: acceptance scenarios that assert the same behavior as the named contracts
- **Triggerability**: reachable trigger conditions for freshness, replay, invalidation, dedupe fallback, and lock recovery mechanisms

Plans missing any of those for applicable topics remain `draft`.

## Constraint Classification (Required)

Every plan must classify its constraints explicitly:

| Constraint | Type | Reason | Could This Be False? |
|------------|------|--------|---------------------|
| {boundary} | hard/soft/assumed | {why it exists} | {evidence or "no"} |

- **Hard**: Physics, platform limits, API contracts. These don't bend.
- **Soft**: Design decisions, tech debt, time pressure. Negotiable with effort.
- **Assumed**: "We've always done it this way." Must be questioned.

**Rule**: Plans with 3+ assumed constraints flagged as hard → flag for review. Assumptions treated as facts cause plan failures.

## Bias Detection Check (Before Synthesis)

Before synthesizing the final plan, check for cognitive biases:

| Bias | Detection Signal | Mitigation |
|------|-----------------|------------|
| **Anchoring** | First approach is the only approach considered | Generate at least 2 alternatives |
| **Sunk Cost** | "We already started X, let's continue" | Evaluate from current state, not past investment |
| **Confirmation** | Only seeking evidence that supports the plan | Actively seek disconfirming evidence |
| **Complexity Bias** | Defaulting to the more sophisticated solution | Start with simplest viable approach |

If any bias is detected, flag in the plan: `"BIAS FLAG: {type} — {mitigation applied}"`.

## Step Confidence Scoring

Each plan step gets a confidence badge:

| Badge | Criteria | Implication |
|-------|----------|-------------|
| `[HIGH]` | Well-understood, existing patterns, clear acceptance criteria | Execute directly |
| `[MED]` | Some unknowns, depends on external state | Add checkpoint before proceeding |
| `[LOW]` | Research needed, unproven approach | Prototype or spike first |

Plans with any `[LOW]` steps in the critical path → status remains `draft` until those steps are validated.

## Artifact Contract

Plans, findings, and review summaries are stored as separate files. See `references/artifact-contract.md` for:
- v1 vs v2 differences table
- Artifact file types and their purposes
- Required plan artifact structure (status header, must-include/must-not-include)
- Disposition table format for review summaries

## ROI Ranking Output Order

When asked to rank solutions by ROI:

1. **State the binding-constraint assumption in one line** ("correctness vs
   throughput vs attention") before any ranking — the lever you optimize
   determines the order.
2. **Deliver the ranked list with a one-sentence rationale and explicit
   assumption per lever.** Answer the ranking question first.
3. **Only then comment on gates/guardrails.** Do not lead with gate critique
   or measurement caveats; if a gate is misbehaving, note it in ≤1 sentence
   and move on — do not let it derail the primary answer.
4. **Rank = debug-time saved × recurrence ÷ effort.** Never fabricate timing
   — if recurrence is undocumented, say so and rank on structural evidence.

## File Locations

```
.claude/skills/planning/
├── SKILL.md                      # This file
├── __lib/
│   ├── auto_verify.py           # Placeholder/contradiction/disposition/purity checks
│   └── auto_fix.py              # Non-semantic-only repairs
├── references/
│   ├── adversarial-agent-prompts.md  # 6 agent prompts + retry protocol
│   ├── artifact-contract.md          # Artifact structure and v1/v2 differences
│   ├── verification-workflow.md      # Steps 1-3: draft, verify, fix
│   └── version-history.md            # Detailed changelog
└── tests/
    ├── test_auto_fix_v2.py     # Non-semantic-only tests
    ├── test_auto_verify_v2.py  # Placeholder + contradiction tests
    └── test_planning_integration_v2.py  # Strict readiness gate tests
```
