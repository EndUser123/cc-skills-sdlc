"""
wiki_after_write.py — Shared post-write auto-link step for the wiki skill.

Both wiki write paths (Ingest per-file subagent, Query-section auto-save) call
this after a page lands on disk. Reads the page's title+summary frontmatter,
queries QMD for the top-K semantically similar existing concept pages, and
idempotently injects (or regenerates) a `## Auto-related` section of
`[[wikilinks]]`. Hand-authored `## Related` sections are never touched.

Marker convention (idempotency):
  - A `## Auto-related` section is auto-managed; re-running rewrites it.
  - A `## Related` section (no marker) is hand-authored; left alone.
This separation lets both coexist on the same page.

CLI:
    python wiki_after_write.py <page-path> [--limit 5] [--dry-run] [--qmd qmd]

Exit codes: 0 on success (including no-links-found no-op), non-zero on error.
Best-effort: qmd unavailable or returns nothing is a clean no-op, not a failure.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

VAULT_ROOT = Path("P:/.data/wiki")
CONCEPTS_DIR = VAULT_ROOT / "concepts"
AUTO_SECTION_HEADER = "## Auto-related"
MAX_QUERY_CHARS = 400


def read_frontmatter(text: str) -> dict:
    """Extract title and summary from YAML frontmatter (defensive, no PyYAML)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = text[3:end]
    out: dict = {}

    m = re.search(r"^title:\s*(.+?)\s*$", fm, re.MULTILINE)
    if m:
        title = m.group(1).strip().strip('"').strip("'")
        out["title"] = title

    # summary may be inline (`summary: foo`) or block (`summary: >\n  foo`).
    # Block form checked first — otherwise the inline regex backtracks and
    # captures the bare `>` indicator.
    m_block = re.search(r"^summary:\s*[>|]\s*\n((?:[ \t]+.+\n?)+)", fm, re.MULTILINE)
    if m_block:
        lines = [ln.strip() for ln in m_block.group(1).splitlines()]
        out["summary"] = " ".join(lines).strip()
    else:
        m_inline = re.search(r"^summary:\s+(.+?)\s*$", fm, re.MULTILINE)
        if m_inline:
            out["summary"] = m_inline.group(1).strip().strip('"').strip("'")
    return out


def build_query(meta: dict) -> str:
    """Build a QMD-safe query from title+summary.

    QMD's FTS5 tokenizer treats `/`, `-`, backticks, parens, etc. as token
    separators or query syntax, so raw frontmatter values return zero hits
    (see #1064 QMD hyphenation bug). Strip FTS5 operator punctuation but keep
    Unicode word characters — `[^\w\s]` is Unicode-aware by default, so Latin,
    CJK, Cyrillic, etc. letters survive while hyphens/dots/parens are dropped.
    """
    parts = [meta.get("title", ""), meta.get("summary", "")]
    raw = " ".join(p for p in parts if p)
    # keep Unicode word chars + spaces; drop FTS5 operator punctuation/markup
    cleaned = re.sub(r"[^\w\s]", " ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_QUERY_CHARS]


def query_qmd(query: str, limit: int, qmd_bin: str) -> list[dict]:
    """Run qmd search, return parsed results. Empty list on any failure."""
    if not query:
        return []
    try:
        proc = subprocess.run(
            [qmd_bin, "search", "--collection", "wiki", "--limit", str(limit + 5),
             "--format", "json", query],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    out = proc.stdout.strip()
    if not out or not out.startswith("["):
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def slug_from_file(file_field: str) -> Optional[str]:
    """`wiki/concepts/foo.md` -> `foo`. Reject non-concept paths."""
    if not file_field:
        return None
    norm = file_field.replace("\\", "/")
    if "/concepts/" not in norm:
        return None
    name = norm.rsplit("/", 1)[-1]
    if not name.endswith(".md"):
        return None
    return name[:-3]


def find_section_bounds(text: str, header: str) -> Optional[tuple[int, int]]:
    """Return (start_of_header_line, end_of_section_exclusive) or None."""
    lines = text.splitlines(keepends=True)
    header_pat = re.compile(r"^" + re.escape(header) + r"\s*$")
    start = None
    for i, ln in enumerate(lines):
        if header_pat.match(ln.rstrip()):
            start = i
            break
    if start is None:
        return None
    # section ends at next `## ` header at the same or shallower indent, or EOF
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^#{1,2} \S", lines[j]):
            end = j
            break
    return start, end


def render_section(links: list[str]) -> str:
    body = "\n".join(f"- [[{slug}]]" for slug in links)
    return f"{AUTO_SECTION_HEADER}\n\n{body}\n\n"


def inject_section(text: str, links: list[str]) -> str:
    """Replace existing auto section, or append new one. Preserves trailing newline."""
    section = render_section(links)
    bounds = find_section_bounds(text, AUTO_SECTION_HEADER)
    if bounds is not None:
        start, end = bounds
        lines = text.splitlines(keepends=True)
        rebuilt = "".join(lines[:start]) + section + "".join(lines[end:])
        return rebuilt
    # append: ensure exactly one blank line before the new section
    stripped = text.rstrip() + "\n\n"
    return stripped + section


def after_write(page_path: Path, limit: int, qmd_bin: str, dry_run: bool) -> dict:
    """Run auto-link on a page. Returns a report dict."""
    if not page_path.exists():
        return {"ok": False, "error": f"page not found: {page_path}"}
    text = page_path.read_text(encoding="utf-8")
    meta = read_frontmatter(text)

    # Respect hand-authored ## Related: never pollute it. Auto goes in its own section.
    query = build_query(meta)
    results = query_qmd(query, limit, qmd_bin)

    self_slug = page_path.stem
    seen: set[str] = set()
    links: list[str] = []
    for r in results:
        slug = slug_from_file(r.get("file", ""))
        if not slug or slug == self_slug or slug in seen:
            continue
        seen.add(slug)
        links.append(slug)
        if len(links) >= limit:
            break

    report = {"page": str(page_path), "query": query, "links": links, "dry_run": dry_run}
    if not links:
        report["ok"] = True
        report["note"] = "no qualifying concept neighbors found (QMD empty or all non-concept)"
        return report

    if dry_run:
        report["ok"] = True
        return report

    new_text = inject_section(text, links)
    page_path.write_text(new_text, encoding="utf-8")
    report["ok"] = True
    report["wrote"] = True
    return report


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="wiki_after_write.py",
                                description="Shared post-write auto-link for wiki pages.")
    p.add_argument("page", help="absolute path to the wiki page just written")
    p.add_argument("--limit", type=int, default=5, help="max links to inject (default 5)")
    p.add_argument("--dry-run", action="store_true", help="print candidates, do not write")
    p.add_argument("--qmd", default="qmd", help="qmd binary (default: qmd on PATH)")
    args = p.parse_args(argv)

    report = after_write(Path(args.page), args.limit, args.qmd, args.dry_run)
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
