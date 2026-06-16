# Changelog

## v1.1.0 (2026-06-05)

### Added
- Synthesis module + Health Score (per task #492). `scripts/synthesize_findings.py` collapses heterogeneous findings into a single 0-100 metric: `100 - (CRITICAL×20) - (HIGH×10) - (MEDIUM×5) - (LOW×2)`, clamped to [0, 100].
- 5-agent configuration (per task #491) in `references/agent-configs.md`: Lead, Finder, Critic, Refactorer, Verifier roles.
- Characterization tests for the export pipeline (per task #483): `recap/tests/test_export_chain.py`.

### Changed
- `run-qa-verification.py` refactored to use direct GTO import (per task #502). Removes the deprecated `gto_quality_runner.py` indirection.
- `/recap SKILL.md` migrated to RNS render module (per task #489).
- `gto/SKILL.md` updated to remove `gto_quality_runner.py` reference (per task #503).

### Fixed
- Test coverage restored for /refactor (per task #500).

### Pending (designed, not yet wired)
- Synthesis module integration into `refactor_plan.py` (per task #496). Module exists; orchestrator does not yet import it.
- `--legacy-agents` rollback flag (per task #497). Designed but not coded.
- `/refactor` SKILL.md workflow documentation update (per task #495). Synthesis is mentioned in passing but the detailed 5-agent / Health Score / RNS flow is not yet documented.

## v1.0.0 (2026-04-14)

- Initial release
- Multi-file refactoring orchestration with rollback automation
- TDD phase support (RED → GREEN → REFACTOR)
- Synergy detection for cross-file pattern analysis
- Complexity triage with cyclomatic complexity scoring
- Incremental refactoring with state persistence
- RollbackManager for git-based safety nets
- TestGenerator for automated test scaffolding
- SynergyDetector for DRY violation detection
- ComplexityTriage for risk-based prioritization
- StateManager for thread-safe state persistence
