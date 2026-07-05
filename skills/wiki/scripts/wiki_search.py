"""
wiki_search.py — thin CLI wrapper around `qmd search` for the wiki collection.

FTS5 operator escaping (#1064) is handled at the root in our forked
qmd.build_fts5_query — see
cc-skills-utils/__lib/qmd_fts5_patch.patch for the owned source of truth.
No caller-side sanitization is needed; raw queries are safe to pass through.

This wrapper exists for the Windows subprocess capture+forward quirk (below),
not for FTS5 safety.

Usage:
    python wiki_search.py <query> [--limit N] [--qmd qmd] [extra qmd search args...]

Passes <query> unmodified to `qmd search --collection wiki`. qmd's
stdout/stderr stream through unchanged. Exit code is qmd's exit code.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wiki_search.py",
        description="Thin qmd search wrapper for the wiki collection.",
    )
    p.add_argument("query", help="search query (passed raw to qmd)")
    p.add_argument("--limit", type=int, default=10, help="max results (default 10)")
    p.add_argument("--qmd", default="qmd", help="qmd binary (default: qmd on PATH)")
    args, extra = p.parse_known_args(argv)

    if not args.query.strip():
        print("wiki_search: empty query", file=sys.stderr)
        return 2

    cmd = [args.qmd, "search", "--collection", "wiki",
           "--limit", str(args.limit), "--format", "json", args.query, *extra]
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
