---
name: wiki-architecture
description: Wiki skill architecture and schema conventions
---

# Wiki Architecture

## Identity Model

`vault_page_id` = vault-relative path (e.g. `wiki/entities/session-chain.md`). Globally unique within vault namespace.

## State Model

**Ordering**: mtime-based (file modification time). All operations sequenced by wall-clock mtime.

**Dedupe**: Page identity = vault-relative path. LLM is sole writer. Log entries deduplicated by `[YYYY-MM-DD] ingest | {title}` prefix.

**Freshness**: Filesystem mtime is authoritative for wiki page freshness. QMD index freshness = QMD index file mtime. If index mtime < vault mtime → stale, rebuild triggered.

**Auto-linking**: On ingest, after writing the page, QMD is queried with the new page's title+summary to find top-K (K=5) semantically similar existing pages. `[[wikilinks]]` to those pages are injected into a `## Related` section in the new page. This is best-effort — QMD similarity scoring determines candidates.

**Speculative linking**: Links to non-existent pages are kept (Obsidian "red links"). They resolve when the target page is ingested. Never suppress a wikilink because the target doesn't exist yet.

**Typed wikilinks**: `[[Page]]@supports`, `[[Page]]@contradicts`, etc. Relationships also recorded in frontmatter `relations:` field.

**Auto-save**: High-value query syntheses are saved directly to the wiki without asking. Only ask if synthesis is uncertain.

## Operations Contract

| Operation | Input | Output | Side Effects |
|-----------|-------|--------|--------------|
| Ingest | file path, URL, or text | wiki page written with auto-links | log.md appended, wikilinks injected, index.md updated |
| Query | question string | synthesized answer | optionally writes wiki page |
| Lint | none | health report | none (read-only) |
| Index | none | index.md rebuilt | index.md written |
| Update | optional topic, --auto flag | stale candidates ranked by age + search frequency | log.md appended on refresh, wiki page rewritten, qmd index updated |

## Graceful Degradation

When `qmd` CLI is unavailable:
- Search falls back to `glob("wiki/**/*.md")` + `grep` content match
- Ingest still works (filesystem write)
- Lint still works (filesystem read)

## Wiki Search Contract (FTS5 safety)

FTS5 operator escaping for hyphenated/punctuated queries (`two-levers`, `foo*bar`) is **fixed at the root** in our forked `qmd.build_fts5_query`. The owned patch lives at `P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/qmd_fts5_patch.patch` and is applied in-place to the installed qmd package. See #1064.

Consequences:

- **Bare `qmd search` is safe** — no caller-side sanitize needed. All invocation paths (Python `QMDWikiBackend`, `wiki_after_write.py`, the `wiki_search.py` wrapper, ad-hoc CLI, the red-team planner prospect pass) go through the one root fix.
- **`wiki_search.py`** is now a thin wrapper retained only for the Windows subprocess capture+forward quirk — not for FTS5 safety.
- **Reinstall protocol**: `pip install --upgrade qmd` (or a Python reinstall) silently loses the patch. Re-apply from the `.patch` file; verify with `python -c "from qmd.core.retrieval import build_fts5_query as f; assert f('two-levers')=='two levers'"`. qmd is pinned to 0.1.1 — do not auto-upgrade.

## Wiki Search Contract (semantic search)

Two further in-place patches to the installed qmd package ensure semantic (vector) search actually runs. Without these, `qmd search` is BM25-only — embeddings are computed and stored but never queried.

- **Patch 1 — `cli/main.py::cmd_search` constructs and passes `llm_backend`**: owned patch at `P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/qmd_cli_main.patch`. Without it, `search()` in `retrieval.py` guards vector search behind `if llm_backend` and skips it; every search silently degrades to BM25.
- **Patch 2 — `llm/sentence_tf.py::SentenceTransformerBackend` default model = `all-mpnet-base-v2`**: owned patch at `P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/qmd_llm_sentence_tf.patch`. The upstream default (`paraphrase-multilingual-MiniLM-L12-v2`) is weaker than the locally-available `all-mpnet-base-v2`. The wiki DB has been rebuilt with the new model; reverting would silently make every embedding mismatched with the stored vectors.

**Reinstall protocol (semantic search)**: `pip install --upgrade qmd` (or a Python reinstall) silently loses both patches — search silently degrades to BM25-only. Re-apply from the `.patch` files:

```powershell
cd C:\Users\<user>\AppData\Roaming\Python\Python314\site-packages
git apply -p1 P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/qmd_cli_main.patch
git apply -p1 P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/qmd_llm_sentence_tf.patch
```

Verify both are present:
```powershell
python -c "from qmd.cli.main import cmd_search; import inspect; assert 'llm_backend' in inspect.getsource(cmd_search), 'patch 1 missing'"
python -c "from qmd.llm.sentence_tf import SentenceTransformerBackend; import inspect; assert 'all-mpnet-base-v2' in inspect.getsource(SentenceTransformerBackend.__init__), 'patch 2 missing'"
```

If the model default was changed, the DB must be rebuilt: `qmd embed --collection wiki --force`.

**Known limitation**: both patches assume the surrounding code is in the English-translated state that already lives in this operator's site-packages. A fresh `pip install qmd==0.1.1` produces Chinese upstream; apply the translation first or hand-apply the functional changes (the comment + 2 inserted lines for patch 1; the single default-value swap for patch 2). The functional changes are minimal and identifiable by their comments.

**Automation (PR-4, Grok-native SessionStart hook)**: the verification check runs automatically at every Grok session start via `~/.grok/hooks/scripts/qmd_patches_session_start.py` and prints `[qmd-patches] PASS/FAIL/SKIP` on stderr. The hook reads site-packages files directly via `pathlib.Path.read_text()` (does NOT import qmd — avoids the ~3.7s sentence-transformers load); total cost <50ms. See `/design` run 10d616f8 and `P:/.data/wiki/concepts/qmd-patch-durability-strategy.md`.

## Security Notes

- YAML frontmatter uses `yaml.safe_dump` exclusively
- Query length: truncated to 500 chars; non-printables stripped by the base backend
- Path traversal prevention: resolved paths validated against vault root