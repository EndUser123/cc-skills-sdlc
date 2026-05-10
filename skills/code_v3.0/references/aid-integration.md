# AID Integration (v2.26.0)

**Enhanced codebase discovery via AI Distiller (AID):**

```python
from .arch.aid_integration import create_aid_integrator

# Generate enterprise-grade codebase analysis
integrator = create_aid_integrator()
result = integrator.analyze_codebase(target_path)
```

**AID `prompt-for-complex-codebase-analysis` provides:**

| Analysis Area | What it Provides | Value to /code |
|---------------|------------------|----------------|
| **Compliance & Governance** | Standards compliance, architectural standards, code quality patterns | Pre-implementation standards check |
| **Scalability Assessment** | Architectural bottlenecks, performance hotspots, resource constraints | Design informed by scalability realities |
| **Technical Debt Inventory** | Code quality issues, anti-patterns, refactoring opportunities | Debt-aware implementation planning |
| **Module Boundaries** | Dependency graph, module responsibilities, integration points | Dependency-aware design decisions |

**When to use AID for codebase discovery:**

- **Large/complex codebases** (>1000 files) - Use AID as initial discovery pass
- **Enterprise systems** - Leverage compliance and governance analysis
- **New to codebase** - Use AID to rapidly understand architectural patterns
- **Pre-implementation** - Run AID analysis before starting TDD to inform test design

**Workflow integration:**

1. **Phase 3 (EXPLORE)**: Run AID codebase analysis on target path
2. **Parse AID output**: Extract compliance, scalability, debt, and boundary findings
3. **Inform design**: Use AID findings when creating plan.md (Phase 4)
4. **Enhance TDD scenarios**: Design tests that address AID-identified issues

**Usage example:**

```python
from .arch.aid_integration import create_aid_integrator

# Run AID analysis during EXPLORE phase
integrator = create_aid_integrator()
analysis = integrator.analyze_codebase("src/")

# Use findings to inform plan.md and TDD scenarios
if analysis["scalability_bottlenecks"]:
    plan["architecture_notes"] += f"Known bottleneck: {analysis['scalability_bottlenecks'][0]}"
```

**Integration module**: `P:\\\\\\\.claude\\skills\\arch\\aid_integration.py`
