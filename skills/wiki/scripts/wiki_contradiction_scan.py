"""
wiki_contradiction_scan.py — Tag-overlap + simple negation contradiction scan.

Sister script to wiki_after_write.py. Runs alongside it during Ingest step 6
(SCHEMA.md §10). Finds concept pages that overlap on tags / semantic similarity
with the freshly-written page and looks for plain negation-keyword disagreement
between their `## Summary` / `## Key Findings` claims. If a contradiction is
detected, injects a typed `[[slug]]@contradicts` line into the existing
`## Auto-related` section (creates the section if missing), with a comment
marker so the line is distinguishable from auto-link lines.

Scope discipline (v1, per handoff): tag-overlap + simple negation only. Real
semantic opposition is delegated to v2. Supersession and version-drift patterns
are explicitly deferred — see TODO(v2) below.

CLI:
    python wiki_contradiction_scan.py <page-path> [--limit 5] [--qmd qmd] [--dry-run]

Exit codes: 0 on success (including no-contradictions no-op), 1 on hard error
(missing file, unparseable page). Best-effort: qmd unavailable or returns empty
is a clean no-op, not a failure.

Marker convention (idempotency):
  - A `<!-- contradiction-scan: detected YYYY-MM-DD -->` line + a
    `- [[slug]]@contradicts` line under `## Auto-related` is the injection shape.
  - Re-running the scan does not duplicate: lines that already carry the marker
    for the same slug + date are left as-is.
  - Hand-authored `## Related` is NEVER touched (same contract as
    wiki_after_write.py).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# TODO(v2): supersession ("X was fixed in v1.2" vs "X is broken") and
# version-drift ("requires v2.1" vs "works on v1.0") heuristics. v1 is
# tag-overlap + simple negation-keyword matching only, per stream-2 handoff.

VAULT_ROOT = Path("P:/.data/wiki")
CONCEPTS_DIR = VAULT_ROOT / "concepts"
AUTO_SECTION_HEADER = "## Auto-related"
MAX_QUERY_CHARS = 400

# Polarity keyword sets. v1 heuristic looks for the SAME content noun phrase
# flanked by opposing polarity words across two pages.
POLARITY_POSITIVE = {
    "works", "working", "fixed", "correct", "true", "success", "succeeded",
    "passes", "passing", "valid", "functional", "verified", "confirmed",
    "supported", "resolves", "resolved",
}
POLARITY_NEGATIVE = {
    "broken", "regressed", "regression", "fails", "failing", "wrong", "false",
    "incorrect", "buggy", "fail", "failed", "deprecated", "obsolete", "unsupported",
    "broken", "missing", "absent",
}

# Common English stop words. Kept short on purpose — only used to make
# content-token overlap meaningful.
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "with", "by", "from", "as", "it", "its", "not", "no", "if", "so",
    "than", "then", "also", "such", "any", "all", "each", "into", "via", "per",
    "we", "you", "they", "i", "he", "she", "do", "does", "did", "have", "has",
    "had", "can", "could", "should", "would", "will", "may", "might", "must",
    "shall", "one", "two", "three", "more", "most", "some", "very", "just",
    "use", "used", "using", "page", "pages", "section", "file", "files",
    "note", "notes", "case", "cases",
}

CONTENT_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
TAGS_RE = re.compile(r"^tags:\s*\[([^\]]*)\]", re.MULTILINE)
CONTRADICTION_COMMENT_RE = re.compile(
    r"<!--\s*contradiction-scan:\s*detected\s+(\d{4}-\d{2}-\d{2})\s*-->"
)
CONTRADICTION_LINK_RE = re.compile(r"^\s*-\s*\[\[([^\]]+)\]\]@contradicts\s*$")


def read_frontmatter(text: str) -> dict:
    """Extract title, summary, and tags from YAML frontmatter (defensive)."""
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
    m_block = re.search(r"^summary:\s*[>|]\s*\n((?:[ \t]+.+\n?)+)", fm, re.MULTILINE)
    if m_block:
        lines = [ln.strip() for ln in m_block.group(1).splitlines()]
        out["summary"] = " ".join(lines).strip()
    else:
        m_inline = re.search(r"^summary:\s+(.+?)\s*$", fm, re.MULTILINE)
        if m_inline:
            out["summary"] = m_inline.group(1).strip().strip('"').strip("'")

    m_tags = TAGS_RE.search(fm)
    if m_tags:
        raw = m_tags.group(1)
        tags = [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
        out["tags"] = tags

    return out


def build_query(meta: dict) -> str:
    """Build a QMD query from tags first, then title/summary. Truncated."""
    parts: list[str] = []
    tags = meta.get("tags") or []
    parts.extend(tags[:5])
    title = meta.get("title", "")
    summary = meta.get("summary", "")
    if title:
        parts.append(title)
    if summary:
        parts.append(summary)
    return " ".join(p for p in parts if p)[:MAX_QUERY_CHARS]


def query_qmd(query: str, limit: int, qmd_bin: str) -> list[dict]:
    """Run qmd search, return parsed results. Empty list on any failure."""
    if not query:
        return []
    try:
        proc = subprocess.run(
            [qmd_bin, "search", "--collection", "wiki",
             "--limit", str(limit + 5), "--format", "json", query],
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
    norm = file_field.replace("\\", "/")
    if "/concepts/" not in norm:
        return None
    name = norm.rsplit("/", 1)[-1]
    if not name.endswith(".md"):
        return None
    return name[:-3]


def find_overlapping_via_grep(tags: list[str], self_slug: str) -> list[tuple[str, int]]:
    """Fallback: scan concepts/ for files with overlapping tags. Returns [(slug, overlap_count)]."""
    if not tags or not CONCEPTS_DIR.exists():
        return []
    tag_set = {t.lower() for t in tags if t}
    if not tag_set:
        return []
    results: list[tuple[str, int]] = []
    for path in CONCEPTS_DIR.glob("*.md"):
        slug = path.stem
        if slug == self_slug:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = read_frontmatter(text)
        other_tags = {t.lower() for t in (meta.get("tags") or [])}
        overlap = tag_set & other_tags
        if overlap:
            results.append((slug, len(overlap)))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


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
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^#{1,2} \S", lines[j]):
            end = j
            break
    return start, end


def extract_claims(text: str) -> list[str]:
    """Pull bullet-pointed lines from `## Summary` and `## Key Findings` sections.

    Within each section, bullets at top level (one leading `-` or `*`).
    Sentence-level lines that are not bullets are ignored for v1 — heuristic
    needs a discrete claim unit, and bullets are what authors use for claims.
    """
    claims: list[str] = []
    for header in ("## Summary", "## Key Findings"):
        bounds = find_section_bounds(text, header)
        if bounds is None:
            continue
        start, end = bounds
        lines = text.splitlines()[start + 1:end]
        for ln in lines:
            m = BULLET_RE.match(ln)
            if m:
                claims.append(m.group(1).strip())
    return claims


def tokenize_claim(claim: str) -> set[str]:
    """Return content-word set: lowercase alphanumeric tokens minus stop words."""
    raw = CONTENT_TOKEN_RE.findall(claim.lower())
    return {t for t in raw if t not in STOP_WORDS and len(t) >= 3}


def polarity_of_claim(claim: str) -> set[str]:
    """Return the polarity words present in a claim."""
    tokens = set(claim.lower().split())
    pos = tokens & POLARITY_POSITIVE
    neg = tokens & POLARITY_NEGATIVE
    return pos, neg  # type: ignore[return-value]


def detect_negation_contradiction(
    claims_a: list[str], claims_b: list[str],
) -> Optional[tuple[str, str]]:
    """Find first claim pair (one from A, one from B) where the same content
    nouns are flanked by opposing polarity words. Returns (claim_a, claim_b)
    or None if no clear contradiction exists.

    Honest heuristic: requires (1) shared content tokens >= 3 between claims,
    (2) one claim contains a positive polarity word, (3) the other contains a
    negative polarity word. If any condition fails, this is not a contradiction
    — we err on the side of no-op to avoid fabricating.
    """
    for a in claims_a:
        tokens_a = tokenize_claim(a)
        pos_a, neg_a = polarity_of_claim(a)
        if not pos_a and not neg_a:
            continue
        for b in claims_b:
            tokens_b = tokenize_claim(b)
            pos_b, neg_b = polarity_of_claim(b)
            if not pos_b and not neg_b:
                continue
            shared = tokens_a & tokens_b
            if len(shared) < 3:
                continue
            # Must be opposing: (A positive AND B negative) OR (A negative AND B positive)
            opposing = (
                (pos_a and neg_b) or (neg_a and pos_b)
            )
            if opposing:
                return a, b
    return None


def load_page_concepts(slug: str) -> Optional[Path]:
    """Resolve a concept slug to its file path under concepts/."""
    path = CONCEPTS_DIR / f"{slug}.md"
    if not path.exists():
        return None
    return path


def inject_contradiction(text: str, slug: str, today: str) -> str:
    """Inject `- [[slug]]@contradicts` with a contradiction-scan marker into
    the `## Auto-related` section. Idempotent: if the (slug, today) pair is
    already present, no change. Never touches `## Related`."""
    section_marker = f"<!-- contradiction-scan: detected {today} -->"
    bounds = find_section_bounds(text, AUTO_SECTION_HEADER)
    new_line = f"{section_marker}\n- [[{slug}]]@contradicts"

    if bounds is not None:
        start, end = bounds
        lines = text.splitlines(keepends=True)
        # Get current section body (lines after the header, up to end)
        body = lines[start + 1:end]
        body_text = "".join(body)

        # Idempotency: if this (slug, today) marker is already in this section, skip.
        if section_marker in body_text and f"[[{slug}]]@contradicts" in body_text:
            return text

        # Drop the trailing blank lines from the body, append our block, ensure
        # the section ends with a single trailing newline before the next header.
        body_stripped = "".join(body).rstrip() + "\n\n"
        rebuilt = "".join(lines[:start]) + f"{AUTO_SECTION_HEADER}\n\n{body_stripped}{new_line}\n\n" + "".join(lines[end:])
        return rebuilt

    # No `## Auto-related` section: create one. Place it AFTER any `## Related`
    # section (preserving the hand-authored section) and BEFORE any subsequent
    # `## ` heading. If no `## Related` either, append at end.
    related_bounds = find_section_bounds(text, "## Related")
    lines = text.splitlines(keepends=True)
    if related_bounds is not None:
        rel_start, rel_end = related_bounds
        # Insert AFTER the Related section, at rel_end.
        before = "".join(lines[:rel_end])
        after = "".join(lines[rel_end:])
        # Ensure exactly one blank line between Related and Auto-related.
        before = before.rstrip() + "\n\n"
        return before + f"{AUTO_SECTION_HEADER}\n\n{new_line}\n\n" + after.lstrip("\n")

    # No Related either: append at end.
    return text.rstrip() + "\n\n" + f"{AUTO_SECTION_HEADER}\n\n{new_line}\n\n"


def contradiction_scan(
    page_path: Path, limit: int, qmd_bin: str, dry_run: bool,
) -> dict:
    """Run the contradiction scan on a page. Returns a JSON-friendly report."""
    if not page_path.exists():
        return {"ok": False, "error": f"page not found: {page_path}"}
    text = page_path.read_text(encoding="utf-8")
    meta = read_frontmatter(text)
    if not meta:
        return {"ok": False, "error": f"page has no parseable frontmatter: {page_path}"}

    self_slug = page_path.stem
    tags = meta.get("tags") or []

    # --- Step 1: find overlapping pages (QMD primary, grep fallback) ---
    candidates: list[tuple[str, float]] = []  # (slug, score)
    query = build_query(meta)
    qmd_results = query_qmd(query, limit, qmd_bin)
    used_fallback = False
    for r in qmd_results:
        slug = slug_from_file(r.get("file", ""))
        if not slug or slug == self_slug:
            continue
        score = r.get("score", 0.0)
        if score < 0.1:
            continue
        candidates.append((slug, float(score)))
        if len(candidates) >= limit:
            break

    if not candidates:
        # Fallback: grep by tag overlap.
        used_fallback = True
        grep_hits = find_overlapping_via_grep(tags, self_slug)
        for slug, overlap_count in grep_hits[:limit]:
            candidates.append((slug, float(overlap_count)))

    if not candidates:
        return {
            "ok": True,
            "page": str(page_path),
            "self_slug": self_slug,
            "candidates": [],
            "contradictions": [],
            "note": "no overlapping concept pages found",
            "used_fallback": used_fallback,
            "dry_run": dry_run,
        }

    # --- Step 2: for each candidate, check for negation contradiction ---
    today = date.today().isoformat()
    self_claims = extract_claims(text)
    contradictions: list[dict] = []

    for slug, score in candidates:
        other_path = load_page_concepts(slug)
        if other_path is None:
            continue
        try:
            other_text = other_path.read_text(encoding="utf-8")
        except OSError:
            continue
        other_claims = extract_claims(other_text)
        pair = detect_negation_contradiction(self_claims, other_claims)
        if pair is None:
            continue
        contradictions.append({
            "slug": slug,
            "score": score,
            "claim_self": pair[0],
            "claim_other": pair[1],
        })
        if len(contradictions) >= limit:
            break

    if not contradictions:
        return {
            "ok": True,
            "page": str(page_path),
            "self_slug": self_slug,
            "candidates": [s for s, _ in candidates],
            "contradictions": [],
            "note": "no contradictions found (overlap exists but no opposing polarity claims)",
            "used_fallback": used_fallback,
            "dry_run": dry_run,
        }

    # --- Step 3: inject into `## Auto-related` ---
    today = date.today().isoformat()
    injected: list[str] = []
    for c in contradictions:
        slug = c["slug"]
        if dry_run:
            injected.append(slug)
            continue
        text = inject_contradiction(text, slug, today)
        injected.append(slug)

    if not dry_run:
        page_path.write_text(text, encoding="utf-8")

    return {
        "ok": True,
        "page": str(page_path),
        "self_slug": self_slug,
        "candidates": [s for s, _ in candidates],
        "contradictions": contradictions,
        "injected": injected,
        "used_fallback": used_fallback,
        "dry_run": dry_run,
    }


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(
        prog="wiki_contradiction_scan.py",
        description="Tag-overlap + simple negation contradiction scan for wiki pages.",
    )
    p.add_argument("page", help="absolute path to the wiki page just written")
    p.add_argument("--limit", type=int, default=5,
                   help="max contradictions to flag/inject (default 5)")
    p.add_argument("--dry-run", action="store_true",
                   help="report candidates, do not write")
    p.add_argument("--qmd", default="qmd", help="qmd binary (default: qmd on PATH)")
    args = p.parse_args(argv)

    report = contradiction_scan(Path(args.page), args.limit, args.qmd, args.dry_run)
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())