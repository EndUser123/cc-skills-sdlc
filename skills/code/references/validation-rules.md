# Validation Rules and Prohibited Actions

## Validation Rules

- **Plan handling is mandatory**: If `plan.md` exists, continue remaining tasks. If missing, create plan before TDD.
- **Plan source precedence**: Markdown plan artifacts first, then active `*plan*.md`, then `plan.md`. JSON artifacts are metadata only.
- **Execution model must be explicit**: State whether using subagents, team, or hybrid.
- **Task list discipline required for team/hybrid**: Scoped list ID, ownership, dependencies.
- **Task completion proof required**: RED fail evidence, GREEN pass evidence, REFACTOR pass evidence, verifier PASS.
- **Merged builder phase allowed**: GREEN and REFACTOR may run in one pass if tests pass before and after cleanup.
- **Anti-hallucination rule**: Before adding new APIs/dependencies, verify presence in repo/docs.
- **Tool-result acknowledgment**: Capture and acknowledge exit status/output for critical commands.
- **Error-handling reminder**: For async/network/file/database changes, verifier must confirm error paths.
- **Verification mode policy**: Advisory feedback allowed mid-build; blocking checks mandatory before DONE.
- **Path canonicalization required**: Test/verifier commands must normalize paths to active runtime.
- **Resume ledger required**: Maintain per-run ledger with task state, evidence pointers, blockers, decisions.
- **Runtime fingerprint required**: Capture shell/runtime/tool paths at BOOTSTRAP and use as execution baseline.
- **Fast-mode exceptions**: Full resume ledger and BOOTSTRAP/runtime-fingerprint optional; minimum path probe + explicit evidence reporting remain mandatory.
- **Scripted gate checks required**: Use `scripts/update_resume_ledger.py`, `scripts/validate_skip_governance.py`, and `scripts/validate_done_claim.py` before completion claims.
- **Transition gate required**: Run `scripts/validate_phase_transition.py` on each phase boundary and block invalid jumps/regressions.
- **TDD sentinel required**: Per-task `tdd_state` in ledger (`none -> red -> green -> refactor -> verify`); completed tasks require `verify`.
- **Evidence scaffold required**: Initialize per-task evidence files and require non-empty RED/GREEN/REFACTOR/VERIFY evidence before done-claim passes.
- **Ledger locking required**: All ledger writes must use lock-protected operations to prevent multi-terminal corruption.
- **Lease ownership required for concurrency**: Claim/release tasks with `owner` + `lease_expires_at`; stale leases must be surfaced before duplicate execution.
- **Run analytics required**: After DONE phase, append run summary to `.claude/history/build-runs.jsonl`.
- **Tagged planning preferred**: Use inline task tags like `[risk:high]` and `[area:infra]` in `plan.md`.
- **Timeout/token escalation required**: Tasks exceeding budget must stop with explicit blocker contract.
- **Skip governance required**: Skipped tasks require explicit user approval, rationale, and risk note.
- **Spec drift checks required**: Compare current edits against acceptance criteria before closing each task.
- **Impact-map checks required**: Each task must map changed files to targeted regression checks.
- **Auto-checkpoint cadence required**: Checkpoint after each high-risk task or every N tasks.
- **Confidence calibration required before done**: List residual risks and targeted checks.
- **TDD compliance**: All code changes must have tests first.

### Phase Gate Requirements
- **Before Phase 2**: Complete PRE-FLIGHT (health check passed)
- **Before Phase 3**: Complete EXPLORE (codebase understood)
- **Before Phase 4**: Complete PLAN (design with pre-mortem documented)
- **Before Phase 5**: Complete TDD (RED -> GREEN -> REFACTOR for all tasks)
- **Before Phase 6**: Complete TEST (full test suite passes)
- **Before Phase 7**: Complete AUDIT (quality checks pass)
- **Before Phase 8**: Complete TRACE (manual verification passes)
- **Before Phase 9**: Complete DONE (final certification)

## Prohibited Actions
- Skipping TDD workflow (tests must be written first)
- Proceeding to next phase without completing current phase
- Making code changes without understanding requirements
- Skipping verification before shipping
- Silent stopping during TDD without explicit blocker reason and question
- Running team/hybrid without explicit task ownership and dependency tracking
- Declaring a task done after RED-only work
- Declaring plan/build done without explicit completion evidence
- Skipping tasks without explicit user-approved skip record
- Claiming done without residual risk statement and final calibration checks
- Returning subagent output inline to orchestrator instead of writing to disk and returning a Result Envelope
- Running high-output tasks (diffs, full module rewrites, long analyses) in parallel
- Passing entire plan documents or large files into subagent prompts instead of targeted excerpts
- Reading entire files when only a function or block is needed

## Subagent Output Routing Rules

Every subagent writes detailed output to disk and returns only a small envelope. See canonical spec: `.claude/skills/shared/result-envelope.md`.

```json
{
  "status": "done" | "blocked" | "retry",
  "artifact": "relative/path/to/output/file.ext",
  "summary": "3 short lines max -- no code, no diffs",
  "metrics": { "artifact_bytes": 4821, "files_read": 3 }
}
```

The orchestrator consumes only Result Envelopes plus selective reads of artifacts; it never inlines full artifact content into its own context.

### Routing rules
- **Phase boundaries = context resets** -- use the handoff system between major phases; new session reads phase summary, not full history.
- **Sequential by default within a phase** -- tasks that produce large artifacts (full diffs, complete implementations, long analyses) are high-output and must run sequentially. Tasks that produce only metadata, verdicts, or short structured JSON are low-output and may run in parallel.
- **Spike before high-output tasks** -- when a task would produce a large artifact, write type signatures and interfaces only first and review before full implementation.
- **Targeted file reads** -- when only part of a file is relevant, use `Grep` + `offset`/`limit`. If a full read is genuinely needed and the file is clearly large, write a summary artifact and return a pointer; do not inline the full content.
- **Pass task excerpts, not full plans** -- brief each subagent with only the relevant task block.
