# cc-skills-sdlc

SDLC skills for Claude Code — architecture, planning, code quality, testing, review, and documentation.

## Skills (39)

| Skill | Purpose |
|-------|---------|
| adversarial-review | Parallel adversarial code review with 8 specialized perspectives |
| arch | Architecture validation and ADR workflow |
| av | Adversarial review variant |
| code | Code implementation with evidence tracking |
| code-flow-visualizer | Code flow analysis and visualization |
| code-review | General code review |
| code-reviewer-business-logic | Business logic focused review |
| critical-code-reviewer | Critical path review |
| diagnose | Diagnostic workflow |
| docs | Documentation generation |
| docs-validate | Documentation validation |
| mermaid-c4 | C4 architecture diagrams |
| mermaid-davila7 | Davila7 architecture diagrams |
| meta-review | Review of reviews |
| multi-file-refactor | Cross-file refactoring |
| perf | Performance analysis |
| performance-profiler | Detailed performance profiling |
| planning | Implementation plan creation and verification |
| prd | Product requirement documents |
| pre-mortem | Failure-mode analysis with phased output |
| prrp | Production-ready code review prompt |
| python-backend-reviewer | Python-specific code review |
| qmd-wiki | Wiki page generation |
| rca | Root cause analysis with hook enforcement |
| refactor | Refactoring with plan-and-review |
| review_bundle | Review bundle aggregation |
| spec-compliance | Spec compliance validation |
| sqa | Software quality assurance (8-layer) |
| sqd | Software quality diagnostics |
| t | Context-aware adaptive testing with ToT enhancement |
| tdd | Test-driven development with evidence |
| tldr-code | Token-efficient code analysis (5-layer stack) |
| tldr-deep | Full 5-layer analysis of specific functions |
| tldr-overview | Overview-level code analysis |
| tldr-router | Router for tldr analysis variants |
| tldr-stats | Statistics for tldr analysis |
| uci | Unified code inspection |
| wiki | Wiki management |

## Artifacts Convention

All runtime artifacts (evidence, state, reports) write to:

```
P:/.claude/.artifacts/{terminal_id}/<skill-name>/
```

`terminal_id` comes from `CLAUDE_TERMINAL_ID` env var (falls back to `"default"`).

Skills MUST NOT write state to their own directory or to the package root. The `.gitignore` covers `.evidence/`, `.state/`, `.benchmarks/`, `__pycache__/`, `.claude/` to prevent accidental tracking.

## Installation

Skills are surfaced via junctions in `.claude/skills/`:

```powershell
New-Item -ItemType Junction -Path "P:/.claude/skills/<name>" -Target "P:/packages/cc-skills-sdlc/skills/<name>"
```

Command frontends live in `.claude/commands/<name>.md` and reference the junction target.
