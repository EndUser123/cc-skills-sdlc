# cc-skills-sdlc

SDLC skills for Claude Code — architecture, planning, code quality, testing, and review.

## Skills (17)

| Skill | Purpose |
|-------|---------|
| arch | Architecture validation and ADR workflow |
| code | Code implementation with evidence tracking |
| mermaid-c4 | C4 architecture diagrams |
| mermaid-davila7 | Davila7 architecture diagrams |
| planning | Implementation plan creation and verification |
| prd | Product requirement documents |
| pre-mortem | Failure-mode analysis with phased output |
| qmd-wiki | Wiki page generation |
| rca | Root cause analysis with hook enforcement |
| refactor | Refactoring with plan-and-review |
| review_bundle | Review bundle aggregation |
| sqa | Software quality assurance (8-layer) |
| sqd | Software quality diagnostics |
| tdd | Test-driven development with evidence |
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
