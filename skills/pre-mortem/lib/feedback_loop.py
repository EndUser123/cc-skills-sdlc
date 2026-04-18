"""Pre-mortem feedback loop — surfaces pending validations for /reflect integration.

Provides PreMortemFeedbackLoop class that:
- Reads pre-mortem session registry (sessions.json)
- Returns sessions pending validation (older than threshold)
- Extracts HIGH/MEDIUM items from p3.md as lesson candidates
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Resolve STAGING_ROOT consistent with premortem_io.py
# Goes up from pre-mortem/lib/ to .claude/ to P:\
STAGING_ROOT = Path(__file__).parent.parent.parent.parent / ".evidence" / "pre-mortem"


def _get_terminal_id() -> str:
    """Get terminal ID for session isolation."""
    try:
        search_research_root = (
            Path(__file__).parent.parent.parent.parent.parent / "packages" / "search-research" / "src"
        )
        if str(search_research_root) not in sys.path:
            sys.path.insert(0, str(search_research_root))
        from core.terminal_id import canonical_terminal_id

        return canonical_terminal_id()
    except (OSError, ModuleNotFoundError):
        hostname = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
        return f"{hostname}-{os.getpid()}"


class PreMortemFeedbackLoop:
    """Surfaces pre-mortem sessions pending validation for kill-criteria checking."""

    def __init__(self, memory_dir: Path | None = None):
        """Initialize feedback loop.

        Args:
            memory_dir: Override for STAGING_ROOT. Defaults to standard evidence path.
        """
        self.staging_root = memory_dir or STAGING_ROOT
        self.sessions_file = self.staging_root / "sessions.json"

    def get_pending_validations(self, days_threshold: int = 30) -> list[Path]:
        """Return pre-mortem session dirs that need validation review.

        A session is pending if:
        - It has a p3.md (critique completed)
        - No validation timestamp exists in source_metadata.json
        - Session is older than days_threshold

        Args:
            days_threshold: Minimum age in days before a session is considered pending.

        Returns:
            List of Path objects for session directories needing validation.
        """
        pending = []
        cutoff = datetime.now() - timedelta(days=days_threshold)

        if not self.sessions_file.exists():
            return pending

        try:
            registry = json.loads(self.sessions_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return pending

        for terminal_id, info in registry.items():
            session_dir = self.staging_root / info.get("session_dir", "")
            if not session_dir.exists() or not session_dir.is_dir():
                continue

            # Check if p3.md exists (critique completed)
            p3_path = session_dir / "p3.md"
            if not p3_path.exists():
                continue

            # Check metadata for validation timestamp
            meta_path = session_dir / "source_metadata.json"
            validated = False
            try:
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    validated = "validated_at" in meta or "validation_timestamp" in meta
            except (json.JSONDecodeError, OSError):
                pass

            if validated:
                continue

            # Check age
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(session_dir))
                if mtime >= cutoff:
                    continue  # Too recent
            except OSError:
                continue

            pending.append(session_dir)

        # Sort by mtime, oldest first
        pending.sort(key=lambda p: os.path.getmtime(p))
        return pending


def extract_critique_lessons(session_dirs: list[Path]) -> list[dict]:
    """Extract HIGH/MEDIUM severity items from pre-mortem p3.md files.

    Each returned dict has:
        - skill_name: always "pre-mortem"
        - type: "critique_lesson"
        - severity: "high" | "medium" | "low"
        - content: findings text
        - session_dir: path to session
        - health_score: int or None

    Args:
        session_dirs: List of pre-mortem session directories.

    Returns:
        List of lesson dicts extracted from p3.md HIGH/MEDIUM items.
    """
    lessons = []

    for session_dir in session_dirs:
        p3_path = session_dir / "p3.md"
        if not p3_path.exists():
            continue

        try:
            content = p3_path.read_text(encoding="utf-8")
        except OSError:
            continue

        # Extract health score
        health_match = re.search(r"Health Score:\s*(\d+)%", content)
        health_score = int(health_match.group(1)) if health_match else None

        # Extract HIGH items
        high_items = _extract_severity_items(content, "HIGH")
        for item_text in high_items:
            lessons.append({
                "skill_name": "pre-mortem",
                "type": "critique_lesson",
                "confidence_score": 0.9 if health_score and health_score < 60 else 0.75,
                "severity": "high",
                "content": item_text.strip(),
                "session_dir": str(session_dir.name),
                "health_score": health_score,
            })

        # Extract MEDIUM items
        medium_items = _extract_severity_items(content, "MEDIUM")
        for item_text in medium_items:
            lessons.append({
                "skill_name": "pre-mortem",
                "type": "critique_lesson",
                "confidence_score": 0.7 if health_score and health_score < 60 else 0.6,
                "severity": "medium",
                "content": item_text.strip(),
                "session_dir": str(session_dir.name),
                "health_score": health_score,
            })

    return lessons


def _extract_severity_items(content: str, severity: str) -> list[str]:
    """Extract all [SEVERITY] items from p3.md content.

    Uses split-first to avoid DOTALL regex greediness across item boundaries.
    Returns list of "Title — Description" strings.
    """
    items: list[str] = []

    # Split content by numbered-item headers for this severity
    # Pattern matches the START of a numbered item: "N.N. [SEVERITY] ..."
    header_re = re.escape(severity)
    parts = re.split(rf"(?=^\d+\.\d+\.\s*\[{header_re}\])", content, flags=re.MULTILINE)

    # Separator is em-dash followed by backtick-reference (description always starts with `path:line`)
    # Use negative lookahead to prevent em-dash WITHIN a title from being treated as separator
    item_re = re.compile(
        r"^\d+\.\d+\.\s*\["
        + re.escape(severity)
        + r"]\s+(.+?)\s+—\s*(?=`.+?:\d+)(.+)",
        re.MULTILINE | re.DOTALL,
    )

    for part in parts:
        if not part.strip():
            continue
        m = item_re.match(part)
        if m:
            title = m.group(1).strip()
            # Collapse internal whitespace but keep sentence breaks
            desc = re.sub(r"[ \t]+", " ", m.group(2).strip())
            desc = re.sub(r"\n+", " ", desc)
            items.append(f"{title} — {desc}")

    return items
