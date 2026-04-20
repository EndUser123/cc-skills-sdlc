# Phase 9: DONE - Detailed Instructions

## Pre-Done Checklist (MANDATORY before Build Verification)

**What this prevents**:
- Incomplete test implementation (5/9 tests -> would have been caught)
- Missing defensive programming (IndexError crashes)
- Unvalidated detection patterns (false positives)

### Test Coverage:
- [ ] **All test cases from plan.md implemented** -> Count matches plan specification
- [ ] **Positive cases tested** -> Detector triggers on expected inputs
- [ ] **Negative cases tested** -> Detector does NOT trigger on wrong inputs
- [ ] **Edge cases tested** -> Empty strings, whitespace, malformed inputs
- [ ] **False positive scenarios validated** -> Test each pattern with adversarial inputs

### Code Quality:
- [ ] **Defensive programming applied** -> Guard clauses for list/dict/string access
- [ ] **No bare list access without length check** -> `if list and list[0]` not `list[0]`
- [ ] **No bare string access without None check** -> `if s and s[0]` not `s[0]`
- [ ] **All pattern examples validated** -> Test against false positives
- [ ] **Error paths documented** -> Even if "graceful degradation", document behavior

### Documentation:
- [ ] **All plan requirements addressed** -> Cross-check plan.md sections
- [ ] **Implementation matches architecture** -> Data flow, modules, interfaces as planned
- [ ] **Error handling documented** -> Explicit or "graceful degradation" noted

### Verification:
- [ ] **ruff linting passes** -> No warnings
- [ ] **pytest passes** -> All tests including new ones
- [ ] **Manual TRACE completed** -> Logic correctness verified
- [ ] **No blocking issues remaining** -> All P0/P1 issues resolved

**BLOCKING RULE**: If ANY checkbox is unchecked, DO NOT proceed to build verification.

**Usage**: Run before Phase 9.1:
```bash
# Quick check (advisory)
python .claude/skills/code/scripts/verify_plan_compliance.py <plan.md> <test_file.py>

# Strict check (blocking)
python .claude/skills/code/scripts/verify_plan_compliance.py <plan.md> <test_file.py> --strict
```

## 9.1 Build Verification

Build verification runs automatically via Stop hook (`Stop_smart_build_verify.py`):

- **Smart detection**: Only checks files changed in current session (`git diff --name-only HEAD`)
- **Project type auto-detection**: Python, TypeScript, or compiled
- **Python**: Runs pytest on test files, falls back to syntax check (`py_compile`) if no tests exist
- **TypeScript**: Runs `npx tsc --noEmit` for type checking
- **Blocks completion**: If checks fail, response is blocked with error details
- **Runtime**: Typically < 10 seconds

Verification mode:
- **Advisory mode** (during active iteration): warnings may continue with explicit risk note.
- **Blocking mode** (before DONE/SHIP): failing build checks or unresolved high-risk advisories must block completion.

## 9.2 Certify DONE

**Step 9.5: Final Code Review**

Before final certification, run automated PR review:

```
Skill(skill="code-review:code-review", args="<target>")
```

**When to run:**
- AFTER build verification passes
- BEFORE marking build as DONE
- OPTIONAL if changes are trivial (< 10 lines)
- MANDATORY for non-trivial features

When build verification passes:

- [ ] All tasks in `plan.md` marked complete
- [ ] Build verification passed (no pytest/tsc failures)
- [ ] Final code review complete (or skipped for trivial changes)
- [ ] Ready for `/qa` or `/evolve`

## 9.3 Domain Mechanics Checkpoint (Before Deployment)

**Check deployment relevance** (< 1 minute):

File-based systems (skills, hooks, configs): File exists = deployed (skip deployment guidance).

Service-based systems (services, databases): Process restart required (include deployment guidance).

## 9.4 Deployment Guidance (For Service-Based Systems Only)

**Detect deployment environment** (5 minutes):
- Check for CI/CD config: `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `circleci/`
- Check for staging/dev environments: `docker-compose.yml`, `terraform/`, `helm/`, environment variables
- Check for feature flags: LaunchDarkly SDK, Unleash, custom flag systems

**Deployment scenarios:**

**Single-environment**: Direct release, full backup, git revert rollback.

**Multi-environment**: Staged rollout (staging -> smoke tests -> production -> monitor).

**Feature flag detected**: Deploy behind flag, gradual rollout 5% -> 25% -> 50% -> 100%.

**No CI/CD detected**: Manual release checklist (backup, migrations, env vars, deps, restart, smoke tests, monitoring).

**Note:** Deployment plan is advisory. Adapt to your project's actual infrastructure and risk tolerance.
