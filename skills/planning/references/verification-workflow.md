# Verification & Fix Workflow (Steps 1-3)

Reference for the verification pipeline that runs before adversarial review.

## Step 1: Draft Generation (Not Normalization)

Generate a concrete draft -- NOT placeholder scaffolding:
- Problem statement derived from actual context
- Existing implementation from actual discovery
- Solution from actual analysis
- Implementation tasks with concrete scope

For ADR-sourced work, Step 1 also means translating ADR or `Planning Handoff Packet` content into the canonical v2 plan shape before verification. Do not verify a shallow ADR transcription and then route formatting fallout to `/arch`.

For non-ADR source artifacts, Step 1 also means translating a `Planning Source Packet` or an explicit extraction map into the canonical v2 plan shape before verification. Do not verify a shallow source transcription and then route normalization fallout to `/arch`.

If the input cannot be converted to concrete content, the result stays `draft`. Do NOT use auto_fix to fill in `*Describe the problem*` or `path/to/file1.py`.

## Step 2: auto_verify.py (Deterministic Checks)

```bash
python P:/.claude/skills/planning/__lib/auto_verify.py <plan_path>
```

**New checks in v2:**
- **Placeholder detection**: FAIL if any of these appear: `TODO`, `TBD`, `Describe the problem`, `Add risk analysis`, `path/to/`, `Component A`, `Criteria one`
- **Contradiction checks**: FAIL if plan claims `implementation-ready` while unresolved blocker/high findings exist
- **Disposition checks**: FAIL if `.review.findings.json` or `.review.summary.md` is missing for an `implementation-ready` plan, or if any blocker/high finding lacks a disposition row in the summary
- **Plan-purity checks**: FAIL if plan artifact contains raw findings tables or verification dumps
- **Ambiguous contract checks**: FAIL if required mechanisms present mutually exclusive choices such as “either X or Y” for ordering, watermark, dedupe, invalidation, or identity boundaries
- **Claim-to-schema consistency checks**: FAIL if prose behavior contradicts schema keys, primary keys, or unique constraints
- **Unresolved core decision checks**: FAIL if `Open Questions` still contains implementation-shaping decisions about source-of-truth, ordering, dedupe, invalidation, projection event source, or isolation boundary
- **State-model completeness checks**: For stateful/history/provider/multi-terminal plans, FAIL if identity, ordering, dedupe, invalidation, source-of-truth, or isolation-boundary contracts are missing
- **Boundary overload checks**: FAIL if `terminal_id` is used as a synthetic stand-in for workspace, session, conversation, or provider instance without a separately named field
- **Contract-to-test coherence checks**: FAIL if the test matrix expects behavior that contradicts the plan's named contract
- **Mechanism triggerability checks**: FAIL if invalidation, replay, freshness, or lock-recovery rules depend on triggers that cannot happen under the plan's own invariants

**Existing checks retained:**
- Section completeness
- Solo-dev constraints
- RTM coverage

**Readiness rule for stateful systems:** if the architecture claims multi-terminal safety, stale-data immunity, event replay, provider ingestion, or durable history ownership, the invalidation/source-of-truth mechanics must be specified in the plan itself, each named contract must have a matching acceptance scenario, and each invalidation/replay/freshness mechanism must name a reachable trigger. `auto_fix` cannot invent them later.

**Remediation rule:** if `auto_verify.py` returns architecture-class blockers (`contract_ambiguity`, `state_model`, `schema_consistency`, `identity_boundary`, `contract_test_coherence`, `mechanism_triggerability`, or core state-model `open_questions`), `/planning` should auto-invoke `/arch`, consume the returned decision packet, rewrite the plan itself, and then re-run verification.

**Nested-resume rule:** this `/arch` call is a nested substep of the same `/planning` run. It is not a separate user action. When `next_action.type == invoke_arch_then_rewrite_plan`, `/planning` must resume automatically after `/arch` returns unless the architecture is still incomplete or clarification is genuinely required.

**Control rule:** `/planning` must treat the latest `auto_verify.py` result as authoritative. Plan notes claiming a blocker is a “false positive” do not override `next_action`. If `next_action.type` is `invoke_arch_then_rewrite_plan`, invoke `/arch` first and defer non-architectural cleanup until after the rewritten plan is re-verified.

If `next_action.resume_policy == automatic_return_to_caller`, do not ask the user to rerun `/planning` or to confirm that `/planning` should continue. Continue the same workflow.

**Important boundary rule:** missing frontmatter, non-canonical section names, unsupported task syntax, and reduced contract-matrix columns in an ADR-derived or source-derived draft are local `/planning` rewrite problems first. Fix the draft shape before treating any remaining architecture findings as `/arch` work.

## Step 3: auto_fix.py (Non-Semantic Only)

If auto_verify finds issues, Claude runs `auto_fix.py` -- but ONLY for:

```bash
python P:/.claude/skills/planning/__lib/auto_fix.py <plan_path>
```

**auto_fix v2 is limited to:**
- Header normalization (consistent `##` prefix, proper spacing)
- Section ordering and canonical heading normalization (ensure v2 section names)
- Metadata updates (status header, source path, unresolved_blockers)

**auto_fix v2 does NOT:**
- Insert placeholder content (`*Describe the problem*`, `path/to/file1.py`)
- Generate fake tasks (`TASK-001`)
- Add plausible-looking scaffold (`Component A`, `Criteria one`)
- Write any content that is not purely structural
