# TLDR-Code Daemon & Semantic Search Reference

## Daemon (Faster Queries)

The daemon holds indexes in memory for instant repeated queries.

### Daemon Commands

```bash
# Start daemon (backgrounds automatically)
tldr daemon start
tldr daemon start --project /path/to/project

# Check status
tldr daemon status

# Stop daemon
tldr daemon stop

# Send raw command
tldr daemon query ping
tldr daemon query status

# Notify file change (for hooks)
tldr daemon notify <file>
tldr daemon notify src/api.py
```

### Daemon Features

| Feature | Description |
|---------|-------------|
| Auto-shutdown | 30 minutes idle |
| Query caching | SalsaDB memoization |
| Content hashing | Skip unchanged files |
| Dirty tracking | Incremental re-indexing |
| Cross-platform | Unix sockets / Windows TCP |

### Daemon Socket Protocol

Send JSON to socket, receive JSON response:

```json
// Request
{"cmd": "search", "pattern": "process", "max_results": 10}

// Response
{"status": "ok", "results": [...]}
```

**All 22 daemon commands:**
```
ping, status, shutdown, search, extract, impact, dead, arch,
cfg, dfg, slice, calls, warm, semantic, tree, structure,
context, imports, importers, notify, diagnostics, change_impact
```

---

## Semantic Search (P6)

Natural language code search using embeddings.

### Setup

```bash
# Build index (downloads model on first run)
tldr semantic index .

# Default model: bge-large-en-v1.5 (1.3GB, best quality)
# Smaller model: all-MiniLM-L6-v2 (80MB, faster)
tldr semantic index . --model all-MiniLM-L6-v2
```

### Search

```bash
tldr semantic search "authentication flow"
tldr semantic search "error handling patterns" --k 10
tldr semantic search "database connection" --expand  # Follow call graph
```

### Configuration

In `.claude/settings.json`:
```json
{
  "semantic_search": {
    "enabled": true,
    "auto_reindex_threshold": 20,
    "model": "bge-large-en-v1.5"
  }
}
```
