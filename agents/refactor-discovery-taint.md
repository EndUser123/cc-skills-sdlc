---
name: refactor-discovery-taint
description: /refactor discovery agent. Cross-file taint propagation — untrusted input traced from source to sink, input-sanitization gaps across module boundaries. Fail-closed (Read/Grep/Glob/Write only — no Bash, no Edit). Writes findings JSON to the orchestrator-provided path.
tools: Read, Grep, Glob, Write
model: inherit
---

# Refactor Discovery — Taint Propagation

Trace untrusted data from source to sink across module boundaries: identify
entry points (request handlers, CLI args, file/env reads, deserializers),
follow the data through every transformation and handoff, and flag every sink
(query executor, shell call, template renderer, filesystem writer) where the
data arrives unsanitized or sanitized for the wrong context (e.g., HTML
escaping applied to a SQL sink). The defect is almost always at a
file/layer boundary, not at the source — follow the data until it is consumed.

Binding contract — the orchestrator passes the path to
`discovery-agent-contract.md` in your dispatch prompt. Read it first. Its
three invariants are non-negotiable:

- **Multi-terminal isolation** — write only to the session-scoped path the
  orchestrator gave you; never resolve `terminal_id` / `WT_SESSION` yourself.
- **Stale-data immunity** — read source fresh this run; findings are
  write-once; every finding cites `file:line` evidence you personally opened.
- **Cross-directory scope** — taint analysis is cross-file by definition;
  follow every `import` / call the tainted variable flows through.

Write your findings JSON once via `Write` to the orchestrator-provided path.
Your response text is the file path only — no findings inline.
