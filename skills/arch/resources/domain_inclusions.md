# Domain Inclusions Reference

This document consolidates shared domain-specific inclusion logic used across all architecture templates. When a domain is detected (via default config or keyword matching), templates should augment their analysis with the considerations listed below.

## Domain Detection

Domains are detected via:
1. **Project config**: `.archconfig.json` with `default_domain` set
2. **User config**: `~/.archconfig.json` with `default_domain` set
3. **Environment**: `ARCH_DEFAULT_DOMAIN` environment variable
4. **Keywords**: Automatic detection from query content

## Domain-Specific Considerations

### Python (`python`)

**Keywords**: `python`, `asyncio`, `type hint`, `pydantic`, `fastapi`, `flask`, `django`, `async`, `await`, `decorator`, `context manager`

**Include in analysis**:
- **Async vs Sync**: Is this I/O-bound (asyncio) or CPU-bound (multiprocessing)?
- **Type System Design**: Protocol-based interfaces, generics, TypeVar usage, precision level needed
- **Framework Architecture**: FastAPI/Flask/Django patterns at scale
- **GIL Strategy**: Threading vs multiprocessing vs async decision matrix
- **Dependency Management**: uv, pyproject.toml, dependency constraints

**For fast.md**: Inject Python-specific considerations into the decision path
**For deep.md**: Augment comprehensive analysis with the above areas

---

### CLI/POSIX (`cli`)

**Keywords**: `cli`, `command line`, `terminal`, `shell`, `posix`, `exit code`, `argument parsing`

**Include in analysis**:
- **POSIX Compliance**: Signal handling, exit codes, file descriptors
- **Terminal Interaction**: TTY detection, progress bars, interactive prompts
- **Argument Parsing**: Subcommands, flags, positional arguments, help generation
- **Error Handling**: Exit code conventions, stderr usage, error messages
- **Shell Completion**: Bash/zsh completion script generation

**For cli.md template**: Use CLI-specific template
**For fast.md/deep.md**: Inject these considerations when CLI domain is active

---

### Data Pipeline (`data-pipeline`)

**Keywords**: `etl`, `elt`, `pipeline`, `streaming`, `batch`, `kafka`, `spark`, `airflow`, `dagster`, `prefect`, `warehouse`, `data lake`

**Include in analysis**:
- **Processing Model**: Streaming vs batch vs hybrid
- **Data Quality**: Validation, schema enforcement, deduplication
- **Schema Evolution**: Backward compatibility, migration strategies
- **Throughput vs Latency**: Trade-offs, scaling strategies
- **Error Handling**: Dead letter queues, retry policies, exactly-once semantics

**For data-pipeline.md template**: Use data-pipeline specific template
**For fast.md/deep.md**: Inject these considerations when data-pipeline domain is active

---

### Precedent/ADR (`precedent`)

**Keywords**: `adr`, `decision record`, `precedent`, `document decision`, `architecture decision record`

**Include in analysis**:
- **ADR Format**: Status, context, decision, rationale, consequences
- **Decision Documentation**: Capturing alternatives, trade-offs, related decisions
- **Precedent Tracking**: Links to related ADRs, versioning, searchability

**For precedent.md template**: Use precedent-specific template
**For fast.md/deep.md**: Note that ADR documentation may be valuable for precedent-setting changes

---

## Integration Instructions

### For Template Authors

When implementing domain-specific logic in templates:

1. **Do NOT switch templates** when domain is detected - instead, augment the current template's decision path
2. **Use this reference** to identify which considerations apply to the detected domain
3. **Inject domain-specific questions** at appropriate decision points
4. **Reference domain-specific patterns** when recommending solutions

### Example: Domain Auto-Inclusion in fast.md

```
## Stage 0.6: Domain Resource Inclusion

### Detect Default Domain
- Environment variable: `ARCH_DEFAULT_DOMAIN`
- Conversation context: `conversation_context.get("default_domain")`

### Domain-Specific Resource Inclusion

If domain is detected, include considerations from `domain_inclusions.md`:

| Domain | Key Considerations |
|--------|-------------------|
| python | Async vs sync, type system, GIL strategy, framework patterns |
| cli | POSIX compliance, signal handling, terminal interaction |
| data-pipeline | Streaming vs batch, data quality, schema evolution |
| precedent | ADR format, decision documentation, precedent tracking |
```

---

## Version History

- v1.0 (2025): Initial consolidation from fast.md/deep.md domain inclusion sections
