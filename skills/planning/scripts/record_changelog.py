#!/usr/bin/env python3
"""Append a dated, evidence-linked entry to a project's changelog."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path


UNRELEASED_RE = re.compile(r"^##\s+\[?Unreleased\]?\s*$", re.I | re.M)


def append_entry(
    changelog: Path,
    *,
    summary: str,
    sources: str,
    claims: str,
    evidence: str,
    entry_id: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Append one entry under [Unreleased] and return its entry id."""
    if not changelog.is_file():
        raise FileNotFoundError(f"changelog does not exist: {changelog}")
    text = changelog.read_text(encoding="utf-8")
    match = UNRELEASED_RE.search(text)
    if not match:
        raise ValueError("changelog must contain a ## [Unreleased] section")
    if not summary.strip() or not sources.strip() or not claims.strip() or not evidence.strip():
        raise ValueError("summary, sources, claims, and evidence are required")

    when = timestamp or datetime.now(UTC)
    stamp = when.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    entry_id = entry_id or f"PROV-{stamp}-design"
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", entry_id):
        raise ValueError("entry_id contains unsupported characters")
    if entry_id in text:
        raise ValueError(f"entry already exists: {entry_id}")

    entry = (
        f"\n### Evidence / Design — {when.astimezone(UTC).isoformat().replace('+00:00', 'Z')} — {entry_id}\n"
        f"- Summary: {summary.strip()}\n"
        f"- Sources / checks: {sources.strip()}\n"
        f"- Claims supported: {claims.strip()}\n"
        f"- Evidence: {evidence.strip()}\n"
    )
    insert_at = match.end()
    updated = text[:insert_at] + entry + text[insert_at:]
    changelog.write_text(updated, encoding="utf-8")
    return entry_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("changelog", type=Path)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--claims", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--entry-id")
    parser.add_argument("--create-if-missing", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.create_if_missing and not args.changelog.exists():
            args.changelog.parent.mkdir(parents=True, exist_ok=True)
            args.changelog.write_text(
                "# Changelog\n\n## [Unreleased]\n",
                encoding="utf-8",
            )
        entry_id = append_entry(
            args.changelog,
            summary=args.summary,
            sources=args.sources,
            claims=args.claims,
            evidence=args.evidence,
            entry_id=args.entry_id,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(entry_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
