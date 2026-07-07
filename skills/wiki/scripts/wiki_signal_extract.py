"""
wiki_signal_extract.py — Scan a source directory for durable-finding candidates
that whole-file LLM-skim agents miss (because they only read the first ~150 lines).

Strategy: regex-based sentence extraction across ALL content of ALL files, dedupe
against the existing wiki via 4-shingle overlap, rank files by signal density.
Output is a candidate list for the downstream filter (wiki_signal_filter.py) and
then LLM verification — NOT direct ingest.

Pipeline:  wiki_signal_extract.py  →  wiki_signal_filter.py  →  LLM triage → wiki pages
           (scan + dedupe vs wiki)   (drop noise + require     (distill survivors into
                                       durable signature)       real concept pages)

Usage:
    python wiki_signal_extract.py \\
        --source C:/Users/brsth/Downloads \\
        --wiki P:/.data/wiki/concepts \\
        --out P:/.data/wiki/_incoming/signal_candidates.json \\
        --report P:/.data/wiki/_incoming/signal_report.md
    python wiki_signal_extract.py --help
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from collections import defaultdict

# Signal patterns — sentences likely to contain durable findings.
# A sentence matching ANY pattern is a candidate; the downstream filter then
# applies the durable-signature + tool-output-noise gates.
SIGNAL_PATTERNS = [
    # Causal / root-cause
    r"\broot cause\b",
    r"\bthe (?:real|actual|underlying) (?:reason|cause|issue|problem)\b",
    r"\bbecause\b.{0,80}(?:fail|break|block|crash|hang|silent|inert|dead)\b",
    r"\bthe fix (?:is|was)\b",
    r"\bfix(?:ed|es)? (?:by|via|requires?)\b",
    r"\bcaused by\b",
    r"\bhappens when\b",
    r"\bthis (?:fails|breaks|blocks?|means)\b",
    # Decision / rejection
    r"\bwe (?:decided|chose|rejected|adopted)\b",
    r"\brejected (?:because|since)\b",
    r"\btrade-?off\b",
    r"\bbetter (?:to|than)\b.{0,60}(?:because|since|as)\b",
    r"\bwrong (?:layer|approach|frame|fix)\b",
    # Measurement
    r"\b\d+(?:\.\d+)?\s*(?:ms|seconds?|s\b|tokens?|KB|MB|GB|chars?|lines?|fires?)\b",
    r"\bn\s*=\s*\d+",
    r"\b\d{2,3}%",
    r"\b~\d+",  # ~3012, ~2K
    # Code/contract specifics
    r"\b[\w_]+\.py:\d+",
    r"\bexit code \d",
    r"\breturns? (?:true|false|none|null)\b.{0,60}(?:if|when|because)\b",
    # Silent failure / design flaw
    r"\bsilently\b.{0,40}(?:fail|drop|ignore|swallow|skip|discard)\b",
    r"\bnever (?:fires?|runs?|reaches?|executes?|registered)\b",
    r"\binverts? (?:causality|the)\b",
    r"\bdead code\b",
    r"\borphan(?:ed)?\b",
    r"\bnot (?:wired|registered|in the router)\b",
    # Limits / contracts
    r"\bcannot\b.{0,40}(?:rewrite|intercept|block|enforce|detect)\b",
    r"\bMUST (?:not|be|emit|print|use)\b",
    r"\bby design\b",
    r"\bplatform (?:limit|constraint)\b",
]
SIGNAL_RE = re.compile("|".join(SIGNAL_PATTERNS), re.IGNORECASE)

# Rough sentence splitter — good enough; the downstream filter re-checks length.
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“•\-*])")


def shingles(text: str, k: int = 4) -> set[str]:
    """4-word shingles for Jaccard-style overlap vs wiki."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < k:
        return set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def extract_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    parts = SENT_SPLIT.split(text)
    out: list[str] = []
    for p in parts:
        for sub in re.split(r"\s*[•\-\*]\s+|\s*\n\s*", p):
            sub = sub.strip()
            if 30 <= len(sub) <= 400:
                out.append(sub)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="Source directory to scan (e.g. C:/Users/brsth/Downloads)")
    ap.add_argument("--wiki", default="P:/.data/wiki/concepts", help="Wiki vault dir for novelty dedup")
    ap.add_argument("--out", required=True, help="Output JSON path (candidates for downstream filter)")
    ap.add_argument("--report", default=None, help="Optional markdown report path (top files + samples)")
    ap.add_argument("--wiki-overlap", type=float, default=0.5,
                    help="Skip sentences with >= this 4-shingle overlap vs wiki (default 0.5)")
    ap.add_argument("--exts", default=".txt,.md", help="Comma-separated file extensions to scan (default .txt,.md)")
    args = ap.parse_args()

    source = Path(args.source)
    wiki = Path(args.wiki)
    if not source.is_dir():
        print(f"ERROR: source dir not found: {source}", flush=True)
        return 1

    exts = tuple("." + e.lstrip(".").lower() for e in args.exts.split(","))

    # Default skip patterns: session-export chain files are already ingested
    # by a previous /wiki signal-extract run (their signal-* pages exist in the
    # wiki). Scanning them wastes time — they're the same transcripts the
    # LLM-skim agents already processed.
    DEFAULT_SKIP = {"chain_*.md"}

    # 1. Build wiki shingle index
    wiki_shingles: set[str] = set()
    wiki_pages = list(wiki.glob("*.md")) if wiki.is_dir() else []
    for p in wiki_pages:
        try:
            wiki_shingles |= shingles(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    print(f"wiki shingle index: {len(wiki_shingles)} unique (from {len(wiki_pages)} pages)")

    # 1b. Load SHA256 hashes already in wiki log.md (reuse wiki_manifest dedup)
    log_file = (Path(wiki) / "log.md") if wiki.is_dir() else None
    existing_hashes: set[str] = set()
    if log_file and log_file.exists():
        log_text = log_file.read_text(encoding="utf-8", errors="replace")
        existing_hashes = set(re.findall(r"SHA256:([a-f0-9]{64})", log_text))
    print(f"log.md already-injected hashes: {len(existing_hashes)}")

    # 2. Walk source, extract signal sentences (skip chains + already-hashed files)
    import fnmatch
    def _is_skipped(f: Path) -> bool:
        name = f.name
        for pat in DEFAULT_SKIP:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    files = [f for f in source.iterdir() if f.is_file() and f.suffix.lower() in exts and not _is_skipped(f)]
    print(f"scanning {len(files)} files (skipped {sum(1 for f in source.iterdir() if f.is_file() and _is_skipped(f))} chain files)...")

    per_file: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
    seen_sentences: set[str] = set()
    novel_count = 0

    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for sent in extract_sentences(text):
            if not SIGNAL_RE.search(sent):
                continue
            key = re.sub(r"\s+", " ", sent.lower().strip())[:120]
            if key in seen_sentences:
                continue
            seen_sentences.add(key)
            sh = shingles(sent)
            if not sh:
                continue
            overlap = len(sh & wiki_shingles) / len(sh)
            if overlap >= args.wiki_overlap:
                continue
            per_file[f.name].append((len(sent), sent, 1.0 - overlap))
            novel_count += 1

    print(f"novel signal sentences: {novel_count}")
    print(f"files with signals: {len(per_file)}")

    # 3. Write candidates JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_sigs = [
        {"file": name, "sentence": sent, "novelty": nov}
        for name, sigs in per_file.items()
        for _len, sent, nov in sigs
    ]
    all_sigs.sort(key=lambda x: -x["novelty"])
    out_path.write_text(json.dumps(all_sigs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote: {out_path} ({len(all_sigs)} candidates)")

    # 4. Optional report — top 30 files by signal count
    if args.report:
        ranked = []
        for name, sigs in per_file.items():
            size_kb = (source / name).stat().st_size / 1024
            density = len(sigs) / max(1.0, size_kb)
            ranked.append((name, len(sigs), density, sigs))
        ranked.sort(key=lambda x: -x[1])
        lines = [
            "# Signal candidates (code-extracted, LLM-unverified)",
            "",
            f"- Source: `{source}`",
            f"- Wiki: `{wiki}` ({len(wiki_pages)} pages)",
            f"- Novel signal sentences: {novel_count}",
            f"- Files with any signal: {len(per_file)}",
            f"- Next step: pipe `{out_path}` through `wiki_signal_filter.py`",
            "",
            "## Top 30 files by novel-signal count",
            "",
        ]
        for name, n, density, sigs in ranked[:30]:
            size_kb = (source / name).stat().st_size / 1024
            lines.append(f"### {name} ({n} signals, {size_kb:.0f}KB, density {density:.2f}/KB)")
            for _len, sent, nov in sorted(sigs, key=lambda x: -x[2])[:8]:
                lines.append(f"- **nov={nov:.0%}** {sent}")
            lines.append("")
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
