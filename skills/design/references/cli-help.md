# CLI Help Reference

## Basic Usage

```
/arch <query>
```

## Template Overrides

```
# Use specific template
/arch redesign api template=deep

# Template chaining
/arch build data processor template=python+data-pipeline

# Preset expansion
/arch multi-term
# Expands to: "what's the optimal long term fix in our multi terminal isolation and immune to stale data environment?"
```

## Flags

| Flag | Description |
|------|-------------|
| `--verbose`, `-v` | Full ADR output with all sections |
| `--no-got` | Disable Graph-of-Thought analysis |
| `--no-lean` | Disable Lean System Design principles |
| `--no-clarity-gate` | Skip clarity gate, proceed directly |
| `template=X` | Force specific template |
| `template=X+Y` | Chain templates (primary + context) |

## Configuration

### Project Config: `.archconfig.json` (highest priority)

```json
{
  "default_domain": "python",
  "output_size": "normal",
  "evidence_level": "standard"
}
```

### User Config: `~/.archconfig.json` (medium priority)

```json
{
  "default_domain": "cli",
  "output_size": "small"
}
```

### Environment Variables (lowest priority)

```bash
export ARCH_DEFAULT_DOMAIN=python
export ARCH_OUTPUT_SIZE=normal
export ARCH_EVIDENCE_LEVEL=standard
```

### Priority Chain

Environment variables > Project config > User config

**Note**: Environment variables ALWAYS override when set, regardless of config file content.

## Valid Domains

| Domain | Description |
|--------|-------------|
| `python` | Python 3.12+ development |
| `cli` | CLI/POSIX tool design |
| `data-pipeline` | Data system architecture |
| `precedent` | ADR and decision record analysis |
| `auto` | Auto-detect from query (default) |

## Valid Output Sizes

| Size | Description |
|------|-------------|
| `small` | Concise output, ~5 KB |
| `normal` | Standard output, ~10 KB |
| `large` | Comprehensive output, ~20 KB |

## Valid Evidence Levels

| Level | Description |
|-------|-------------|
| `low` | Minimal evidence requirements |
| `standard` | Normal evidence requirements (default) |
| `high` | Strict evidence requirements |

## Error Recovery Playbook

| Error | Cause | Recovery |
|-------|-------|----------|
| "Invalid default_domain" | Config has unrecognized domain | Use: python, cli, data-pipeline, precedent, or auto |
| "Missing required field: default_domain" | Config file missing required field | Add `"default_domain": "auto"` to config |
| "Template file not found" | Template name misspelled | Use: fast, deep, cli, python, data-pipeline, precedent |
| "Out-of-scope" | Query better suited to another skill | Follow redirect suggestion or confirm "continue with /arch" |
| "Clarity gate: insufficient clarity" | Query too ambiguous | Provide more specific query or answer clarifying question |
| "Contract closure incomplete" | Boundary not fully specified | Review boundary inventory and close missing fields |

## Template Chaining Examples

```
# Primary: python, Context: data-pipeline
/arch design etl pipeline template=python+data-pipeline

# Primary: cli, Context: python
/arch build cli tool template=cli+python

# Primary: precedent, Domain: python (precedent must be primary)
/arch document this adr template=precedent+python
```
