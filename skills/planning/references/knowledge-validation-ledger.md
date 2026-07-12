# Knowledge / Validation

Use this compact section in material designs and implementation-ready plans:

```markdown
## Knowledge / Validation

- Sources/checks used: `/wiki`, `/check`, or `none`
- Sources/checks not used: `/find`, `/nlm`, or `none`
- Evidence: `path/to/output`, URL, test command, or `none`
- Claims affected: [claim IDs or concise descriptions]
- Unverified claims: [claims or `none`]

## Change Record

- Changelog: `CHANGELOG.md`
- Entry ID: `PROV-20260712T184200Z-design`
- Entry status: `recorded`
```

Invocation does not prove that a source influenced a decision or that a check
validated a claim. Record `internal/unverified` when a material decision relies
on internal model knowledge rather than a named source or executed check.

Create `CHANGELOG.md` lazily when a material decision or implementation needs
recording. Put the concise entry under `## [Unreleased]`; do not create an
entry for every skill invocation. The changelog is a human-facing summary, not
an audit log.
