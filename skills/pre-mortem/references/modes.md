# Pre-Mortem Modes

Adapters should expose these modes without weakening the common method.

## quick

Use for small edits or immediate "check predictable problems" requests.

- Single-agent pass.
- Static investigation by default.
- No specialist dispatch by default.
- Output only the highest-value findings and required verification.
- Must still include data-safety checks when deletion, cleanup, migration, auth, or external services are involved.

## standard

Use for implementation plans, non-trivial code changes, benchmark readiness, and operational changes.

- Review static risks, live/runtime risks, data safety, dependency chain, and verification.
- Separate static findings from non-static probes that were run or are recommended.
- Load project-specific profiles when present.
- Produce the full output contract.

## deep

Use for Claude Code primary agentic reviews, major architecture changes, high-risk live runs, or RCA-quality investigations.

- Use the Claude specialist dispatch workflow.
- Include explicit static vs non-static investigation coverage in synthesis.
- Require Phase 1 specialist findings, Phase 2 meta-critique, and Phase 3 synthesis.
- Preserve completion gates and evidence-bound verification.
