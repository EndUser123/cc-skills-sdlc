# Subagent Output Routing Rules

When using subagents (team/hybrid/subagents execution mode):

## Subagent Result Envelope

Every subagent writes detailed output to disk and returns only a small envelope to the orchestrator. See canonical spec: `.claude/skills/shared/result-envelope.md`.

```json
{
  "status": "done" | "blocked" | "retry",
  "artifact": "relative/path/to/output/file.ext",
  "summary": "<=3 short lines -- no code, no diffs, no large analysis",
  "metrics": { "artifact_bytes": 4821, "files_read": 3 }
}
```

The orchestrator consumes only Result Envelopes plus selective reads of artifacts; it never inlines full artifact content into its own context.

## Routing Rules

- **Phase boundaries = context resets** -- use the handoff system between major phases; new session reads phase summary, not full history.
- **Sequential by default within a phase** -- tasks that produce large artifacts (full diffs, complete implementations, long analyses) are high-output and must run sequentially. Tasks that produce only metadata, verdicts, or short structured JSON are low-output and may run in parallel.
- **Spike before high-output tasks** -- when a task would produce a large artifact, write type signatures and interfaces only first and review before full implementation.
- **Targeted file reads** -- when only part of a file is relevant, use `Grep` + `offset`/`limit`. If a full read is genuinely needed and the file is clearly large, write a summary artifact and return a pointer; do not inline the full content.
- **Pass task excerpts, not full plans** -- brief each subagent with only the relevant task block.
