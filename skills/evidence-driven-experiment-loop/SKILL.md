---
name: evidence-driven-experiment-loop
description: Manage evidence-first experiments, benchmarks, performance optimization, A/B comparisons, repeated evidence gathering, live-run decisions, and fresh-agent handoffs with explicit lifecycle gates and deterministic delegated goals.
---

# Evidence-Driven Experiment Loop

Use `scripts/experiment_loop.py` to initialize, validate, compile, and hand off
an experiment state. Read `references/state-schema.md` before editing state.

1. Initialize a JSON state with `init`, then fill evidence, claims, and gates
   from authoritative artifacts.
2. Advance only through the lifecycle states in schema order. Keep authority
   checks, attribution, instrumentation, decision, telemetry, mechanism,
   implementation, and throughput validation distinct.
3. Run `validate` before delegating or acting. Treat validation errors as a
   stop condition; do not infer missing authorization or verification.
4. Use `goal` to emit the bounded delegated condition. Preserve every safety
   field and stop when the requested character budget cannot contain them.
5. Use `handoff` for a concise parent packet. Report verified evidence,
   unresolved claims, gates, and the next action without inventing conclusions.

Keep strategy and final judgment with the parent. Workers may gather only
bounded evidence permitted by `allowed_actions`; they must obey
`forbidden_actions`, falsifiers, abort gates, and promotion rules. Do not run
live work without explicit authorization represented in state and accepted by
validation.
