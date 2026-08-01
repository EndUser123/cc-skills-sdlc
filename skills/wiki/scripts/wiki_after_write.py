"""
wiki_after_write.py — Shared post-write auto-link step for the wiki skill.

Both wiki write paths (Ingest per-file subagent, Query-section auto-save) call
this after a page lands on disk. Reads the page's title+summary frontmatter,
uses keyword-based grep to find related existing concept pages, and
idempotently injects (or regenerates) a `## Auto-related` section of
`[[wikilinks]]`. Hand-authored `## Related` sections are never touched.

Marker convention (idempotency):
  - A `## Auto-related` section is auto-managed; re-running rewrites it.
  - A `## Related` section (no marker) is hand-authored; left alone.
This separation lets both coexist on the same page.

CLI:
    python wiki_after_write.py <page-path> [--limit 5] [--dry-run]

Exit codes: 0 on success (including no-links-found no-op), non-zero on error.
Best-effort: grep finds no neighbors is a clean no-op, not a failure.

History: this script previously used QMD (vector/semantic search) for neighbor
discovery. QMD was removed from this host (replaced by the built-in grep tool).
The neighbor discovery now uses keyword extraction + grep.
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

    m_block = re.search(r"^summary:\s*[>|]\s*\n((?:[ \t]+.+\n?)+)", fm, re.MULTILINE)
    if m_block:
        lines = [ln.strip() for ln in m_block.group(1).splitlines()]
        out["summary"] = " ".join(lines).strip()
    else:
        m_inline = re.search(r"^summary:\s+(.+?)\s*$", fm, re.MULTILINE)
        if m_inline:
            out["summary"] = m_inline.group(1).strip().strip('"').strip("'")
    return out


def extract_keywords(meta: dict) -> list[str]:
    """Extract search keywords from title and summary.

    Splits title+summary into significant words (>=4 chars, not stopwords).
    Returns 3-6 keywords most likely to find related concepts via grep.
    """
    title = meta.get("title", "").lower()
    summary = meta.get("summary", "").lower()
    combined = f"{title} {summary[:200]}"
    words = re.findall(r"[a-z]{4,}", combined)

    stopwords = {
        "that", "this", "with", "from", "have", "they", "will", "been",
        "were", "what", "when", "which", "their", "would", "could", "should",
        "there", "these", "those", "about", "into", "over", "than", "then",
        "them", "only", "also", "more", "some", "such", "very", "just",
        "each", "both", "does", "done", "make", "makes", "made", "work",
        "here", "session", "first", "agent", "model", "skill",
    }
    keywords = [w for w in words if w not in stopwords and len(w) >= 4]

    seen: set[str] = set()
    unique: list[str] = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
        if len(unique) >= 6:
            break
    return unique


def query_grep(keywords: list[str], limit: int, self_slug: str) -> list[str]:
    """Use ripgrep to find concept files matching keywords.

    Runs rg with an OR pattern against concepts directory.
    Returns ranked list of slugs (excluding self), sorted by match count.
    """
    if not keywords:
        return []

    pattern = "|".join(re.escape(k) for k in keywords)
    try:
        proc = subprocess.run(
            ["rg", "-l", "-i", "--count-matches", pattern, str(CONCEPTS_DIR)],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _python_fallback_search(keywords, limit, self_slug)

    if proc.returncode not in (0, 1):
        return []

    matches: dict[str, int] = {}
    for line in proc.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.rsplit(":", 1)
        if len(parts) == 2:
            filepath, count_str = parts
            try:
                count = int(count_str)
            except ValueError:
                filepath = line
                count = 1
        else:
            filepath = line
            count = 1

        slug = Path(filepath).stem
        if slug == self_slug:
            continue
        if "/concepts/" not in filepath.replace("\\", "/"):
            continue
        matches[slug] = matches.get(slug, 0) + count

    ranked = sorted(matches.items(), key=lambda x: -x[1])[:limit]
    return [slug for slug, _ in ranked]


def _python_fallback_search(keywords: list[str], limit: int, self_slug: str) -> list[str]:
    """Pure-Python fallback when rg is not available."""
    if not CONCEPTS_DIR.exists():
        return []

    pattern = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    matches: dict[str, int] = {}

    for concept_file in CONCEPTS_DIR.glob("*.md"):
        slug = concept_file.stem
        if slug == self_slug:
            continue
        try:
            text = concept_file.read_text(encoding="utf-8", errors="replace")
            count = len(pattern.findall(text))
            if count > 0:
                matches[slug] = count
        except Exception:
            continue

    ranked = sorted(matches.items(), key=lambda x: -x[1])[:limit]
    return [slug for slug, _ in ranked]


def slug_from_file(file_field: str) -> Optional[str]:
    """wiki/concepts/foo.md -> foo. Reject non-concept paths."""
    if not file_field:
        return None
    norm = file_field.replace("\\", "/").lower()
    basename = norm.rsplit("/", 1)[-1]
    if basename in ("log.md", "schema.md", "index.md"):
        return None
    if "/concepts/" not in norm:
        return None
    if not basename.endswith(".md"):
        return None
    return basename[:-3]


def find_section_bounds(text: str, header: str) -> Optional[tuple[int, int]]:
    lines = text.splitlines(keepends=True)
    header_pat = re.compile(r"^" + re.escape(header) + r"\s*$")
    start = None
    for i, ln in enumerate(lines):
        if header_pat.match(ln.rstrip()):
            start = i
            break
    if start is None:
        return None
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
    section = render_section(links)
    bounds = find_section_bounds(text, AUTO_SECTION_HEADER)
    if bounds is not None:
        start, end = bounds
        lines = text.splitlines(keepends=True)
        rebuilt = "".join(lines[:start]) + section + "".join(lines[end:])
        return rebuilt
    stripped = text.rstrip() + "\n\n"
    return stripped + section


def after_write(page_path: Path, limit: int, dry_run: bool) -> dict:
    """Run auto-link on a page. Returns a report dict."""
    if not page_path.exists():
        return {"ok": False, "error": f"page not found: {page_path}"}
    text = page_path.read_text(encoding="utf-8")
    meta = read_frontmatter(text)
    self_slug = page_path.stem

    keywords = extract_keywords(meta)
    query_str = " ".join(keywords)
    links = query_grep(keywords, limit, self_slug)
    links = links[:limit]

    report = {
        "page": str(page_path),
        "query": query_str,
        "keywords": keywords,
        "links": links,
        "dry_run": dry_run,
    }
    if not links:
        report["ok"] = True
        report["note"] = "no qualifying concept neighbors found (grep returned no matches)"
        return report

    if dry_run:
        report["ok"] = True
        return report

    new_text = inject_section(text, links)
    page_path.write_text(new_text, encoding="utf-8")
    report["ok"] = True
    report["wrote"] = True
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wiki_after_write.py",
                                description="Shared post-write auto-link for wiki pages.")
    p.add_argument("page", help="absolute path to the wiki page just written")
    p.add_argument("--limit", type=int, default=5, help="max links to inject (default 5)")
    p.add_argument("--dry-run", action="store_true", help="print candidates, do not write")
    args = p.parse_args(argv)

    report = after_write(Path(args.page), args.limit, args.dry_run)
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
