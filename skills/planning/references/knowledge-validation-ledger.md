# Knowledge / Validation Ledger

Use this ledger in design and implementation plans to distinguish source
provenance from the human-facing changelog.

```markdown
## Knowledge / Validation Ledger

| Source or check | Used? | Evidence | Claims supported | Status |
|---|---|---|---|---|
| /wiki | yes/no | path, URL, or transcript reference | claim IDs | verified/unverified/not applicable |
| /find | yes/no | path, URL, or transcript reference | claim IDs | verified/unverified/not applicable |
| /nlm | yes/no | notebook/source reference | claim IDs | verified/unverified/not applicable |
| /check | yes/no | command and output artifact | claim IDs | verified/unverified/not applicable |
| Other | yes/no | ... | claim IDs | ... |
```

Record `no` explicitly when a named source or check was not used. Do not claim
that a source influenced a decision unless the transcript, artifact, command
output, or cited document supports that claim. A pasted LLM response is a
hypothesis source, not authority, until independently verified.

## Change Record

Every implementation-ready plan must link its material decision or validation
record to the project changelog:

```markdown
## Change Record

- Changelog: `CHANGELOG.md`
- Entry ID: `PROV-20260711T184200Z-design`
- Entry status: recorded
```

The changelog entry belongs under `## [Unreleased]`, uses an ISO-8601 UTC
timestamp, and links back to the plan or evidence artifact. The changelog is a
curated human-facing summary; the ledger remains the detailed provenance.

If no external knowledge source or validation check was used, record that fact
in the ledger and write a concise changelog entry only when the decision or
implementation itself is material. Never create a noisy entry for every skill
invocation.
