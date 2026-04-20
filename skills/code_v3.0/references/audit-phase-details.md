# Phase 7: AUDIT - Detailed Instructions

## When to Run

**Before TRACE**: After TDD completes (tests passing), before manual trace-through.

**Parallel execution**: Can run concurrent with TEST (Phase 6). Both phases test orthogonal concerns:
- TEST = behavioral correctness (do tests pass?)
- AUDIT = code quality (linting, types, security)

**Why this order**: Automated tools catch 20-40% of bugs (different bugs than TRACE finds). Running TEST and AUDIT in parallel saves 5-15 minutes without sacrificing safety.

## Standards Integration by Language

**Python**: Follow `//p` standards
- Toolchain: uv, ruff, mypy, Pydantic V2, asyncio patterns
- Reference: `//p` for Python 2025+ best practices

**TypeScript**: Follow `/code-typescript` standards
- Toolchain: Node 22, pnpm, biome, strict mode

**Universal Principles**: Follow `/code-standards`
- Cross-language standards: DRY, separation of concerns, YAGNI, testing, documentation

## Step 7.1: Code Quality Review

After static analysis, run general code quality review:

```
Agent(subagent_type="pr-review-toolkit:code-reviewer", description="General code quality review for <target>")
```

**What this does:**
- Reviews code for readability and maintainability
- Checks adherence to project conventions
- Identifies code smells and anti-patterns
- Reports findings with confidence scores (80+ threshold)
- Enforces constitutional filter

**Fallback for other languages:**

**Go**:
```bash
go vet ./...
golangci-lint run
gofmt -l .
```

**Rust**:
```bash
cargo clippy -- -D warnings
cargo fmt -- --check
```

## What Tools Catch vs. TRACE

| Issue Type | Static Analysis | TRACE Phase |
|------------|-----------------|--------------|
| Type errors | Catches | N/A |
| Security vulnerabilities | Catches | Also catches |
| Code style violations | Catches | N/A |
| Resource leaks | Sometimes | Catches more |
| Race conditions | Rarely | Catches |
| Logic errors | No | Catches |
| File descriptor reuse | No | Catches |
| Lock cleanup bugs | No | Catches |

**Combined effectiveness**: 85-95% bug detection vs. 60-80% for either alone.

## Static Analysis Protocol

**Automated Verification Loop:**
```
For each attempt (max 3):
  1. Run static analysis (ruff, mypy, pylint)
  2. Auto-fix what's possible (ruff --fix)
  3. Check results
  4. If clean -> EXIT (PASS)
  5. If issues remain: Report blocking issues, Apply auto-fixes, Re-run verification
```

**Blocking Issues** (must fix):
- Type errors (mypy failures)
- Security vulnerabilities (bandit findings)
- Import errors
- Syntax errors

**Advisory Issues** (document, continue):
- Style violations (ruff warnings)
- Complexity issues
- Documentation gaps
- Unused imports

## Static Analysis Exemptions

**Skip static analysis** for:
- **Trivial changes** (< 10 lines, variable renames, imports)
- **Documentation-only changes** (.md files)
- **Test files** (already covered by test verification)
- **Configuration files** (.json, .yaml, .toml)

**Fast mode**: Static analysis is optional
**Full mode**: Static analysis is mandatory for code changes
