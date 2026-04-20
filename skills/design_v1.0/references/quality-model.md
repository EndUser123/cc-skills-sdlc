# Quality Model Reference

## 8 Architectural Lenses

Every architecture option is evaluated through 8 lenses derived from ISO 25010 and Cloud Framework Pillars.

### 1. Functional Suitability
**Question**: Does the design provide the right capabilities for the problem?
**ISO 25010**: Functional completeness, correctness, appropriateness
**Evaluation**: Map features to requirements; identify gaps and over-engineering

### 2. Performance Efficiency
**Question**: Does the design meet performance requirements within resource bounds?
**ISO 25010**: Time behavior, resource utilization, capacity
**Evaluation**: Profile hot paths; estimate memory/CPU/I/O; identify bottlenecks

### 3. Compatibility
**Question**: Can the design interoperate with existing systems and dependencies?
**ISO 25010**: Co-existence, interoperability
**Evaluation**: Map integration points; check API contracts; verify protocol compatibility

### 4. Usability
**Question**: Is the design learnable and operable by the target users?
**ISO 25010**: Learnability, operability, user error protection, accessibility
**Evaluation**: Count user steps for common operations; identify error-prone paths

### 5. Reliability
**Question**: Does the design perform consistently under specified conditions?
**ISO 25010**: Maturity, availability, fault tolerance, recoverability
**Evaluation**: Identify failure modes; design recovery paths; estimate MTBF/MTTR

### 6. Security
**Question**: Does the design protect information and operations from unauthorized access?
**ISO 25010**: Confidentiality, integrity, non-repudiation, accountability, authenticity
**Evaluation**: Threat model; identify trust boundaries; validate input/output handling

### 7. Maintainability
**Question**: Can the design be modified, corrected, or adapted efficiently?
**ISO 25010**: Modularity, reusability, analysability, modifiability, testability
**Evaluation**: Count coupling points; assess cohesion; estimate change cost

### 8. Portability
**Question**: Can the design be transferred to different environments?
**ISO 25010**: Adaptability, installability, replaceability
**Evaluation**: Identify environment-specific assumptions; count external dependencies

---

## Quality Tradeoff Analysis

For each option, identify:

| Aspect | Description |
|--------|-------------|
| **Favored quality** | Which ISO 25010 quality attribute does this option maximize? |
| **Degraded quality** | Which quality attribute is sacrificed? |
| **Failure conditions** | Under what circumstances does this option fail to deliver? |
| **Blast radius** | If this option fails, what is the impact scope? |

---

## Cloud Framework Pillar Lenses

In addition to ISO 25010, evaluate through cloud architecture pillars:

| Pillar | Relevance to /arch | Key Question |
|--------|-------------------|--------------|
| **Cost Optimization** | Solo dev cost awareness | Does this design minimize unnecessary resource costs? |
| **Operational Excellence** | CLI-centric workflow | Can this be operated and monitored by a solo developer? |
| **Reliability** | Multi-terminal safety | Does this design survive terminal crashes and concurrent access? |
| **Performance Efficiency** | Local execution | Does this design avoid unnecessary I/O or computation? |
| **Security** | Local-first constraints | Does this design avoid exposing secrets or sensitive data? |

---

## Lean System Design Principles

| Principle | Description |
|-----------|-------------|
| **Value optimization** | Focus on the ~80% value delivered by ~20% of the effort |
| **Extension over creation** | Prefer extending existing patterns over creating new ones |
| **Dependency pruning** | Classify dependencies as MUST/SHOULD/MAY; minimize MUST |
| **Contract-first design** | Define boundaries before implementation |
| **Core vs extended plans** | v1 = 5-10 tasks for ~80% value; extended = remaining 20% |
| **Environment alignment** | Design for the actual deployment environment (Windows 11, CLI, solo dev) |

**Opt-out**: `--no-lean` flag

---

## Graph-of-Thought (GoT) Integration

GoT is **enabled by default**. It extracts architecture nodes, analyzes edge relationships, detects circular dependencies, and provides multi-alternative comparison.

### Node Types
- `DECISION`: An architectural choice
- `CONSTRAINT`: A limiting factor
- `DEPENDENCY`: A required component or service
- `RISK`: A potential failure mode
- `TRADEOFF`: A quality tradeoff

### Edge Types
- `SUPPORTS`: One node strengthens another
- `CONTRADICTS`: One node weakens or conflicts with another
- `DEPENDS`: One node requires another
- `MITIGATES`: A risk reduction relationship

### Scoring Dimensions
| Dimension | Description |
|-----------|-------------|
| Feasibility | Can this be implemented with current constraints? |
| Completeness | Does this address all aspects of the problem? |
| Novelty | Is this meaningfully different from standard approaches? |
| Risk | What is the failure probability and impact? |

**Opt-out**: `export ARCH_NO_GOT=true` or `--no-got` flag
