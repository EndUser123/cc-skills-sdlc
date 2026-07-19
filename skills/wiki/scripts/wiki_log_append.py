"""wiki_log_append.py — Atomic log prepend for the wiki skill.

Replaces fragile ad-hoc PowerShell `Set-Content` heredocs that previously
prepended entries to `P:/.data/wiki/log.md`. Handles the `# Vault Log`
sentinel, SCHEMA.md §6 format construction, and atomic write via `.tmp`
+ `os.replace` (prevents partial writes visible to other terminals).

CLI:
    python wiki_log_append.py --page <page.md> --notes "<1-line>" [--type ingest|update] [--log PATH]

Exit codes: 0 on success (including idempotent re-runs that find the entry
already present), non-zero on hard error (page not found, log missing,
sentinel missing, post-write validation failed).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

LOG_PATH = Path("P:/.data/wiki/log.md")
SENTINEL = "# Vault Log"


def read_title_slug(page: Path) -> tuple[str, str]:
    """Extract (title, slug) from page frontmatter. Falls back to stem if absent."""
    text = page.read_text(encoding="utf-8")
    m = re.search(r'^title:\s*"?([^"\n]+)"?', text, re.MULTILINE)
    title = m.group(1).strip() if m else page.stem
    return title, page.stem


def build_entry(title: str, slug: str, notes: str, entry_type: str) -> str:
    today = date.today().isoformat()
    notes_line = f"Notes: {notes}\n" if notes else ""
    return (
        f"## [{today}] {entry_type} | {title}\n"
        f"Source: session-{today}\n"
        f"Agent: grok\n"
        f"{notes_line}"
        f"Page: wiki/concepts/{slug}.md\n"
        f"\n"
    )


def _entry_already_present(log_path: Path, slug: str, entry_type: str) -> bool:
    """Return True if a recent entry already references this page+type. Idempotency check.

    Tracks the most recent entry type as we scan; when the page marker is found,
    verifies the owning entry's type matches. Only scans the first 200 lines
    (recent entries) — historical entries won't collide.
    """
    page_marker = f"Page: wiki/concepts/{slug}.md"
    text = log_path.read_text(encoding="utf-8")
    head_lines = text.splitlines()[:200]
    most_recent_entry_type: str | None = None
    entry_header_re = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\]\s+(\w+)\s*\|")
    for ln in head_lines:
        m = entry_header_re.match(ln)
        if m:
            most_recent_entry_type = m.group(1).lower()
            continue
        if ln.strip() == page_marker:
            return most_recent_entry_type == entry_type.lower()
    return False


def atomic_prepend(log_path: Path, entry: str, slug: str, entry_type: str) -> dict:
    """Prepend `entry` after the `# Vault Log` sentinel. Atomic via tmp + replace."""
    if not log_path.exists():
        return {"ok": False, "error": f"log not found: {log_path}"}
    if _entry_already_present(log_path, slug, entry_type):
        return {"ok": True, "skipped": "entry already present (idempotent no-op)"}
    text = log_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    sentinel_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == SENTINEL), None
    )
    if sentinel_idx is None:
        return {"ok": False, "error": f"missing {SENTINEL!r} sentinel"}
    insert_at = sentinel_idx + 1
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    new_text = "".join(lines[:insert_at] + [entry] + lines[insert_at:])
    tmp = log_path.with_suffix(log_path.suffix + ".tmp")
    try:
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(log_path)
    except OSError as e:
        return {"ok": False, "error": f"atomic write failed: {e}"}
    if not log_path.read_text(encoding="utf-8").startswith(SENTINEL):
        return {"ok": False, "error": "post-write validation: sentinel not at head"}
    first_new_line = entry.splitlines()[0]
    return {"ok": True, "entry_added": first_new_line}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="wiki_log_append.py",
        description="Atomic log prepend for wiki pages.",
    )
    p.add_argument("--page", required=True, help="absolute path to wiki page just written")
    p.add_argument("--notes", default="", help="1-line notes (optional)")
    p.add_argument("--type", default="ingest", choices=["ingest", "update"],
                   help="entry type (default: ingest)")
    p.add_argument("--log", default=str(LOG_PATH), help=f"path to log.md (default: {LOG_PATH})")
    args = p.parse_args(argv)

    page = Path(args.page)
    if not page.exists():
        print(f"ok=False error=page not found: {page}", file=sys.stderr)
        return 1
    title, slug = read_title_slug(page)
    entry = build_entry(title, slug, args.notes, args.type)
    report = atomic_prepend(Path(args.log), entry, slug, args.type)
    print(json_dumps(report))
    return 0 if report.get("ok") else 1


def json_dumps(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=True)


if __name__ == "__main__":
    sys.exit(main())