# Hosted Skills Analysis for /code Improvements

**Date**: 2026-03-02
**Sources Searched**: SkillsMP (AI semantic search), SkillHub (keyword search), ClawHub (semantic search)

---

## Executive Summary

Found **30+ relevant skills** across three sources that could enhance the `/code` workflow. Key themes:

1. **TDD Workflow Automation** - 8 skills (55K+ stars each from affaan-m)
2. **Code Review & Architecture** - 10 skills (automated review, clean architecture)
3. **Quality Assurance** - 8 skills (linting, static analysis, verification)
4. **Testing Strategies** - 5 skills (E2E, testing patterns, QA workflows)
5. **Pre-mortem Analysis** - 10 skills (failure mode identification)

---

## Top Recommendations by Category

### 1. TDD Workflow Enhancement ⭐

**Highest Impact**: Framework-specific TDD skills with 55,676 stars each

| # | Skill | Author | Stars | Source | Key Feature | Integration Potential |
|---|-------|--------|-------|--------|-------------|----------------------|
| 1 | **tdd-workflow** | affaan-m | 55,676 | SkillsMP | RED→GREEN→REFACTOR enforcement | ⭐⭐⭐ Direct workflow enhancement |
| 2 | **django-tdd** | affaan-m | 55,676 | SkillsMP | Django-specific TDD with pytest-django | ⭐⭐ Framework specialization |
| 3 | **springboot-tdd** | affaan-m | 55,676 | SkillsMP | Spring Boot TDD with JUnit 5, Mockito | ⭐⭐ Framework specialization |
| 4 | **golang-testing** | affaan-m | 55,676 | SkillsMP | Table-driven tests, benchmarks, subtests | ⭐⭐ Framework specialization |
| 5 | **Task Development Workflow** | majiayu000 | 82 | SkillHub | TDD-first with structured planning | ⭐⭐⭐ Complements existing /code |

**Why These Matter for /code**:
- `/code` already enforces TDD, but could use framework-specific patterns
- **tdd-workflow** by affaan-m has explicit RED→GREEN→REFACTOR loop enforcement
- **Task Development Workflow** on SkillHub adds structured planning + task tracking

**Integration Strategy**: Borrow RED→GREEN→REFACTOR enforcement patterns, framework-specific test strategies

---

### 2. Code Review & Architecture ⭐

**Highest Impact**: Automated review workflows with architecture validation

| # | Skill | Author | Stars | Security | Source | Key Feature |
|---|-------|--------|-------|----------|--------|-------------|
| 1 | **code-review** | agno-agi | 38,280 | - | SkillsMP | Linting + style checking + best practices |
| 2 | **phase-8-review** | popup-studio-ai | 228 | 100/100 | SkillHub | Codebase quality verification + gap analysis |
| 3 | **code-architecture-review** | omer-metin | 6 | 100/100 | SkillHub | Architecture review for maintainability |
| 4 | **clean-architecture** | nathankim0 | 0 | 100/100 | SkillHub | Design guidance based on Clean Architecture |
| 5 | **clean-architecture-principles** | majiayu000 | 82 | 100/100 | SkillHub | Enforce DRY, YAGNI, SOLID principles |

**Why These Matter for /code**:
- `/code` Phase 7 (AUDIT) could borrow automated review patterns
- **phase-8-review** explicitly verifies codebase quality (complements TRACE phase)
- **clean-architecture-principles** enforces principles that /code mentions but doesn't automate

**Integration Strategy**:
- Borrow automated review checklists from **phase-8-review**
- Add architecture validation from **code-architecture-review**
- Integrate DRY/YAGNI/SOLID enforcement from **clean-architecture-principles**

---

### 3. Pre-mortem & Failure Analysis ⭐

**Critical Gap**: `/code` has pre-mortem in PLAN phase, but could be more systematic

| # | Skill | Author | Stars | Security | Source | Key Feature |
|---|-------|--------|-------|----------|--------|-------------|
| 1 | **premortem** | parcadei | 3,535 | 100/100 | SkillHub | Structured risk analysis, failure mode identification |
| 2 | **premortem** | Dunc4nJ | 2 | 100/100 | SkillHub | Identify failure modes before they occur |
| 3-10 | **premortem** (various) | Various | 1-2 | 100/100 | SkillHub | Same pattern, different implementations |

**Why This Matters for /code**:
- `/code` PLAN phase has pre-mortem step (5 minutes), but no structured methodology
- **premortem** skill by parcadei has 3,535 stars → proven, systematic approach
- Could enhance Step 4.5 (Execution Path Verification) with structured failure analysis

**Integration Strategy**:
- Adopt structured failure mode identification from **premortem** (parcadei)
- Add failure mode taxonomy to pre-mortem step in PLAN phase
- Create pre-mortem checklist templates (borrow from skill patterns)

---

### 4. Quality Assurance & Static Analysis ⭐

**Highest Impact**: Automated linting, verification loops, quality gates

| # | Skill | Author | Stars | Security | Source | Key Feature |
|---|-------|--------|-------|----------|--------|-------------|
| 1 | **django-verification** | affaan-m | 55,676 | - | SkillsMP | Verification loop: migrations → linting → tests |
| 2 | **lint-and-validate** | davila7 | 21,677 | - | SkillsMP | Automatic quality control, linting, static analysis |
| 3 | **dyadlint** | dyad-sh | 19,774 | - | SkillsMP | Pre-commit checks: formatting, linting, type-checking |
| 4 | **python-code-style** | wshobson | 29,815 | - | SkillsMP | Python linting, formatting, naming conventions |
| 5 | **quality-validation** | qodex-ai | 1 | 100/100 | SkillHub | Validate quality before completing tasks |

**Why This Matters for /code**:
- `/code` Phase 7 (AUDIT) runs ruff/mypy manually
- **django-verification** has automated verification loop pattern
- **lint-and-validate** has automatic quality control procedures
- **dyadlint** has pre-commit check framework

**Integration Strategy**:
- Borrow verification loop pattern from **django-verification**
- Add pre-commit check framework from **dyadlint**
- Integrate quality validation from **quality-validation**
- Enhance AUDIT phase with automated verification loops

---

### 5. Testing Strategies & Patterns ⭐

**Highest Impact**: E2E testing, test automation, QA workflows

| # | Skill | Version | Stars | Source | Key Feature |
|---|-------|---------|-------|--------|-------------|
| 1 | **Test Master** | None | (1.15) | ClawHub | Test strategy creation, automation |
| 2 | **E2E Testing Patterns** | None | (1.06) | ClawHub | Playwright + Cypress E2E patterns |
| 3 | **Testing Workflow** | None | (1.02) | ClawHub | Orchestrates comprehensive testing |
| 4 | **Testing Patterns** | None | (1.01) | ClawHub | Unit/integration/E2E patterns |
| 5 | **QA & Testing Engine** | None | (0.99) | ClawHub | Comprehensive testing methodology |

**Why This Matters for /code**:
- `/code` Phase 6 (TEST) runs pytest, but no test strategy guidance
- **Test Master** on ClawHub helps create test strategies
- **E2E Testing Patterns** adds E2E coverage (gap in current /code)
- **Testing Workflow** orchestrates comprehensive testing (automates test execution)

**Integration Strategy**:
- Add test strategy guidance from **Test Master**
- Integrate E2E testing patterns from **E2E Testing Patterns**
- Add test orchestration from **Testing Workflow**

---

### 6. Workflow Orchestration ⭐

**Highest Impact**: End-to-end workflow automation, team coordination

| # | Skill | Version | Stars | Source | Key Feature |
|---|-------|---------|-------|--------|-------------|
| 1 | **Code** | None | (1.18) | ClawHub | Coding workflow: planning → implementation → verification |
| 2 | **end-to-end-orchestrator** | majiayu000 | 82 | 100/100 | SkillHub | Complete development workflow orchestrator |
| 3 | **Workflow Patterns** | None | (1.04) | ClawHub | TDD, phase checkpoints, structured implementation |
| 4 | **Task Development Workflow** | majiayu000 | 82 | 100/100 | SkillHub | TDD-first + structured planning + task tracking |
| 5 | **Delegation** | None | (1.00) | ClawHub | Architecture-first workflow for delegating complex projects |

**Why This Matters for /code**:
- `/code** is already a workflow orchestrator, but could learn from other implementations
- **Code** skill on ClawHub has similar structure (planning → implementation → verification)
- **end-to-end-orchestrator** has team coordination features (future enhancement)
- **Workflow Patterns** has TDD + phase checkpoints (similar to /code's phases)

**Integration Strategy**:
- Study **Code** skill (ClawHub) for architectural patterns
- Borrow team coordination from **end-to-end-orchestrator**
- Compare phase checkpoint implementation with **Workflow Patterns**
- Analyze task tracking from **Task Development Workflow**

---

## Detailed Integration Ideas

### Idea 1: Enhanced TDD Enforcement (HIGH IMPACT)

**Borrow from**: `tdd-workflow` (affaan-m, 55,676 stars)

**Current `/code` Phase 5 (TDD)**:
```
Plan → Test(Red) → Code(Green+Refactor) → Review/Verify
```

**Enhanced with patterns from `tdd-workflow`**:
- **RED gate**: Tests must FAIL before implementation proceeds (current /code does this)
- **GREEN gate**: Minimal implementation only (current /code does this)
- **REFACTOR gate**: Must pass all tests before AND after refactor (current /code does this)
- **Coverage threshold**: Enforce 80% coverage (borrow from `tdd-workflow` description)
- **Framework-specific patterns**: Borrow from `django-tdd`, `golang-testing`, etc.

**Implementation**: Add coverage threshold enforcement to VERIFY phase in TDD loop

---

### Idea 2: Automated Verification Loops (HIGH IMPACT)

**Borrow from**: `django-verification` (affaan-m, 55,676 stars)

**Current `/code` Phase 7 (AUDIT)**:
```
Run ruff, mypy, pylint (manual, one-time)
```

**Enhanced with verification loop pattern from `django-verification`**:
```
Loop:
1. Run static analysis (ruff, mypy)
2. Check results
3. If issues found → fix
4. Re-run verification
5. Exit when clean OR max iterations reached
```

**Integration**: Add to AUDIT phase, automate fix-verify cycle

---

### Idea 3: Pre-mortem Structured Framework (MEDIUM IMPACT)

**Borrow from**: `premortem` (parcadei, 3,535 stars)

**Current `/code` PLAN phase pre-mortem** (5 minutes):
```
1. Imagine: "6 months from now and this feature failed. Why?"
2. List top 3 failure modes
3. Document preventive action
```

**Enhanced with structured framework from `premortem`**:
- **Failure mode taxonomy**: Common categories (deadlock, data corruption, memory leak, race condition)
- **Risk assessment**: Impact × likelihood matrix
- **Preventive measures**: Test cases, guardrails, validation
- **Observability planning**: Metrics, alerts, diagnosis paths
- **Documentation**: Structured pre-mortem report

**Integration**: Replace 5-minute free-form pre-mortem with structured framework

---

### Idea 4: Architecture Validation (HIGH IMPACT)

**Borrow from**: `code-architecture-review` (omer-metin, 6 stars, 100/100 security)

**Current `/code`**: No architecture review in PLAN phase

**Enhanced with architecture validation**:
- **Module structure review**: Verify component boundaries
- **Interface validation**: Check API contracts
- **Dependency analysis**: Check circular dependencies
- **Scalability assessment**: Load handling, performance risks
- **Maintainability review**: Code organization, documentation

**Integration**: Add to PLAN phase Step 4.5 (Execution Path Verification already does some of this)

---

### Idea 5: E2E Testing Gap (MEDIUM IMPACT)

**Borrow from**: `E2E Testing Patterns` (ClawHub, 1.06 relevance)

**Current `/code` Phase 6 (TEST)**:
- Unit tests (from TDD)
- Integration tests
- Regression tests

**Missing**: E2E tests

**Enhanced with E2E patterns**:
- **Playwright patterns** (if web app)
- **Cypress patterns** (if web app)
- **API E2E** (if backend)
- **CLI E2E** (if CLI tool)
- **Database E2E** (if data-heavy)

**Integration**: Add E2E test patterns to TEST phase documentation

---

### Idea 6: Quality Gates (HIGH IMPACT)

**Borrow from**: `quality-validation` (qodex-ai, 100/100 security)

**Current `/code`**: Manual verification in DONE phase

**Enhanced with quality gates**:
- **Pre-commit gates**: Block commits if quality checks fail
- **Pre-merge gates**: Block PRs if quality threshold not met
- **Pre-deploy gates**: Block deployment if coverage < threshold
- **Automated enforcement**: Not optional (current /code is too optional)

**Integration**: Add blocking quality checks at phase boundaries

---

## Top 5 Skills to Investigate Further

| Priority | Skill | Source | Stars | Why Investigate |
|----------|-------|--------|-------|-----------------|
| 1 | **tdd-workflow** | SkillsMP | 55,676 | RED→GREEN→REFACTOR enforcement patterns |
| 2 | **django-verification** | SkillsMP | 55,676 | Automated verification loop pattern |
| 3 | **phase-8-review** | SkillHub | 228 | Codebase quality verification methodology |
| 4 | **premortem** | SkillHub | 3,535 | Structured failure mode analysis |
| 5 | **lint-and-validate** | SkillsMP | 21,677 | Automatic quality control procedures |

---

## Action Items

### Short Term (Quick Wins)

1. **Study `tdd-workflow`** (affaan-m, 55,676 stars)
   - Extract RED→GREEN→REFACTOR enforcement patterns
   - Borrow coverage threshold enforcement
   - Learn framework-specific TDD patterns

2. **Study `django-verification`** (affaan-m, 55,676 stars)
   - Extract verification loop pattern
   - Learn automated fix-verify cycle
   - Apply to AUDIT phase

3. **Study `phase-8-review`** (popup-studio-ai, 228 stars)
   - Extract codebase verification methodology
   - Borrow gap analysis techniques
   - Apply to TRACE phase

### Medium Term (Strategic Enhancements)

4. **Investigate `premortem`** (parcadei, 3,535 stars)
   - Learn structured failure mode analysis
   - Integrate into PLAN phase pre-mortem step
   - Create pre-mortem checklist templates

5. **Study `Task Development Workflow`** (majiayu000, 82 stars)
   - Compare with /code workflow structure
   - Borrow task tracking patterns
   - Learn TDD-first planning integration

6. **Investigate `lint-and-validate`** (davila7, 21,677 stars)
   - Extract automatic quality control procedures
   - Integrate into AUDIT phase
   - Add pre-commit quality gates

### Long Term (Architecture Evolution)

7. **Study `Code` skill** (ClawHub, 1.18 relevance)
   - Compare architectural patterns
   - Learn verification strategies
   - Identify workflow orchestration improvements

8. **Study `end-to-end-orchestrator`** (majiayu000, 82 stars)
   - Learn team coordination patterns
   - Borrow multi-phase orchestration
   - Enhance scalability

9. **Study `Workflow Patterns`** (ClawHub, 1.04 relevance)
   - Learn TDD + phase checkpoint implementation
   - Compare phase boundary enforcement
   - Improve phase transition validation

---

## Risk Assessment

### Low-Risk Borrowing (Complementary, Non-Competing)

- **Testing patterns**: Enhances existing /code TEST phase
- **E2E patterns**: Fills gap (E2E not covered in /code)
- **Quality gates**: Adds automation (no manual workflow changes)
- **Pre-mortem framework**: Adds structure to existing 5-minute step

### Medium-Risk Borrowing (Requires Careful Integration)

- **TDD enforcement patterns**: Must not conflict with existing TDD loop
- **Verification loops**: Must not create infinite loops in AUDIT phase
- **Architecture validation**: Must integrate with existing PLAN phase
- **Task tracking**: Must not conflict with existing task list management

### High-Risk Borrowing (Requires Evaluation First)

- **Team coordination patterns**: /code is solo-dev focused, team features may not apply
- **Multi-phase orchestration**: /code already has 9 phases, adding more may confuse
- **Automated gates**: Too many blocking gates may slow down development
- **Framework-specific patterns**: Must not lock /code into specific technologies

---

## Implementation Strategy

### Phase 1: Research (Week 1)

1. **Install and study top 5 skills** (tdd-workflow, django-verification, phase-8-review, premortem, lint-and-validate)
2. **Document patterns** from each skill
3. **Map to /code phases**: Which pattern enhances which phase?
4. **Identify conflicts**: Any overlapping functionality?

### Phase 2: Prototype (Week 2)

1. **Select 1-2 high-impact patterns** (e.g., verification loop from django-verification)
2. **Create prototype integration** in test branch
3. **Verify compatibility**: Does it work with existing /code workflow?
4. **Measure impact**: Does it improve results? Slow down development?

### Phase 3: Integration (Week 3-4)

1. **Integrate proven patterns** into main /code skill
2. **Update documentation** with new patterns
3. **Create examples** showing enhanced workflow
4. **Version bump** to 2.20.0

### Phase 4: Validation (Week 5)

1. **Test with real projects**: Does it help?
2. **Gather feedback**: What works, what doesn't?
3. **Refine**: Adjust based on feedback
4. **Release**: Announce enhanced /code v2.20.0

---

## Success Metrics

**Quantitative**:
- Reduced bug rate (post-implementation bugs vs pre-implementation)
- Faster development time (hours saved vs time spent)
- Higher test coverage (pre vs post integration)
- Fewer user-reported issues

**Qualitative**:
- Better planning quality (pre-mortem structured)
- More consistent code review (automated checklists)
- Stronger quality gates (automated enforcement)
- Comprehensive testing strategies (E2E coverage)

---

## Conclusion

**30+ relevant skills** identified across SkillsMP, SkillHub, and ClawHub. Top priorities:

1. **TDD enforcement** (tdd-workflow, 55K stars) - Enhance Phase 5
2. **Verification loops** (django-verification, 55K stars) - Enhance Phase 7
3. **Codebase verification** (phase-8-review, 228 stars) - Enhance Phase 8
4. **Pre-mortem framework** (premortem, 3.5K stars) - Enhance Phase 4
5. **Quality automation** (lint-and-validate, 21K stars) - Enhance Phase 7

**Next step**: Install and study top 5 skills to extract borrowable patterns for /code enhancement.
