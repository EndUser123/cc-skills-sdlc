# Refactor Discovery Agent Contract

Binding on every `refactor-discovery-*` agent. Encodes the three invariants
every refactor discovery dispatch must honor — multi-terminal isolation,
stale-data immunity, and cross-directory analysis scope — plus the fail-closed
tool rationale and the output contract.

The orchestrator passes this document's path in the dispatch prompt. Read it
before analyzing.

## 1. Multi-terminal isolation (session-scoped artifacts)

**Artifact paths are keyed by `session_id`, never `terminal_id` / `WT_SESSION`.**
`WT_SESSION` is shared across every concurrent Claude session in one Windows
Terminal — keying by it makes two parallel `/refactor` runs overwrite each
other's findings. This is the documented anti-pattern
(`terminal_id` is NOT a per-session key).

The orchestrator computes the session-scoped findings path and passes it to
you. You do not resolve any scoping key yourself, and you never read
`CLAUDE_TERMINAL_ID` / `WT_SESSION` from the environment.

Canonical findings path:

```
P:/.claude/.artifacts/{session_id}/refactor/{target_slug}/findings-{role}.json
```

Write ONLY to the path the orchestrator gave you. Never write into the target
tree, the skill directory, the package root, or any path you constructed
yourself.

## 2. Stale-data immunity

- **Read source fresh every run.** Do not assume a file's contents from a
  prior run, a sibling agent's summary, or memory. Re-`Read` / re-`Grep`
  before you cite a line. Claims of absence require a confirmed
  Read/Grep/git failure in THIS dispatch, not "I didn't see it earlier."
- **Findings are write-once per dispatch.** Write your findings JSON in a
  single `Write` call to the orchestrator-provided path. Never append to,
  merge with, or read back a prior findings file. If the orchestrator signals
  `--rediscover`, it discards the old file before dispatching you — you never
  inherit a previous run's output.
- **Every finding cites evidence you personally read this run**: `file:line`
  plus a short quoted snippet. Description-only inference (you reasoned about
  a file you did not open) caps `confidence` at `unverified` — do not promote
  it to `high`.

## 3. Cross-directory analysis scope (DRY + multi-file defects)

Your scope is the **repository / module**, not just the passed target path.
Many refactor-worthy defects only surface across files:

- **duplicates** — the same function, class, or logic copied into sibling
  modules
- **circular dependencies** — import cycles that span packages
- **taint / interface mismatch** — a caller passes args a callee no longer
  accepts; escaping or validation differs between producer and consumer
- **shared mutable state** — module-level state read or mutated from
  multiple call sites, including across async boundaries

Use `Grep` with no path restriction and `Glob` broadly to trace symbols
across directories. When the target is one directory but a symbol is defined,
imported, or duplicated elsewhere — follow it. Report the cross-file
relationship in the finding's `failure_scenario` (e.g., "caller in
`api/router.py:88` passes raw user input; `db/query.py:201` escapes for LIKE
but not for `%` wildcards").

## 4. Fail-closed tools (why no Bash / Edit)

Your `tools:` are `Read, Grep, Glob, Write` only. You **cannot** edit source,
run shell commands, or dispatch further agents — by design.

Discovery must not mutate the code under analysis; the orchestrator and the
executor phase own mutation. A discovery agent that cannot mutate cannot
corrupt the working tree, cannot race a sibling agent's edit, and cannot ship
a half-applied change. This is the `tools:` hygiene invariant: omitting
`Bash`/`Edit` from a read-only subagent fail-closes it (agent `tools:` is hard
enforcement, not advisory).

If you believe an analysis needs a script (AST-based duplicate detection, an
import-cycle scanner, a test runner), do NOT attempt to run it — you have no
`Bash`. Return a `blocked` envelope naming the script and the question it
would answer; the orchestrator runs it and re-dispatches you with the output
inline.

## 5. Output contract

- Use `Write` exactly once, to the orchestrator-provided `.json` path.
- Construct the complete JSON in that single `Write` call. You have no
  `Bash`, so no `echo`, append, heredoc, or redirect is possible anyway —
  build the object in the `Write` payload directly.
- Your response text contains ONLY the file path. No findings inline, no
  summary prose — the orchestrator reads the artifact, never your reply.
- Per-finding schema:

  ```json
  {
    "file": "<absolute or repo-relative path>",
    "line": <int>,
    "summary": "<one line>",
    "failure_scenario": "<concrete inputs/state -> wrong output/crash; name cross-file relationships here>",
    "confidence": "high|medium|unverified",
    "category": "<specialty tag>"
  }
  ```

- Discard findings with an empty `summary` or no `file`. Maximum 10 findings,
  ranked by severity. Quality over volume — 3 verified cross-file defects beat
  15 single-file nits.

## See also

- `references/subagent-routing.md` — Result Envelope format, phase-boundary
  context resets, targeted-read discipline, and the spike-before-high-output
  rule.
- `references/agent-configs.md` — the 12-agent roster, dispatch protocol, and
  the session-scoped artifact-path scheme.
