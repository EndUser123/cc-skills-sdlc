# Unified SQA Quality Model (11-Layer)

## 1. The Quality Layers

| Layer | Name | Focus |
|-------|------|-------|
| **L0** | **CHECKLIST** | Fast-fail structural check (Frontmatter, registration, file existence). |
| **L0** | **PREDICTIVE** | Adversarial specialist dispatch (16 specialists for logic, security, IO). |
| **L1** | **SYNTACTIC** | Static analysis (Ruff, Mypy, AI Distiller). |
| **L2** | **SEMANTIC** | Test execution (Pytest, coverage, TDD Build). |
| **L3** | **STRUCTURAL** | Cross-file analysis (Circular deps, assertion guards, safety patterns). |
| **L4** | **REQUIREMENTS** | Spec compliance (GTO, ARD/PRD sync). |
| **L5** | **SECURITY** | Path traversal, anti-bleed gates, CVE/Deprecated API scan. |
| **L6** | **PERFORMANCE** | Bottleneck analysis, thread-to-CPU mismatch, perf tracing. |
| **L7** | **OPERATIONAL** | Hook chain audit, multi-terminal isolation, stale-data invalidation. |
| **L8** | **E2E** | End-to-end workflow invocation and side-effect verification. |
| **META** | **SYNTHESIS** | Consensus detection, blind-spot detection, evidence quality. |
| **L9** | **CONTRACTS** | Producer/consumer boundary proof (CAP alignment). |

## 2. Focus Lenses
- `risk`: Pre-mortem failure analysis.
- `gaps`: Completeness and unhandled cases.
- `security`: Prioritize adversarial-security and path traversal.
- `comprehensive`: All lenses elevated to blocking.

## 3. Health Score & Severity
**Formula**: `health_score = max(-100, 100 - Σ(severity_weight × evidence_tier_factor))`
- **CRITICAL**: 20 pts | **HIGH**: 10 pts | **MEDIUM**: 5 pts | **LOW**: 2 pts.
- **Evidence Tiers**: T1=1.0x, T2=0.75x, T3=0.5x, T4=0.25x.

## 4. Operational Principles
### Two-Sided Enforcement
Durable correctness requires both **write-time** (producer) and **consume-time** (consumer) validation.
- One-sided enforcement at any boundary is a **HIGH** finding.

### Halt-on-Impact
Execution stops after any layer if raw findings exceed the `--halt-on` threshold (default: HIGH).

### Exit Criteria Validation
After every layer, run verification commands (exit codes, parse JSONs) before trusting self-reported results.

## 5. Auto-Fix Loop
- **L1/L2**: Safe fixes (imports, formatting) via `ruff --fix`.
- **L3+**: Iterative fix loop (max 5 iterations) delegating to `/code` for specific issues.
