# cc-skills-sdlc

SDLC skills for Claude Code — architecture, planning, code quality, testing, review, and documentation.

## Skills (49)

| Skill | Purpose |
|-------|---------|
| arch | Architecture Advisor (Resource Router) |
| av | Skill Improvement Tool |
| cfg | /cfg - Control Flow Graph Visualization |
| chat-to-decisions | God-Tier Chat-to-Decisions v12 |
| code | /code -- Feature Development Mission Control |
| code-flow-visualizer | Code Flow Visualizer |
| code-review | Code Review — Automated Multi-Agent Review |
| code-reviewer-business-logic | Business Logic Reviewer (Correctness) |
| critical-code-reviewer | Mindset |
| deliberate-changes | Deliberate Changes Management |
| deps | /deps - Dependency Management |
| design | Architecture Advisor (Resource Router) |
| diagnose | Structured Diagnostic Protocol |
| docs | /docs - Documentation Automation |
| docs-validate | Documentation Quality Validation |
| dpef | DPEF - Deterministic Prompt Execution Framework |
| go | /go — Local PR-Ready Ralph Loop |
| harden | /harden |
| mermaid-c4 | Mermaid Diagrams |
| mermaid-davila7 | Mermaid Diagramming |
| meta-review | Meta-Review Skill |
| multi-file-refactor | Code Editing Patterns |
| perf | /perf - Performance Tracing Wrapper |
| performance-profiler | Performance Profiler |
| planning | Plan Workflow v2 |
| prd | PRD — Product Requirements Document |
| pre-mortem | Critique — Adaptive Adversarial Review |
| profile | /profile - Performance Baseline & Comparison |
| prrp | Production-Ready Review Prompt (PRRP) |
| python-backend-reviewer | Python Backend Code Reviewer |
| qmd-wiki | qmd-wiki |
| rca | Debug RCA Skill v2.12.0 |
| review_bundle | Review Bundle Creation |
| ship | /ship — Deploy readiness and runtime snapshot |
| snapshot | /snapshot — Session snapshot capture and restore (moved to snapshot package) |
| spec-compliance | Purpose |
| specify | Specify — Detailed Specification |
| sqd | /sqd — SDLC Quality Dispatcher |
| staging-protocol | Code Editing Patterns |
| step-6-5 | Step 6.5 - Generate ORCHESTRATION.md |
| synergy | Code Editing Patterns |
| system-internals-verification | Purpose |
| t | Code Editing Patterns |
| task | /task — Task list orchestration |
| team | /team — Multi-agent task coordination |
| tdd | TDD - Test-Driven Development with PARALLEL Delegation |
| tilldone | /tilldone — Batch convergence runner |
| tldr-code | TLDR-Code: Token-Efficient Code Analysis |
| tldr-deep | TLDR Deep Analysis |
| tldr-overview | TLDR Project Overview |
| tldr-router | TLDR Smart Router |
| tldr-stats | TLDR Stats Skill |
| uci | Unified Code Inspection (`/uci`) |
| wiki | /wiki — Obsidian Wiki + QMD Search Skill |

## Artifacts Convention

All runtime artifacts write to:



 from  env var (falls back to ).

Skills MUST NOT write state to their own directory or to the package root.

## Installation

Skills surfaced via junctions in :



Command frontends live in .
