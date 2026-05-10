# Architecture Advisor Skill (/arch)

[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen)](https://github.com/brsth/claude-skills)
[![Tests](https://img.shields.io/badge/tests-291%20passed-success)](https://github.com/brsth/claude-skills)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

Adaptive architecture advisor with template-based variants. Auto-routes to appropriate template based on domain and complexity. Supports: fast, deep, cli, python, data-pipeline, precedent.

The `/arch` skill provides intelligent architecture guidance by analyzing user queries and routing them to specialized templates. It uses keyword detection, configuration files, and complexity analysis to select the most appropriate architecture template.

## Features

| Feature | Description |
|---------|-------------|
| **Template-based routing** | Auto-routes queries to specialized templates (fast, deep, cli, python, data-pipeline, precedent) |
| **Domain detection** | Intelligent keyword-based domain detection with configuration override support |
| **Cascading configuration** | Project-level, user-level, and environment variable configuration with priority handling |
| **Template chaining** | Support for combining up to two templates (e.g., `python+data-pipeline`) |
| **CKS integration** | Optional Constitutional Knowledge System integration for enhanced architecture decisions |
| **Output persistence** | Auto-save architecture decisions to searchable archive |
| **Prerequisite analysis** | Smart gating to prevent false positives on optimization queries |
| **One-page ADR template** | Lightweight Architecture Decision Records for significant changes |
| **ARCHITECTURE.md guidance** | Repository-level documentation norms with hybrid approach |
| **Graph-aware reasoning** | Graph-based thinking prompts for component/dependency analysis |
| **GoT Controller operations** | Graph-of-Thought reasoning for enhanced architecture evaluation |
| **87% test coverage** | Comprehensive test suite with 291 passing tests |

## Architecture

```
arch/
├── config.py                   # Configuration loader with cascading priority
├── routing.py                  # Template routing and validation logic
├── persistence.py              # Decision persistence and archival
├── prerequisite_analyzer.py    # Semantic analysis for prerequisite gates
├── validate_templates.py       # Template validation and duplicate detection
├── cross_platform_paths.py     # Cross-platform path resolution
├── path_detection.py           # Template path detection utilities
├── resources/                  # Architecture templates
│   ├── fast.md                 # Quick decisions (5-15 min, ~5 KB)
│   ├── deep.md                 # Comprehensive analysis (40-90 min, ~15-30 KB)
│   ├── cli.md                  # CLI/POSIX specific
│   ├── python.md               # Python 3.12+ specific
│   ├── data-pipeline.md        # Data systems specific
│   ├── precedent.md            # ADR documentation
│   └── shared_frameworks.md    # Shared template frameworks
└── tests/                      # 35 test files, 87% coverage
```

## Installation

The `/arch` skill is part of the Claude Code skills ecosystem. Clone this repository to your skills directory:

```bash
git clone https://github.com/brsth/claude-skills.git
cp -r claude-skills/arch ~/.claude/skills/
```

### Configuration

Create a `.archconfig.json` file in your project root:

```json
{
  "$schema": "./.archconfig.schema.json",
  "default_domain": "python",
  "output_size": "normal",
  "evidence_level": "standard"
}
```

**Configuration priority:**
1. Project config: `.archconfig.json` (in project root)
2. User config: `~/.archconfig.json`
3. Environment variable: `ARCH_DEFAULT_DOMAIN`
4. Keywords: Auto-detection from query

## Usage

### Basic Usage

```bash
# Auto-detect domain and complexity
/arch "improve memory system"

# Force specific template
/arch "redesign api" template=deep
/arch "cli tool" template=cli

# Template chaining (max 2 templates)
/arch "async data pipeline" template=python+data-pipeline
```

### Available Templates

| Template | Use Case | Output Size | Time |
|----------|----------|-------------|------|
| `fast` | Quick decisions, single file | ~5 KB | 5-15 min |
| `deep` | Complex decisions, multi-system | ~15-30 KB | 40-90 min |
| `cli` | CLI/POSIX specific | ~8 KB | 10-20 min |
| `python` | Python 3.12+ specific | ~10 KB | 15-25 min |
| `data-pipeline` | Data systems specific | ~12 KB | 20-30 min |
| `precedent` | ADR documentation | ~20 KB | 60-90 min |

### Valid Domains

- `cli` - CLI/POSIX architecture
- `python` - Python 3.12+ architecture
- `data-pipeline` - Data systems architecture
- `precedent` - ADR documentation
- `auto` - Keyword-based detection

## API Reference

### Core Modules

#### `config.py`
```python
from arch.config import load_arch_config, VALID_DOMAINS

# Load configuration with cascading priority
config = load_arch_config()
# Returns: {"default_domain": "python", "output_size": "normal", ...}
```

#### `routing.py`
```python
from arch.routing import select_template, validate_template

# Select template based on query analysis
result = select_template("improve memory system")
# Returns: {"template": "fast", "domain": None, "complexity": "fast"}

# Validate template name and file existence
validation = validate_template("fast")
# Returns: {"valid": True, "template": "fast", "path": Path(...)}
```

#### `persistence.py`
```python
from arch.persistence import save_arch_decision, should_skip_persistence

# Save architecture decision to archive
save_arch_decision(
    query="design API gateway",
    output="...",
    template="deep"
)

# Check if decision should be saved
if not should_skip_persistence(query, output):
    # Save to .claude/arch_decisions/
    pass
```

#### `prerequisite_analyzer.py`
```python
from arch.prerequisite_analyzer import PrerequisiteAnalyzer

# Analyze query for prerequisite gates
result = PrerequisiteAnalyzer.analyze("improve memory system")
# Returns: {"should_trigger_gate": False, "is_optimization": True}
```

## Metrics

- **Test Coverage**: 87% (3494 lines, 471 uncovered)
- **Test Count**: 291 passed, 11 skipped
- **Python Files**: 43 modules
- **Test Files**: 35 test modules
- **Templates**: 6 domain-specific templates
- **Valid Domains**: 5 (cli, python, data-pipeline, precedent, auto)

---

## v4.4 Feature Documentation

### One-Page ADR Template

For architecturally significant changes, `/arch` now recommends a lightweight one-page ADR format:

```markdown
# ADR-XXXX: [Decision Title]

**Status:** Proposed | Accepted | Superseded by ADR-YYYY
**Date:** YYYY-MM-DD
**Context:** [What problem does this solve?]

### Decision
[One-line decision statement]

### Rationale
[Why this approach - brief, 2-3 sentences]

### Tradeoffs
| Quality | Improved | Degraded |
|---------|----------|----------|
| [ISO 25010 quality] | [Benefit] | [Cost] |

### Multi-Terminal Safety
- [Safe / Single-terminal only / Needs investigation]

### Implementation
- [What changes: files, APIs, structures]
- [Testing approach]
- [Rollback: how to undo]

### Consequences
- **Positive:** [Benefits]
- **Negative:** [Costs/risks with mitigations]
```

**Location**: `P:\\\\\\.claude/arch_decisions/ADR-YYYYMMDD-[slug].md`

### ARCHITECTURE.md Guidance

For repository-level architecture documentation:

```markdown
# Architecture

## Components
[Key system components - brief descriptions]

## Invariants
[Core invariants - what must always be true]

## Pointers
- ADRs: `./.claude/arch_decisions/`
- Hooks: `./.claude/hooks/`
- Skills: `./.claude/skills/`
```

**Single Best Practice**: "Every major design change gets a one-page ADR" (preferred over maintaining ARCHITECTURE.md as source of truth)

**Rationale**: ADRs provide historical context (why vs what) and scale better with project growth.

### Graph-Aware Reasoning Prompts

When evaluating architecture, `/arch` applies graph-based reasoning:

1. **Node Extraction**: Components, Constraints, Risks
2. **Edge Relationships**: Dependencies, Contradictions, Supports
3. **Cycle Detection**: Circular dependencies, Layering, Coupling points
4. **Failure Mode Analysis**: Cascading failures, Single points of failure, Degradation patterns

**Optional graph.txt format** for visual documentation (complex architectures with >5 components):

```txt
# Architecture Graph: [System Name]

# Components
[ComponentA]
  depends_on: [ComponentB, ComponentC]
  provides: [ServiceX, ServiceY]
  risks: [SinglePointOfFailure]

# Relationships
ComponentA → ComponentB: synchronous_call

# Contradictions
ConstraintA contradicts IdeaB: [Explanation]

# Cycles Detected
[None] or [Cycle: ComponentA → ComponentB → ComponentA]
```

---

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `pytest`
2. Coverage remains above 85%: `pytest --cov=.`
3. New features include tests
4. Code follows Python 3.12+ standards

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Recent Enhancements

### v4.4 (2026-03-16)

**New Features:**
- **One-Page ADR Template**: Lightweight Architecture Decision Record format for significant design changes
- **ARCHITECTURE.md Guidance**: Repository-level architecture documentation with content norms (components, invariants, pointers)
- **Graph-Aware Reasoning**: Graph-based thinking prompts (node extraction, edge relationships, cycle detection, failure mode analysis)
- **Enhanced Tradeoff Articulation**: Merged Alternative Quality + Tradeoff Clarity lens for explicit tradeoff documentation

**Documentation Improvements:**
- Context Contract with explicit scope constraints and input requirements
- "When Not to Use /arch" section for domain boundary clarity
- Quality Model Mapping (ISO 25010, cloud frameworks as analogical lenses)
- Single Best Practice Recommendation: ADR over ARCHITECTURE.md for historical context

**Architecture Enhancements:**
- GoT Controller operations (Aggregate, Refine, Generate, Split)
- Scoring Dimensions (Relevance, Accuracy, Coherence)
- Optional graph.txt format for visual documentation

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

---

**Version:** 4.4 | **Architecture:** Template-based router with GoT Controller operations, ADR documentation, one-page ADR template, ARCHITECTURE.md guidance, graph-aware reasoning prompts, ARCHITECTURE_REVIEW intent type, review-first principle, three-path execution (ARCHITECTURE_REVIEW / IMPROVE_SYSTEM / DEFAULT), enhanced Context Contract, Tradeoff Articulation, and Quality Model Mapping
