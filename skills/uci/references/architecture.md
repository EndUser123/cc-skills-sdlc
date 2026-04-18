# UCI Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      /uci (Unified Code Inspection)                │
├─────────────────────────────────────────────────────────────────────┤
│  Intelligent Mode Detection:                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  │
│  │   TRIAGE    │  │  STANDARD    │  │    DEEP      │  │  COMP   │  │
│  │  (auto)     │  │  (auto)      │  │   (auto)     │  │ (auto)  │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └─────────┘  │
│  ───────────────────────────────────────────────────────────────── │
│  Override Flags:  --lite (force triage)  |  --full (force comp)    │
├─────────────────────────────────────────────────────────────────────┤
│  Context Signals for Auto-Detection:                               │
│  • Risk indicators (auth, security, payments)                      │
│  • File count (1-2 → triage, 15+ → deep, 50+ → comprehensive)      │
│  • Line count (<100 → triage, 2000+ → comprehensive)               │
│  • File types (.md only → triage, .py/.js → standard/deep)         │
│  • Change type (bug_fix → standard, new_feature → deep)            │
├─────────────────────────────────────────────────────────────────────┤
│  Intelligent Sequential Trigger (NEW):                             │
│  • Conditional triggering based on code characteristics              │
│  • Codebase analysis: state-heavy, concurrency, security, flow     │
│  • Early finding patterns: density, severity clusters, coupling     │
│  • Only triggers when expected benefit > 600% overhead              │
│  • Default: parallel-only (opt-in sequential when justified)        │
├─────────────────────────────────────────────────────────────────────┤
│  Shared Core Layer:                                                │
│  • Scope detection priority                                        │
│  • Intelligent mode detection                                     │
│  • Intelligent sequential trigger (conditional)                    │
│  • Impact/Effort matrix calculation                                 │
│  • Three-tier verdict synthesis                                     │
│  • Constitutional filter (solo-dev compliance)                     │
│  • Cross-agent validation (line-number confirmation)               │
│  • Pre-existing issue detection                                    │
│  • Circuit breaker (LLM provider resilience)                       │
│  • Memory Integration (CKS cross-session learning)                │
│  • Parallel agent orchestration (default)                          │
└─────────────────────────────────────────────────────────────────────┘
```
