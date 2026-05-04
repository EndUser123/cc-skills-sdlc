# Multi-File Refactoring Standards

## 1. Refactoring Workflow (16-Step)
1. **PREFLIGHT**: assessed structural migration safety (shims, shams).
2. **DISCOVER**: hot-spot detection and parallel agent analysis.
3. **DEDUPLICATE**: merge findings by file+line and semantic similarity.
4. **EVIDENCE_VERIFY**: verify P0/P1 findings via targeted reads.
5. **CLASSIFY_DEBT**: Label findings (Design, Code, Test, Doc, Migration).
6. **PRIORITIZE**: P0 (Bugs) -> P1 (Error Handling) -> P2 (DRY) -> P3 (Style).
7. **CONSTITUTIONAL_FILTER**: Apply SoloDevConstitutionalFilter.
8. **PLAN**: Create refactor plan with tiny commits and migration shims.
9. **RED PHASE**: Write characterization tests; verify they FAIL.
10. **ADVERSARIAL_REVIEW**: Stress-test tests via 8 perspectives.
11. **REFACTOR**: Apply AST-based changes (LibCST).
12. **LSP_VALIDATE**: Verify types and references after each edit.
13. **REGRESSION**: Run full suite; verify no new failures.
14. **SIMPLIFICATION**: Polish code for clarity and maintainability.
15. **DELETION_METRIC**: Report `lines_removed - lines_added`.
16. **QUALITY_SCORE**: Report delta across 8 dimensions.

## 2. Debt Classification
- **Design Debt**: Coupling, boundary violations, missing abstractions.
- **Code Debt**: Duplication, complexity, dead code, poor naming.
- **Migration Debt**: OLD paths that should use NEW paths, stale re-exports.

## 3. Constitutional Filter (Solo-Dev)
- **NO Enterprise Patterns**: Filter out service extraction, factories, and complex abstractions unless proven necessary.
- **YAGNI**: No "flexibility" abstractions without immediate use.

## 4. TDD Characterization
- Characterization tests MUST be created and verified FAILING before any production code changes.
- Rollback safety: Reset to RED/GREEN git tags if catastrophic failure occurs.

## 5. Metrics & Success Criteria
- **Deletion Metric**: Aim for a positive value (simpler is better).
- **Done When**:
    - **P0**: No crashes, no race conditions.
    - **P1**: No bare `except`, no swallowed errors.
    - **P2**: CC <= 10, no duplicates > 6 lines.
    - **P3**: Passes `ruff check`, complete type hints.
