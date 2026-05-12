"""
wiki_manifest.py — Generate ingest manifest for /wiki ingest pipeline.

Usage:
    python wiki_manifest.py                          # default: C:/Users/brsth/Downloads/*.md
    python wiki_manifest.py --source yt-is         # P:/.data/yt-is/transcripts/*.txt
    python wiki_manifest.py --source /path/to/dir   # custom path, .txt files
    python wiki_manifest.py --resume               # re-run with existing manifest, skip already-done/skipped entries
    python wiki_manifest.py --help                 # show full help

For stdin-based source injection (used by YouTube URL handler):
    "yt-is" | python wiki_manifest.py --stdin-source

Exit codes: zero on success, non-zero on error.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

# --- Slug generation with collision fix ---
_MAX_SLUG_LEN = 60  # safe max for filesystem


def sha256_first8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def make_slug(filename: str) -> str:
    """Slugify: lowercase ASCII alphanumeric + hyphens. Non-ASCII is NFKD-normalized then stripped.

    Non-ASCII characters are transliterated to ASCII equivalents where possible.
    If the result is empty (e.g. pure CJK), falls back to 'untitled'.
    """
    name = Path(filename).stem  # strip extension
    # NFKD normalization + ASCII stripping: é→e, 中文→[stripped]
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", errors="ignore").decode("ascii")
    slug_base = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if not slug_base:
        slug_base = "untitled"
    # Truncate to leave room for disambiguator
    if len(slug_base) > _MAX_SLUG_LEN - 9:  # 8 hex + 1 hyphen
        slug_base = slug_base[: _MAX_SLUG_LEN - 9]
    return slug_base


def make_collision_slug(filename: str, file_path: Path) -> str:
    """Collision-safe slug: slug + SHA256[:8] from file content.

    Use this when ingesting files where two different filenames must not collide.
    """
    slug = make_slug(filename)
    h = sha256_first8(file_path)
    return f"{slug}-{h}"


# --- Tier classification ---
MAX_SAFE = 200_000  # bytes — safe for single LLM call
MAX_WARN = 500_000  # bytes — warn but attempt ingest


def classify_tier(size: int) -> str:
    if size > MAX_WARN:
        return "large_skip"
    elif size > MAX_SAFE:
        return "large_warn"
    return "safe"


# --- Manifest generation ---
def build_manifest(
    src_dir: Path,
    ext: str,
    log_file: Path,
    manifest_path: Path,
    resume: bool = False,
) -> dict:
    """Build ingest manifest and write to manifest_path.

    Returns a summary dict with counts.
    """
    # Load existing hashes from log (dedup)
    existing: set[str] = set()
    if log_file.exists():
        text = log_file.read_text(encoding="utf-8")
        existing = set(re.findall(r"SHA256:([a-f0-9]{64})", text))

    entries = []
    for f in sorted(src_dir.glob(f"*{ext}"), key=lambda p: p.stat().st_size, reverse=True):
        h = hashlib.sha256(f.read_bytes()).hexdigest()

        # Load existing manifest to check prior status if --resume
        prior_status = None
        if resume and manifest_path.exists():
            try:
                prior = json.loads(manifest_path.read_text(encoding="utf-8"))
                for pe in prior:
                    if pe.get("path") == str(f):
                        prior_status = pe.get("status")
                        break
            except (json.JSONDecodeError, OSError):
                pass

        # Skip if already ingested (hash in log)
        if h in existing:
            entries.append(
                {"path": str(f), "size": f.stat().st_size, "hash": h, "status": "skipped", "reason": "already_ingested"}
            )
            continue

        # If --resume and was already processed, mark skipped
        if resume and prior_status in ("done", "skipped"):
            entries.append(
                {"path": str(f), "size": f.stat().st_size, "hash": h, "status": "skipped", "reason": "already_processed"}
            )
            continue

        sz = f.stat().st_size
        tier = classify_tier(sz)
        entries.append({"path": str(f), "size": sz, "hash": h, "status": "pending", "tier": tier})

    manifest_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    return {
        "total": len(entries),
        "safe": sum(1 for e in entries if e.get("tier") == "safe"),
        "large_warn": sum(1 for e in entries if e.get("tier") == "large_warn"),
        "large_skip": sum(1 for e in entries if e.get("tier") == "large_skip"),
        "skipped": sum(1 for e in entries if e.get("status") == "skipped"),
        "pending": sum(1 for e in entries if e.get("status") == "pending"),
    }


# --- CLI ---
DEFAULT_SRC = Path(os.path.expanduser("~/Downloads"))
DEFAULT_VAULT = Path("P:/.data/wiki")
MANIFEST_DEFAULT = Path("/tmp/wiki_ingest_manifest.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate /wiki ingest manifest")
    p.add_argument("--source", dest="source", help="Source mode: 'yt-is', an explicit path, or empty for default Downloads")
    p.add_argument(
        "--stdin-source",
        action="store_true",
        help="Read --source value from stdin (for pipe-based invocation from YouTube URL handler)",
    )
    p.add_argument("--vault", type=Path, default=DEFAULT_VAULT, help=f"Wiki vault dir (default: {DEFAULT_VAULT})")
    p.add_argument("--log", type=Path, help="Override log file path (default: <vault>/log.md)")
    p.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT, help=f"Manifest output path (default: {MANIFEST_DEFAULT})")
    p.add_argument(
        "--resume",
        action="store_true",
        help="Skip entries already marked done/skipped in existing manifest (prevents re-dispatch on retry after crash)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Stdin source injection (YouTube URL handler uses: "yt-is" | python wiki_manifest.py --stdin-source)
    source_override = None
    if args.stdin_source and not sys.stdin.isatty():
        source_override = sys.stdin.read().strip()

    # Determine source directory and file extension
    effective_source = source_override or args.source
    if effective_source == "yt-is":
        # yt-nlm path outputs transcript_*.txt files to P:/.data/yt-is/
        src_dir = Path("P:/.data/yt-is")
        ext = ".txt"
    elif effective_source:
        src_dir = Path(effective_source)
        ext = ".txt"
    else:
        src_dir = DEFAULT_SRC
        ext = ".md"

    if not src_dir.exists():
        print(f"ERROR: Source directory does not exist: {src_dir}", file=sys.stderr)
        return 1

    vault_dir = args.vault
    log_file = args.log or (vault_dir / "log.md")
    manifest_path = args.manifest

    # Use tempfile if manifest path is the default /tmp path (prevents cross-terminal collision)
    if str(manifest_path) == str(MANIFEST_DEFAULT):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        manifest_path = Path(tmp.name)
        tmp.close()  # close but don't delete — file persists

    counts = build_manifest(
        src_dir=src_dir,
        ext=ext,
        log_file=log_file,
        manifest_path=manifest_path,
        resume=args.resume,
    )

    print(
        f"Manifest [{src_dir.name}]: {counts['total']} files — "
        f"safe={counts['safe']} "
        f"large_warn={counts['large_warn']} "
        f"large_skip={counts['large_skip']} "
        f"pending={counts['pending']} "
        f"skipped={counts['skipped']}"
    )
    print(f"Manifest written to: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
