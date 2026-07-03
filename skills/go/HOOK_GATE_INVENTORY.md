# Hook & Gate Inventory — `/go` and cc-skills-sdlc Stop surfaces

Last audited: 2026-07-04. Every Stop/gate surface that exists in this plugin or
project settings is listed here with an explicit status. **No gate is left in
limbo.** Statuses: `live`, `dormant-intentional`, `deprecated`.

Legend:
- **live** — registered on a dispatch surface Claude Code actually invokes.
- **dormant-intentional** — present but deliberately not wired; kept for a reason.
- **deprecated** — superseded; slated for removal.

## Dispatch surfaces in play

| # | Surface | File | State |
|---|---|---|---|
| S1 | Project settings Stop | `P:/.claude/settings.json` `hooks.Stop` | Active dispatch path for Stop |
| S2 | Plugin dispatcher | `cc-skills-sdlc/hooks/hooks.json` | `{"hooks": {}}` — intentionally dormant |
| S3 | Skill-frontmatter hooks | `skills/go/SKILL.md` frontmatter `hooks.Stop` | **LIVE** — CC's skill loader honors `hooks` in SKILL.md frontmatter for the active skill. Resolves `$CLAUDE_PLUGIN_ROOT` and invokes the command. |

## Stop / gate entries

| ID | Path / entry | Status | Reason | Next action |
|---|---|---|---|---|
| G1 | S1 Stop[0]: `P:/.claude/hooks/Stop.py` (via `hook_runner.py`) | live | Main quality Stop gate | Out of /go scope; owned by P:/.claude/hooks |
| G2 | S1 Stop[1]: `skill-guard` router + `log_hook.py` | live | Skill-first enforcement + logging | Out of /go scope; owned by skill-guard |
| G3 | S1 Stop[2]: `{"matcher":".*","hooks":[]}` | dormant-intentional | Empty no-op entry | Harmless; leave or remove in a separate settings-cleanup task |
| G4 | S1 Stop[3]: `skills/go/scripts/go_continuation_gate.py` | **live (this work)** | Session-bound deterministic /go continuation gate | Direct-entry exception — see decision below |
| G5 | S3 / `skills/go/hooks/Stop_enforce_gate.py` | **live** | SKILL.md frontmatter `hooks.Stop` dispatch. CC resolves `$CLAUDE_PLUGIN_ROOT` and invokes the command when `/go` skill is active. Fires on every Stop event during a `/go` session. Enforces SDLC hard gates (worktree_ready, task_selected, code_completed, verified, simplified, reviews_passed, qa_passed, pr_ready) via `enforce/stop_gate.py`. Blocks with message listing missing gates. **Order:** fires BEFORE G4 (settings.json Stop[3]) — proven by stop hook feedback ordering and matrix tests. **Session-binding:** G5 is STATELESS (checks markers in GO_STATE_DIR regardless of session_id); G4 is SESSION-BOUND (payload session_id → pointer → state dir). **Matrix-proven:** 7/7 cases correct (active incomplete→BLOCKS, fully complete→ALLOW, partial→BLOCKS, validation-only→ALLOW, foreign→BLOCKS, stale→ALLOW, no state→ALLOW). | **Keep.** G5 enforces SDLC completeness for real /go runs. G4 handles task-completion semantics. Complementary: G5 blocks incomplete SDLC runs; G4 blocks when work remains. No bypass needed for validation-only tasks (validation tasks should not use /go). G5 is the primary blocker; G4 is a secondary safety net. |
| G6 | `cc-skills-sdlc/hooks/Stop.py` | dormant-intentional | Exists in plugin hooks dir but plugin dispatcher (S2) is `{"hooks": {}}`, so it is never dispatched. Referenced only by `enforce/tests/test_enforce.py`. | **Decide:** retire (delete + drop test) OR wire deliberately via S2. Not wired here. |
| G7 | S1 SubagentStop[0]: `SubagentStop_cjk_drift_detector.py` | live | Different event (SubagentStop, not Stop) | Out of /go scope |

## Decision: dispatch reconciliation (task #1053) — DECIDED

**Keep G4 as a documented direct-entry exception. Do NOT migrate into the
plugin dispatcher (S2) or skill frontmatter (S3).**

Rationale:
1. **Source-liveness.** `settings.json` Stop[3] invokes the gate at its SOURCE
   path (`skills/go/scripts/go_continuation_gate.py`). Edits take effect
   without a cache rebuild. Migrating to the plugin dispatcher (S2) couples
   the gate to the version-keyed cache, where a stale cache can silently
   override source fixes — exactly the drift class we just had to resolve.
2. **Self-scoping + fail-silent.** The gate prints nothing when identity is
   absent, the bound state dir is missing, or state is foreign/stale/ambiguous.
   It is inert in every non-`/go` session, so direct-entry imposes no
   cross-session cost.
3. **No mixed patterns.** Keeping G4 on S1 and S2/S3 dormant is a single,
   consistent pattern (project-settings direct entry). Wiring S2 would create a
   second active dispatch surface for this plugin and resurrect G5/G6 ambiguity.

**G5 resolved (2026-07-04):** Confirmed live via SKILL.md frontmatter dispatch.
Keep as-is. G5 (enforce gate) and G4 (continuation gate) are complementary:
G5 enforces SDLC completeness (blocks incomplete runs); G4 handles
task-completion semantics (blocks when work remains). No conflict; no
double-fire (different dispatch surfaces, different concerns).

**G6 still open:** `cc-skills-sdlc/hooks/Stop.py` remains dormant-intentional.
Retire or wire deliberately — separate, isolated decision, not a side effect.

## Mechanical-check coverage

The test suite (`skills/go/tests/test_thought_partner.py`) asserts:
- G4 is the only `/go` Stop gate reachable from S1 (`test_gate_registered_in_settings`).
- G4 emits empty stdout on allow/fail-open/foreign/stale/ambiguous.
- G4 never emits `{}` or `{"decision":"approve"}`.
- G4 does not cross-block across terminals or foreign sessions.

A separate `test_no_dead_gate_without_status` check (in
`test_thought_partner.py`) parses THIS file and asserts every `G#` row carries
an explicit Status — so a gate cannot be added to the tree without being
classified here.
