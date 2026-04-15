# Changelog

All notable changes to the refactor skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Rollback automation with git-based safety nets
- Test generation with TDD phases (RED → GREEN → REFACTOR)
- Synergy detection for cross-file pattern analysis
- Complexity triage with risk-based prioritization
- Incremental refactoring mode with state persistence
- Configuration management (CLI + YAML/JSON)
- Windows junction installation script
- Portfolio-quality README with architecture diagrams
- Comprehensive test suite

### Changed
- Moved automation modules to canonical location `__csf/src/refactor/`
- Updated skill interface to import from canonical location
- Improved thread safety for state manager operations

### Fixed
- Corrected variable name typo in `mark_skipped()` method
- Fixed import paths for Python automation modules
- Resolved module filename pattern detection issues

## [1.0.0] - 2026-01-11

### Added
- Initial release of refactor skill
- 8 priority improvements:
  1. Rollback Automation (git-based)
  2. Test Generation Integration (TDD phases)
  3. Synergy Detection (cross-file patterns)
  4. Complexity Triage (risk-based prioritization)
  5. Incremental Refactoring Mode (state persistence)
  6. Configuration-Based Thresholds (CLI + config file)
  7. Progress Persistence (tracking completed findings)
  8. Integration with /synergy skill
- Python 3.12+ type hints throughout
- Dataclass-based configuration and state management
- Thread-safe atomic state persistence
- Comprehensive documentation and examples

### Architecture
- Skill interface at `.claude/skills/refactor/`
- Automation modules at `__csf/src/refactor/`
- Test suite at `__csf/tests/refactor/`
- Windows-compatible junction installation

## [0.1.0] - 2026-01-10

### Added
- Initial skill scaffolding
- Basic SKILL.md documentation
- Implementation plan (8 improvements)

---

## Version Summary

| Version | Date | Status | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-11 | Production | Full feature set |
| 0.1.0 | 2026-01-10 | Alpha | Initial scaffolding |
