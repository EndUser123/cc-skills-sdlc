# Changelog

**Version:** 2.26.0 (2026-03-25)

## v2.26.0: TDD Resume Context auto-injection (ADR-20260324, ADR-20260325)
- Added `tdd_resume.py` module with configurable paths via environment variables
  - `TDD_STATE_DIR`: Override default `~/.claude/.state/code/tdd/` path
  - `TDD_EVIDENCE_DIR`: Override default `~/.claude/.evidence/code/tdd95/` path
- Key functions for TDD context restoration:
  - `find_active_tdd_contracts()`: Discovers active TDD sessions by terminal_id
  - `find_phase3_evidence()`: Finds Phase 3 evidence files for contracts
  - `generate_tdd_resume_context()`: Generates markdown context for session resume
  - `get_tdd_state_for_handoff()`: Returns TDD state summary for handoff envelope
- SessionStart hook integration via `inject_tdd_resume_context()` in `SessionStart_verification_cleanup.py`
- Multi-terminal isolation: State files scoped by `terminal_id`
- Test coverage: 14 tests passing with proper path isolation via `importlib.reload()`
- References: ADR-20260324 (Clean-Room TDD Loop v2), ADR-20260325 (Resume Context)

## v2.25.0: Core Plan v1 integration
- **NEW:** Evidence tracking integration with /tdd timestamped artifacts
- **NEW:** Pre-execution checklist validation (non-empty answers)
- **NEW:** Ralph Loop auto-enable based on task type detection
- See `references/core-plan-v1-integration.md` for details

## v2.24.0: Continuous Execution Mode now DEFAULT
- **BREAKING CHANGE:** /code now runs through all phases by default
- Continuous mode is ON by default (no opt-in phrases required)
- Phase boundaries are NOT stopping points
- Added opt-out flags: --interactive, --step-by-step, --step-by-phase, -i

## v2.23.0-23.1: Continuous Execution Mode
- Detects intent phrases for uninterrupted multi-phase execution
- Suppresses phase-completion summaries and "Next Steps" menu in continuous mode
- Only stops for genuine blockers

## v2.22.0: Graph-of-Thought (GoT) and Tree-of-Thought (ToT)
- Phase 4: GoT node extraction and edge analysis (opt-out: `--no-got`)
- Phase 8: ToT branch generation and scoring (opt-out: `--no-tot`)
- New utils modules: `got_planner.py` (GoT) and `tot_tracer.py` (ToT)
- 60 tests passing

## v2.21.0: Integrated review agents from pr-review-toolkit
- Step 6.5: Test Coverage Analysis (pr-test-analyzer)
- Step 7.1: Code Quality Review (code-reviewer)
- Step 8.1: Error Handling Verification (silent-failure-hunter)
- Step 9.5: Final Code Review (code-review plugin)

## v2.20.0: Enhanced quality enforcement
- Coverage threshold enforcement in Phase 5 VERIFY (from tdd-workflow)
- Automated verification loops in Phase 7 AUDIT (from django-verification)
- Patterns borrowed from SkillsMP analysis of 30+ hosted skills

## v2.19.0: Execution path verification in PLAN phase
- Step 4.5: Execution Path Verification (mandatory for non-linear flows)
- Detects unreachable branches, early exits, lifecycle gaps, marker conflicts
- Saves 10-30 minutes of rework by catching issues earlier

## v2.18.0: Major phase restructuring -- 9-phase workflow
- Renamed BUILD -> TDD with explicit RED -> GREEN -> REFACTOR cycle
- Renamed Phase 6: VALIDATION -> TEST
- Renamed Phase 7: STATIC ANALYSIS -> AUDIT
- Renamed Phase 9: SHIP -> DONE
- Removed BOOTSTRAP, ALIGN, DESIGN, PARSE+TRIAGE phases
- Added PRE-FLIGHT, EXPLORE phases

## v2.10.0: TRACE now mandatory in all modes
- Removed "fast mode" exemptions. Skipping verification is borrowing bugs.
