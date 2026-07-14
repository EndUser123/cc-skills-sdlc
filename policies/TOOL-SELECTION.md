# Tool-Selection Policy

> **Authoritative source for choosing tools by operation, lifecycle, and verification needs — not merely by the host operating system.**

This policy governs how agents select tools when the choice is consequential. It
does not override platform safety constraints, package-local AGENTS.md rules,
or explicit current-task user direction.

For a concise invariant, see `P:\.claude\CLAUDE.md` section *Tool Selection*.

---

## Decision Hierarchy

When tool choice is consequential, use this order of priority:

1. **Existing repository utilities** — tested, authoritative, reachable from the
   current workflow. Verify existence, authority, contract, and test coverage
   before creating a substitute or reproducing logic in a shell command.
2. **Native agent tools** — Grep (repository text search), Glob (file discovery),
   Read (file reading), where they provide equivalent evidence with less shell
   quoting, fewer permission prompts, clearer tool intent, easier path scoping,
   and less accidental command composition.
3. **Structured maintained logic** — Python (or another language already
   authoritative in the subsystem) for logic that is structured, reusable,
   deterministic, testable, cross-platform, stateful, or complex enough that
   shell quoting or pipelines obscure behavior. Select Python by fit, not by
   default. Prefer the language already owning the subsystem to minimize
   duplication and authority ambiguity.
4. **Windows-native operations** — PowerShell for genuinely Windows-specific
   responsibilities such as services, registry, ACLs, environment scopes,
   scheduled tasks, process/job control, PowerShell module integration, thin
   Windows launchers, and verification of PowerShell permission behavior.
   Do not use PowerShell merely because the host is Windows.
5. **Shell pipelines** — for small, disposable, easily reviewed operations.
   Before composing a multi-stage pipeline, check whether native search options
   can perform the filtering directly, or an existing repository utility exists.

---

## Decision Questions

When tool choice is consequential — adding a maintained helper, changing a
wrapper, introducing a runtime dependency, creating operational automation,
implementing a reusable parser/classifier/resolver/audit/migration, choosing
between platform-specific and cross-platform implementations, or changing a
canonical execution path — record:

| Question | Purpose |
|---|---|
| Operation | What is being done? |
| One-time or maintained | Will this be reused? |
| Existing utility checked | Did you search before creating? |
| Structured or unstructured input | Does the input need parsing? |
| Platform-specific or portable | Does it need to work everywhere? |
| Expected callers | Who will invoke this? |
| Source of authority | Which package owns this? |
| Output or artifact | What does it produce? |
| Failure behavior | What happens on error? |
| Verification path | How is it tested? |
| Selected tool | What you chose |
| Alternatives rejected | What was considered and why |

Do not require this record for trivial reads or one-line disposable commands.

---

## New-Helper Requirements

Before adding a maintained `.py`, `.ps1`, `.sh`, `.js`, executable wrapper, or
equivalent helper, verify:

- **Owner** — who owns, maintains, and answers questions about this helper.
- **Reason it belongs in this package** — why not an existing package or utility.
- **Existing alternatives searched** — what was found and why it was insufficient.
- **Callers** — who invokes this, and from what entry points.
- **Inputs** — exact arguments, stdin, environment, or state it reads.
- **Outputs** — exact stdout, stderr, exit codes, or artifacts it produces.
- **Authority** — which configuration, file, or database it is authoritative for.
- **State or artifacts** — what files or state it creates or modifies.
- **Failure direction** — what happens on missing input, bad input, runtime error.
- **Tests** — focused test path and expected coverage.
- **Removal or migration condition** — if temporary, when and how to remove.

A hard failure should occur for:

- new maintained helper has no owner;
- generated cache is being edited as source;
- existing authoritative utility was not inspected;
- duplicate live implementations are introduced;
- a runtime path has no verification method.

Do not hard-block merely because a reviewer would have chosen a different
language.

---

## Tool Categories

### Native Agent Tools

Prefer native search, glob, and read tools for ordinary repository discovery
when they provide equivalent evidence.

| Tool | When | Avoid |
|---|---|---|
| Grep | Repository text search, pattern matching | Long PowerShell `Select-String` pipelines for what Grep does in one call |
| Glob | File discovery by pattern | cd + ls + filter chains |
| Read | Reading known files | cat, Get-Content, or type when no shell processing is needed |

*Reasons:* less shell quoting, fewer permission prompts, clearer tool intent,
easier path scoping, less accidental command composition.

Do not require native tools when a repository script or direct command provides
materially better evidence (e.g., a script that cross-references multiple
sources, or a command whose structured output is the result).

### Existing Repository Utilities

A tested, authoritative repository utility normally takes precedence over
creating another helper or reproducing its logic in a shell command. Verify:

- the utility exists;
- it is the authoritative source;
- it is reachable from the current workflow;
- its contract matches the requested operation;
- its tests are relevant.

### Structured Maintained Logic (Python or other language)

Prefer Python — or another language already authoritative in the subsystem —
for logic that is structured, reusable, deterministic, testable, cross-platform,
stateful, or complex enough that shell quoting or pipelines obscure behavior.

Do not select Python automatically. Use the language already owning the
subsystem when that produces less duplication and a clearer authority path.

Examples of good Python use:

- Worktree-root resolvers
- JSON schema validation
- Multi-file audits
- Reusable classifiers
- State-machine orchestration

### PowerShell

Prefer PowerShell for genuinely Windows-native responsibilities:

- Windows services
- Registry operations
- ACLs and permissions
- Windows environment scopes
- Scheduled tasks
- Process and job control
- PowerShell module integration
- Thin Windows launchers
- Verification of PowerShell permission behavior

Do not use PowerShell merely because the host is Windows.

### Shell Pipelines

Use shell pipelines for small, disposable, easily reviewed operations.

Before composing a multi-stage pipeline, check whether:

- native search options can perform the filtering directly;
- an existing repository utility exists;
- the logic is becoming maintained policy;
- structured parsing would be safer;
- the pipeline creates unnecessary permission or portability friction.

---

## Tool Mapping for Claude Code

| Task | Recommended tool |
|---|---|
| Repository text search | Grep |
| File discovery by pattern | Glob |
| Reading known files | Read |
| Windows-native operations | PowerShell |
| Structured maintained logic | Python |

Prefer these native tools before falling back to shell approximations. The
Claude Code tool belt provides Grep, Glob, Read, Bash, Edit, Write, and Skill.

For delegated `/go` workers or subagents, the calling prompt should include
tool-selection guidance consistent with this policy. The delegated agent is
bound by its own runtime's available tools and the caller's instructions.

---

## Recurring Failure Patterns

These patterns must be prevented:

- Using long PowerShell pipelines for repository searches that native Grep/Glob
  could perform.
- Using PowerShell for structured reusable logic better suited to Python.
- Using Python merely to invoke a Windows-native operation.
- Introducing new helper scripts without checking for an existing utility.
- Creating duplicate implementations in `.py`, `.ps1`, `.sh`, or another language.
- Embedding maintained policy in ad hoc shell commands.
- Adding a maintained helper for a one-time operation.
- Assuming Windows 11 means PowerShell should be the default for all work.

---

## Exception Behavior

This policy is advisory, not hard-enforced. A justified exception may override
any default when the agent documents:

- why the exception applies;
- what alternative was considered;
- what evidence supports the exception.

Exception documentation should be brief but specific — one to three sentences.

---

## Verification

A focused test suite verifies the decision model, not specific language
preferences. See `skills/go/tests/test_tool_selection_policy.py` for the
regression corpus.
