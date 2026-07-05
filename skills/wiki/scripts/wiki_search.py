"""
wiki_search.py — FTS5-safe wrapper around `qmd search` for the wiki collection.

Why this exists: qmd-py v0.1.1's `build_fts5_query` does `query.strip()` with no
escaping, so raw queries containing FTS5 operator punctuation (`-`, `*`, `()`,
`"`, `:`) either parse wrong (`two-levers` → `two NOT levers` → zero hits) or
raise a syntax error. The Python callers (QMDWikiBackend, wiki_after_write.py)
sanitize inline; this wrapper gives non-Python callers (manual CLI use, the
red-team planner prospect pass, ad-hoc scripts) the same safety.

Contract: internal callers MUST use this wrapper instead of bare `qmd search`
until the upstream qmd-py fix ships. See skills/wiki/CLAUDE.md.

Usage:
    python wiki_search.py <query> [--limit N] [--qmd qmd] [extra qmd search args...]

Sanitizes <query> (strips FTS5 operator punctuation, preserves Unicode word
chars), then delegates to `qmd search --collection wiki`. qmd's stdout/stderr
stream through unchanged. Exit code is qmd's exit code.

Once a pinned qmd-py release contains the upstream fix, the sanitize step here
becomes an idempotent no-op; this wrapper can then be deleted and callers can
return to bare `qmd search`.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


def sanitize_query(query: str) -> str:
    """Strip FTS5 operator punctuation, preserve Unicode word chars."""
    cleaned = re.sub(r"[^\w\s]", " ", query)
    return re.sub(r"\s+", " ", cleaned).strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wiki_search.py",
        description="FTS5-safe qmd search wrapper for the wiki collection.",
    )
    p.add_argument("query", help="search query (will be FTS5-sanitized)")
    p.add_argument("--limit", type=int, default=10, help="max results (default 10)")
    p.add_argument("--qmd", default="qmd", help="qmd binary (default: qmd on PATH)")
    args, extra = p.parse_known_args(argv)

    sanitized = sanitize_query(args.query)
    if not sanitized:
        print("wiki_search: empty query after sanitization", file=sys.stderr)
        return 2

    cmd = [args.qmd, "search", "--collection", "wiki",
           "--limit", str(args.limit), "--format", "json", sanitized, *extra]
    # capture+forward: on Windows, a bare subprocess.run(cmd) does not reliably
    # inherit the parent's redirected stdout handle to the grandchild, so qmd's
    # output vanishes when this wrapper is piped/redirected. Capture explicitly
    # and re-emit so callers see qmd's bytes regardless of platform.
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
