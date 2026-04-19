# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-terminal isolation integration tests (test_multi_terminal_isolation.py)
- Real config file integration tests (test_config_real_files.py)
- Fixture cleanup verification tests (TestFixtureCleanup class)
- Thread-safe config caching with lru_cache clearing

### Fixed
- Config test thread safety issues - replaced pathlib.Path.exists patching with environment variable approach
- Invalid output_size values across test files ('medium'→'normal', 'concise'→'small', 'verbose'→'large')
- Import error in test_config_thread_safety.py (skill.config → config)
- Test ordering failure caused by global patching affecting concurrent tests
- Cache clearing completeness - added lru_cache clearing to clear_config_cache()

### Changed
- Documented cache behavior (maxsize=1, invalidation triggers, performance considerations)
- All 48 config tests now passing (thread safety, caching, validation, types, real files, multi-terminal)

### Added (from prior)
- Portfolio artifacts (README.md, LICENSE, .gitignore, CHANGELOG.md)
- GitHub Actions CI workflow with test, lint, and template validation jobs
- Test coverage badge (87%)
- Python version badge (3.12+)

## [3.2.0] - 2025-02-10

### Added
- Template chaining validation (max 2 templates, precedent cannot be secondary)
- Domain keyword detection with override support
- Cascading configuration priority (project -> user -> env var)
- CKS integration with fallback support
- Output persistence for architecture decisions
- Prerequisite analyzer with semantic analysis
- Cross-platform path resolution

### Changed
- Improved template validation with duplicate logic detection
- Enhanced domain detection with keyword override
- Better error messages with "Did you mean?" suggestions

### Fixed
- COMP-001: Config file location mismatch
- COMP-002: Remove JSON comments from example file
- COMP-003: Add template chaining validation
- COMP-008: Implement output persistence
- SEC-001: Path Traversal vulnerability
- SEC-002: Unsafe JSON Deserialization
- PERF-001: Large Transcript Memory Load
- PERF-002: O(n*m) Nested Loop Complexity
- TEST-001: Add Concurrent Write Tests

## [3.1.0] - 2025-02-06

### Added
- Template override support via `template=` parameter
- Domain-specific templates (cli, python, data-pipeline, precedent)
- Complexity detection (fast vs deep)
- Configuration schema validation

### Changed
- Restructured routing logic for better template selection
- Improved SKILL.md with execution flow documentation

## [3.0.0] - 2025-02-03

### Added
- Complete template-based routing system
- Six domain templates (fast, deep, cli, python, data-pipeline, precedent)
- Shared frameworks and template contracts
- Evidence system integration

### Changed
- Major refactor from monolithic to template-based architecture
- Moved from procedural to configuration-driven routing

## [2.0.0] - 2025-01-28

### Added
- Initial architecture advisor implementation
- Basic domain detection
- Simple template system

## [1.0.0] - 2025-01-15

### Added
- First release
- Basic architecture queries
