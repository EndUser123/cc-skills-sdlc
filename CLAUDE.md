# cc-skills-sdlc

SDLC skills for Claude Code — architecture, planning, code quality, testing, review, and documentation.

## Skills (39)

| Skill | Purpose |
|-------|---------|
| av | Skill Improvement Tool |
| cfg | /cfg - Control Flow Graph Visualization |
| chat-to-decisions | God-Tier Chat-to-Decisions v12 |
| code | /code -- Adaptive Feature Development (Task Engine under /go + Mission Control standalone) |
| code-flow-visualizer | Code Flow Visualizer |
| deliberate-changes | Deliberate Changes Management |
| deps | /deps - Dependency Management |
| design | Architecture Advisor with ADR Phase Gates |
| diagnose | Structured Diagnostic Protocol |
| docs | /docs - Documentation Automation with inline validation |
| dpef | DPEF - Deterministic Prompt Execution Framework |
| go | Task orchestrator (thin) — shared scripts for go-ef/go-pi |
| go-ct | Task orchestrator (execution-contract migration) |
| go-pi | Task orchestrator (Pi model variant) |
| go-ef | Task orchestrator (evidence-first, canonical) |
| mermaid-c4 | Mermaid Diagrams |
| meta-review | Meta-Review Skill |
| multi-file-refactor | Code Editing Patterns |
| perf | /perf - Performance Tracing Wrapper |
| performance-profiler | Performance Profiler |
| planning | Plan Workflow v2 |
| prd | PRD — Product Requirements Document |
| pre-mortem | Critique — Adaptive Adversarial Review |
| profile | /profile - Performance Baseline & Comparison |
| review | /review — Unified code & PR review (modes: pr/diff/file/tests/errors/types/simplify/critical/multi/full) |
| review-pr | *DEPRECATED stub → /review* (pr mode) |
| sqd | *DEPRECATED stub → /review multi* (multi-LLM adversarial dispatch) |
| uci | *DEPRECATED stub → /review full* (Unified Code Inspection engine) |
| qmd-wiki | qmd-wiki |
| rca | Debug RCA Skill — Root cause analysis with Iron Law |
| review_bundle | Review Bundle Creation |
| ship | /ship — Deploy readiness and runtime snapshot |
| snapshot | /snapshot — Session snapshot capture and restore (moved to snapshot package) |
| spec-compliance | Purpose |
| specify | Specify — Detailed Specification |
| sqd | /sqd — SDLC Quality Dispatcher |
| staging-protocol | Code Editing Patterns |
| step-6-5 | Step 6.5 - Generate ORCHESTRATION.md |
| synergy | Code Editing Patterns |
| system-internals-verification | Purpose |
| t | Code Editing Patterns |
| task | /task — Task list orchestration |
| team | /team — Multi-agent task coordination |
| tdd | TDD - Test-Driven Development with PARALLEL Delegation |
| tilldone | /tilldone — Batch convergence runner |
| tldr-code | TLDR-Code: Token-Efficient Code Analysis |
| tldr-deep | TLDR Deep Analysis |
| tldr-overview | TLDR Project Overview |
| tldr-router | TLDR Smart Router |
| tldr-stats | TLDR Stats Skill |
| uci | Unified Code Inspection (`/uci`) |
| wiki | /wiki — Obsidian Wiki + QMD Search Skill |

## Artifacts Convention

All runtime artifacts write to:



 from  env var (falls back to ).

Skills MUST NOT write state to their own directory or to the package root.

## Installation

Plugins live directly in `P:/packages/.claude-marketplace/plugins/<name>/`.


Command frontends live in .

## Hook-Work Contract

Binding for any task that touches hook wiring (Stop/PreToolUse/PostToolUse,
settings.json, hooks.json, dispatch routers). Injected into `/go` worker
prompts for hook tasks; applies to direct edits too.

1. **Discover the dispatch surface BEFORE wiring.** Read `settings.json`,
   `settings.local.json`, plugin `hooks/hooks.json`, and `__lib/router.py`.
   State which surface is live. Do not create a third dispatch pattern unless
   documented as a temporary exception.
2. **Stop output contract (strict).** Block → print
   `{"decision":"block","reason":"continue: ..."}` and exit 0. Allow / done /
   fail-open / not-my-session → print **nothing** and exit 0. Never print `{}`,
   `{"decision":"approve"}`, `{"continue":true}`, or any other allow payload —
   those surface as "Stop hook error: JSON validation failed". stderr is
   diagnostics-only.
3. **Never claim "registered" / "live" / "verified" without evidence.** Cite
   the registration file:line and show real-command smoke output for each
   branch (block, done, no-state). Tests-passing is not liveness — a gate can
   be green in unit tests yet emit the wrong shape on the real dispatch path.
4. **Tests must cover three layers:** unit logic, direct invocation, and real
   registered-dispatch-path smoke. A mocked implementation cannot fake success
   at the dispatch boundary.
5. **Plugin file changes trigger the mutation checklist where applicable:**
   version bump + cache rebuild + scope check before declaring "done".

### Direct-entry exception: `go_continuation_gate.py`

This gate is wired as a **direct project-settings entry**
(`P:/.claude/settings.json` `hooks.Stop[3]` → source path
`skills/go/scripts/go_continuation_gate.py`), NOT through this plugin's
`hooks/hooks.json` (kept at `{"hooks": {}}` — dormant).

- **Why direct-entry:** the gate must run from source so edits take effect
  without a cache rebuild, and `settings.json` invokes the source path
  directly (not the version-keyed cache copy).
- **Self-scoping & fail-silent:** `_find_state_dir()` returns `None` and the
  gate prints nothing when no `console_go_*/go` state tree exists, so it is
  inert in every non-`/go` session.
- **Status: DECIDED — keep direct-entry permanently (task #1053 closed).**
  Rationale: the gate must run from source for edit-liveness (settings.json
  points at the source path); migrating into the versioned cache would couple
  it to cache state where stale cache silently overrides source fixes. Direct
  entry is a single, consistent pattern; the plugin dispatcher stays dormant.
  Full rationale + gate inventory: `skills/go/HOOK_GATE_INVENTORY.md`.
- **Dormant surfaces NOT to revive:** `cc-skills-sdlc/hooks/Stop.py`
  — exists but plugin dispatcher is dormant, referenced only by
  `enforce/tests/test_enforce.py`. Classified in
  `HOOK_GATE_INVENTORY.md` as G6 (dormant-intentional).
- **G5 (Stop_enforce_gate.py) is LIVE:** Confirmed 2026-07-04 — CC's skill
  loader honors SKILL.md frontmatter `hooks.Stop` for the active skill.
  G5 fires on every Stop event during a `/go` session and enforces SDLC hard
  gates via `enforce/stop_gate.py`. It is complementary to G4 (continuation
  gate): G5 enforces completeness; G4 handles task-completion semantics.
  Full classification in `HOOK_GATE_INVENTORY.md`.
  `HOOK_GATE_INVENTORY.md` (G5, G6). Do not wire either as a side effect of
  gate work — their retirement/wiring is a separate isolated decision.

The gate is **additive** to the native goal-loop evaluator — it does not
replace it (no plugin API exists to disable the native evaluator).
