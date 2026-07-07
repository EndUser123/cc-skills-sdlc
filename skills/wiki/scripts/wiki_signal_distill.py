"""
wiki_signal_distill.py — Group durable-candidate sentences into self-contained
verification chunks for LLM distillation.

Each output chunk carries:
  - source_file, source_path
  - candidates: [{sentence, novelty, line_no, context_snippet}]
    where context_snippet is ±N lines around the sentence in the source file

Chunks are small enough (~2-8KB each) for any consumer: a Claude Task-tool
subagent, a local LLM via /ai-cli, or a Bifrost-routed model. The script is
LLM-agnostic — it only chunks + extracts context. Dispatch is documented in
the /wiki SKILL.md "Signal-extract Stage 3" section.

Usage:
    python wiki_signal_distill.py \\
        --in P:/.data/wiki/_incoming/durable_candidates.json \\
        --source C:/Users/brsth/Downloads \\
        --out-dir P:/.data/wiki/_incoming/distill_chunks \\
        --context-lines 15
    python wiki_signal_distill.py --help
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path


def find_line_no(lines: list[str], sentence: str) -> int:
    """Return 1-based line number of the source line most likely to anchor this
    candidate. Candidates are often newline-collapsed by the upstream extractor,
    so a start-anchored probe won't work — instead search for distinctive tokens.

    Strategy (first hit wins):
      1. file.py:line refs  (e.g. 'xyz_router.py:42')
      2. long alnum runs    (>= 8 chars, e.g. 'xyz_pipeline', 'EpistemicPolicyResult')
      3. numbers+units      (e.g. '15ms', '400 tokens', 'v3.0')
      4. short start-probe  (fallback: first 30 chars of the sentence)
    Returns 0 if nothing matches.
    """
    if not sentence:
        return 0
    # Build a list of (regex, source) probes in priority order
    probes: list[str] = []
    probes += re.findall(r"\b[\w_]+\.py:\d+", sentence)            # file.py:line
    probes += re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{7,}\b", sentence)  # long alnum
    probes += re.findall(r"\b\d+\s*(?:ms|tokens?|KB|MB|GB|%|×)\b", sentence, re.I)  # num+unit
    probes += re.findall(r"\bv\d+\.\d+\b", sentence, re.I)         # version
    # Fallback: distinctive short phrase (skip generic leading words)
    fallback = re.sub(r"\s+", " ", sentence).strip()
    if len(fallback) >= 30:
        probes.append(fallback[:30])

    for probe in probes:
        probe_lower = probe.lower()
        for i, line in enumerate(lines):
            if probe_lower in line.lower():
                return i + 1
    return 0


def extract_context(lines: list[str], line_no: int, context_lines: int) -> str:
    """Return ±context_lines around line_no (1-based). Returns '' if line_no is 0."""
    if not line_no:
        return ""
    start = max(0, line_no - 1 - context_lines)
    end = min(len(lines), line_no + context_lines)
    snippet = lines[start:end]
    # Annotate the anchor line so the reviewer can find it fast
    anchor_idx = line_no - 1 - start
    out = []
    for i, line in enumerate(snippet):
        marker = ">>> " if i == anchor_idx else "    "
        out.append(f"{marker}{start + i + 1:5d}: {line.rstrip()}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_path", required=True, help="Input durable_candidates.json from wiki_signal_filter.py")
    ap.add_argument("--source", required=True, help="Source dir the candidates came from (for reading context)")
    ap.add_argument("--out-dir", required=True, help="Output dir for one chunk-JSON per source file")
    ap.add_argument("--context-lines", type=int, default=15, help="Lines of context each side of the anchor (default 15)")
    ap.add_argument("--max-per-chunk", type=int, default=20, help="Split a file's candidates into multiple chunks above this count")
    args = ap.parse_args()

    candidates: list[dict] = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    source = Path(args.source)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Group by source file
    by_file: dict[str, list[dict]] = {}
    for c in candidates:
        by_file.setdefault(c["file"], []).append(c)

    # Source-file line cache (read once per file)
    line_cache: dict[str, list[str]] = {}

    manifest = []
    for fname, cands in by_file.items():
        src_path = source / fname
        if not src_path.exists():
            continue
        if fname not in line_cache:
            try:
                line_cache[fname] = src_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

        lines = line_cache[fname]
        # Split into sub-chunks if huge
        for chunk_idx, batch in enumerate(
            [cands[i:i + args.max_per_chunk] for i in range(0, len(cands), args.max_per_chunk)]
        ):
            enriched = []
            for c in batch:
                ln = find_line_no(lines, c["sentence"])
                ctx = extract_context(lines, ln, args.context_lines)
                enriched.append({
                    "sentence": c["sentence"],
                    "novelty": c.get("novelty", 0),
                    "line_no": ln,
                    "context_snippet": ctx,
                })
            stem = re.sub(r"[^a-z0-9]+", "-", fname.lower()).strip("-")[:40] or "source"
            chunk_name = f"{stem}-{chunk_idx}.json" if len(cands) > args.max_per_chunk else f"{stem}.json"
            chunk_path = out_dir / chunk_name
            chunk_path.write_text(json.dumps({
                "source_file": fname,
                "source_path": str(src_path),
                "chunk_index": chunk_idx,
                "candidates": enriched,
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            manifest.append({
                "chunk": str(chunk_path),
                "source_file": fname,
                "candidate_count": len(enriched),
            })

    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"grouped {len(candidates)} candidates into {len(manifest)} chunks")
    print(f"chunks: {out_dir}")
    print(f"manifest: {manifest_path}")
    print(f"\nDispatch (see /wiki SKILL.md Stage 3):")
    print(f"  - Claude subagents: one Task-tool call per chunk in _manifest.json")
    print(f"  - Local LLM: /ai-cli parallel call per chunk (chunks are self-contained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())