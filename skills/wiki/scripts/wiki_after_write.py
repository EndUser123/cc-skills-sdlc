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


def build_query(meta: dict, summary_chars: int = 0) -> str:
    """Build a QMD query from title (and optionally truncated summary).

    Title is the most semantically dense signal; concatenated title+summary strings
    cause QMD to return poor results because the long concatenated text dilutes
    the per-token match weight. Default = title only. Pass summary_chars > 0
    for a fallback that appends the first N chars of summary.

    FTS5 operator stripping is handled at the root in our forked
    qmd.build_fts5_query (see __lib/qmd_fts5_patch.patch in cc-skills-utils),
    so no caller-side sanitization is needed here.
    """
    title = meta.get("title", "")
    parts = [title]
    if summary_chars > 0:
        summary = meta.get("summary", "")
        if summary:
            parts.append(summary[:summary_chars])
    return " ".join(p for p in parts if p)[:MAX_QUERY_CHARS]


def query_qmd(query: str, limit: int, qmd_bin: str) -> list[dict]:
    """Run qmd search, return parsed results. Empty list on any failure."""
    if not query:
        return []
    try:
        proc = subprocess.run(
            [qmd_bin, "search", "--collection", "wiki", "--limit", str(limit + 5),
             "--format", "json", query],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    out = proc.stdout.strip()
    idx = out.find("[") if out else -1
    if idx < 0:
        return []
    try:
        return json.loads(out[idx:])
    except json.JSONDecodeError:
        return []


def slug_from_file(file_field: str) -> Optional[str]:
    """`wiki/concepts/foo.md` -> `foo`. Reject non-concept paths."""
    if not file_field:
        return None
    norm = file_field.replace("\\", "/").lower()
    # Explicitly reject vault-level files that aren't concept pages
    basename = norm.rsplit("/", 1)[-1]
    if basename in ("log.md", "schema.md", "index.md"):
        return None
    if "/concepts/" not in norm:
        return None
    if not basename.endswith(".md"):
        return None
    return basename[:-3]


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
    """Run auto-link on a page. Returns a report dict.

    Two-pass query strategy (fixes dense-query bug):
      Pass 1: title only — best semantic density
      Pass 2: title + first 200 chars of summary — fallback if pass 1 returns <2
              non-self concept neighbors
    """
    if not page_path.exists():
        return {"ok": False, "error": f"page not found: {page_path}"}
    text = page_path.read_text(encoding="utf-8")
    meta = read_frontmatter(text)
    self_slug = page_path.stem

    def _filter_concepts(results: list[dict]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for r in results:
            slug = slug_from_file(r.get("file", ""))
            if not slug or slug == self_slug or slug in seen:
                continue
            seen.add(slug)
            out.append(slug)
        return out

    # Pass 1: title only
    # Use a high limit so concept pages aren't crowded out by the 150+ source docs.
    # Source docs outnumber concepts ~6:1, so we need to search deep to find concepts.
    search_limit = max(limit + 5, 40)
    query1 = build_query(meta, summary_chars=0)
    results1 = query_qmd(query1, search_limit, qmd_bin)
    links = _filter_concepts(results1)

    # Pass 2 fallback: title + 200 chars summary, only if pass 1 gave <2 results
    pass2_used = False
    if len(links) < 2:
        query2 = build_query(meta, summary_chars=200)
        if query2 != query1:
            pass2_used = True
            results2 = query_qmd(query2, search_limit, qmd_bin)
            links = _filter_concepts(results2)
            # If pass 2 actually found more, use it; else keep pass 1
            if not links and results1:
                links = _filter_concepts(results1)
                pass2_used = False

    links = links[:limit]
    report = {
        "page": str(page_path),
        "query": query1,
        "query_pass2": (build_query(meta, summary_chars=200) if pass2_used else None),
        "pass2_used": pass2_used,
        "links": links,
        "dry_run": dry_run,
    }
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
