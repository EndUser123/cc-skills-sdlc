# CLI Architecture Analysis

## Template Metadata
- **Target Complexity:** Any
- **Target Domain:** CLI/POSIX
- **Expected Output Size:** ~8 KB
- **Execution Instructions:** Read steps, execute in order, do not restate.

## Common Glossary
- **ARCHITECTURE_REVIEW:** Query asks to review/evaluate proposed design or architecture
- **IMPROVE_SYSTEM:** Query asks to optimize/harden existing subsystem
- **DEFAULT:** General architecture decision without improvement intent
- **CKS.db:** Constitutional Knowledge System

## Execution Instructions

**Do not:** Restate these instructions, summarize, or paraphrase.

**Do:**
1. Execute steps sequentially
2. Follow decision tree exactly
3. CLI/POSIX specific analysis
4. Stop at each decision point and evaluate

---

## Stage 0: Detect Intent Type

From the user query, identify:

**Is this an ARCHITECTURE_REVIEW request?**
- Keywords: review, evaluate, assess, analyze, audit, validate, critique
- Context: design, architecture, integration, proposal, theoretical
- **If YES:** Proceed to "Stage 0: ARCHITECTURE_REVIEW Path" (below)

**Is this an IMPROVE_SYSTEM request?**
- Keywords: improve, optimize, harden, stabilize, enhance, strengthen
- Subsystem: memory, CKS, hooks, research, retro, lesson, ingestion, validation
- **If YES:** Proceed to "IMPROVE_SYSTEM" below

**Otherwise (DEFAULT):**
- Proceed to "DEFAULT" below

---

## Stage 0.1: Constitutional Compliance Check (MANDATORY)

**Before proceeding to any decision path, evaluate:**

### Multi-Terminal Isolation & Stale Data Immunity

**For ALL architecture decisions, evaluate:**

1. **Identify shared mutable state**: Does this design create or modify files, databases, or in-memory state that could be accessed by multiple terminals?

2. **Assess concurrency safety**: Can multiple Claude Code terminals execute this pattern simultaneously without:
   - Data races (corrupted state)
   - Stale reads (terminal A sees outdated state)
   - Lost updates (write from terminal A overwrites terminal B silently)

3. **Check propagation mechanisms**: If state changes, how do other terminals discover the change?
   - File-based state: Requires polling or file system events
   - Database-based state: Requires query or notification mechanism
   - In-memory state: Cannot propagate across terminals (violates isolation)

4. **Document edge cases**: What happens when:
   - Terminal A writes while terminal B reads?
   - Two terminals write simultaneously?
   - A terminal crashes mid-operation?
   - Network filesystem has delays?

**Red flags that REQUIRE explicit mitigation:**
- ❌ Shared JSON/YAML files without atomic write + locking
- ❌ SQLite databases without WAL mode or proper transaction isolation
- ❌ In-memory caches without per-terminal isolation
- ❌ File locking assumptions (flock doesn't work across all platforms)
- ❌ Assumptions that only one terminal will run at a time

**Required output:**
- If design is multi-terminal safe: Document the isolation mechanism
- If design is single-terminal only: Explicitly state limitation + migration path
- Always document edge cases and failure modes

---

## Stage 0: ARCHITECTURE_REVIEW Path

**Purpose**: Evaluate proposed architecture/design WITHOUT recommending alternatives or suggesting implementation first.

### Scope Constraints

**CRITICAL: Architecture reviews are valid EVEN for theoretical/unimplemented designs.**

**DO:**
- Identify gaps and risks in the proposed design
- Evaluate against best practices (from web research in Stage 0.7)
- Assess feasibility and complexity
- Flag missing components or edge cases
- Cite evidence (files, lines, docs) for each finding

**DO NOT:**
- Suggest skipping or delaying the work
- Recommend installation before review
- Propose alternative architectures (that's DEFAULT path)
- Gatekeep based on implementation status
- Declare design "premature" due to lack of installation
- Tell user to "implement first, then review"

### Key Principle

> **Architecture reviews exist PRECISELY to evaluate designs BEFORE implementation.**
> Theoretical designs deserve rigorous analysis precisely to prevent costly mistakes.
> If the design were already implemented, we wouldn't need a review—we'd test it instead.

### Review Stages

1. **Scope Verification** — Confirm understanding of what's being reviewed
2. **Gap Analysis** — Identify missing elements from proposed design
3. **Risk Assessment** — What could fail, based on research + design analysis
4. **Evidence Table** — Each finding MUST be backed by:
   - Specific file:line from codebase (if applicable)
   - Specific line from design document/proposal
   - External source (web research, standards, best practices)

### Output Format

## Architecture Review: [Title]

### Scope
[What was reviewed - 1-2 sentences]

### Design Summary
[Brief description of what the design proposes - 2-4 sentences]

### Findings

| ID | Severity | Finding | Evidence | Impact |
|-----|-----------|----------|-----------|---------|
| ARCH-001 | HIGH | [description] | [file:line or source] | [consequence] |
| ARCH-002 | MEDIUM | [description] | [file:line or source] | [consequence] |
| ARCH-003 | LOW | [description] | [file:line or source] | [consequence] |

### Risk Summary
- Technical: [summary]
- Operational: [summary]
- Integration: [summary]

### Conclusion
[Overall assessment - proceed with caution / needs clarification / looks viable with noted gaps]

---
**Confidence:** [X]%

**Evidence basis:**
- Design doc: [source]
- Web research: [count] sources
- Codebase analysis: [files reviewed]

**Key assumptions:**
1. [assumption]
2. [assumption]

### Multi-Command App
```python
@click.group()
def cli():
    """My CLI app with subcommands."""
    pass

@cli.command()
def init():
    """Initialize project."""
    pass

@cli.command()
def build():
    """Build project."""
    pass

---

## Output Format

Structure your recommendation as:

### 1. Framework Recommendation
- **Chosen framework:** [Click/Typer/argparse/Cliff/Other]
- **Rationale:** Why this fits use case
- **Trade-offs:** What you're giving up

### 2. Architecture Pattern
- **Single-command vs multi-command:**
- **Subcommands needed:** List if applicable
- **Flag style:** GNU style (`--long`, `-short`)

### 3. POSIX Compliance Checklist
- [ ] Exit codes defined
- [ ] stdout/stderr separated
- [ ] Signal handling implemented
- [ ] Pipeline-friendly output

### 4. Terminal UX
- [ ] Help text completeness
- [ ] Progress indicators (if applicable)
- [ ] Color output with NO_COLOR respect
- [ ] Pagination (if applicable)

### 5. Shell Integration
- [ ] Completion scripts (bash/zsh/fish)
- [ ] Config file locations (XDG)
- [ ] Environment variable conventions

---

## Success Criteria

- POSIX-compliant exit codes
- stdout/stderr correctly separated
- SIGINT/SIGTERM handled gracefully
- Help text clear and complete
- Colors respect NO_COLOR
- Terminal size awareness (if applicable)
- Config follows XDG conventions

---

## Final Output Block

**Decision:** [One sentence recommendation]

**Rationale:** [2-3 key reasons, domain-specific]

**Alternatives Considered:** [Brief list with domain trade-offs]
> Apply **Forced Alternative Quality Gate** — each alternative must differ on at least one axis.

**Risk:** [Domain-specific risks]

> Apply **Version Verification Rule** — verify all CLI framework version/API claims against official docs.

**Confidence:** [X]% — [evidence basis]
> Apply **Confidence Calibration Rules** from `shared_frameworks.md`.

**Adversarial Self-Review:** (Recommended)
> One-line weakest assumption + consequence per `shared_frameworks.md`.

**Persist:** Auto-save to `P:/.claude/arch_decisions/` per **Output Persistence** protocol.

```python
# Filename format (use actual datetime, do not hardcode date)
from datetime import datetime
date = datetime.now().strftime("%Y-%m-%d")
slug = re.sub(r'[^a-z0-9]+', '-', query[:50].lower()).strip('-')
filename = f"{date}_cli_{slug}.md"

---
*End of CLI template. Falls back to generic decision format.*
