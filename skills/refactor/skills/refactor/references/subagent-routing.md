# Subagent Output Routing Rules

## Subagent Result Envelope

Every agent writes findings to disk (e.g., `.claude/state/agent-{name}.json`) and returns only a small envelope. See canonical spec: `.claude/skills/shared/result-envelope.md`.

```json
{
  "status": "done" | "blocked" | "retry",
  "artifact": ".claude/state/agent-quality.json",
  "summary": "≤3 short lines — no code, no diffs, no large analysis",
  "metrics": { "artifact_bytes": 2048, "files_read": 4 }
}
```

The orchestrator consumes only Result Envelopes plus selective reads of artifacts; it never inlines full artifact content into its own context.

## Routing Rules

- **Phase boundaries = context resets** — use the handoff system between discovery→plan→execute; new session reads summary file, not full history.
- **Sequential by default** — discovery agents that produce long analysis artifacts are high-output and must run sequentially. Classification-only or metadata agents are low-output and may run in parallel.
- **Targeted file reads** — use `Grep` to locate relevant sections first, then `Read` with `offset`/`limit`. When only part of a file is relevant, read only that part. If a full read is genuinely needed and the file is clearly large, write a summary artifact and return a pointer; do not inline the full content.
- **Spike before high-output refactors** — when a refactor would produce a large diff, produce a type-signature-only diff first and review before full implementation.
