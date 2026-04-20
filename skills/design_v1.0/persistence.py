"""
Architecture decision persistence module.

This module implements the Output Persistence protocol from shared_frameworks.md
for auto-saving /arch outputs to make them searchable by CKS.

Usage Monitoring:
- Template chaining usage is tracked via logging (routing.py)
- Chain usage events are saved to arch_decisions/index.jsonl
- Monitor alert: No chaining usage for 30 days signals failed feature
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "save_arch_decision",
    "should_skip_persistence",
    "generate_decision_filename",
    "DECISIONS_DIR",
    "INDEX_FILE",
    "track_template_chaining_usage",
    "check_chaining_usage_monitoring",
    "cleanup_old_entries",
    "rotate_index",
    "cleanup_orphaned_files",
    "_find_cks_db",
    "_ingest_into_cks",
    "log_decision_metrics",
    "log_candidate_metrics",
    "METRICS_DIR",
    "DECISIONS_LOG_FILE",
    "CANDIDATES_LOG_FILE",
]

# Constants
DECISIONS_DIR = Path(".claude/arch_decisions")
INDEX_FILE = DECISIONS_DIR / "index.jsonl"
METRICS_DIR = DECISIONS_DIR / "architecture" / "logs"
DECISIONS_LOG_FILE = METRICS_DIR / "decisions.jsonl"
CANDIDATES_LOG_FILE = METRICS_DIR / "candidates.jsonl"
MIN_OUTPUT_SIZE_TO_SAVE = 2048  # 2KB minimum output size to save
CHAINING_USAGE_FILE = DECISIONS_DIR / "chaining_usage.jsonl"
CHAINING_MONITORING_DAYS = 30  # Alert if no chaining usage for 30 days

# Index cleanup constants
INDEX_MAX_ENTRIES = 1000  # Maximum entries before auto-cleanup
INDEX_ROTATE_KEEP = 500  # Keep N most recent entries when rotating
INDEX_OLD_ENTRY_DAYS = 365  # Remove entries older than N days

logger = logging.getLogger(__name__)


def should_skip_persistence(
    query: str,
    output: str,
    skip_keywords: tuple[str, ...] = ("don't save", "ephemeral", "do not persist"),
) -> bool:
    """
    Determine if a decision should be skipped from persistence.

    Skip conditions:
    - User says "don't save" or "ephemeral"
    - Query was out-of-scope (redirected to another skill)
    - Analysis was trivially short (fast template, <2KB output)

    Args:
        query: The original user query.
        output: The full /arch output content.
        skip_keywords: Keywords that indicate user wants to skip persistence.

    Returns:
        True if persistence should be skipped, False otherwise.

    Examples:
        >>> should_skip_persistence("don't save this", "...")
        True
        >>> should_skip_persistence("design a system", "x" * 100)
        True
        >>> should_skip_persistence("design a system", "x" * 3000)
        False
    """
    # Check for explicit skip keywords in query
    query_lower = query.lower()
    for keyword in skip_keywords:
        if keyword in query_lower:
            return True

    # Check for trivially short output
    if len(output) < MIN_OUTPUT_SIZE_TO_SAVE:
        return True

    return False


def generate_decision_filename(query: str, _template: str = "") -> str:
    """
    Generate a filename for an architecture decision.

    Filename format: ADR-YYYYMMDD_[slug].md

    The template name is stored in frontmatter (persistence.py save_arch_decision),
    not in the filename. This makes the format location-independent — the format
    comes from /arch skill code, not from the output directory.

    Args:
        query: The original user query (first 50 chars used for slug).
        _template: Unused — kept for API compatibility. Template is stored in frontmatter.

    Returns:
        A filename string.

    Examples:
        >>> generate_decision_filename("design a REST API", "python")
        'ADR-20260210_design-a-rest-api.md'
    """
    date = datetime.now().strftime("%Y%m%d")
    # Slug from first 50 chars of query, sanitized
    slug = re.sub(r"[^a-z0-9]+", "-", query[:50].lower()).strip("-")
    return f"ADR-{date}_{slug}.md"


def _find_cks_db() -> Path | None:
    """
    Find the CKS SQLite database by walking up the directory tree.

    Searches up to 6 parent directories of this module for ``__csf/data/cks.db``.

    Returns:
        Path to the database if found, else None.
    """
    check = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = check / "__csf" / "data" / "cks.db"
        if candidate.exists():
            return candidate
        check = check.parent
    return None


def _ingest_into_cks(
    query: str,
    template: str,
    domain: str,
    output: str,
    filename: str,
) -> None:
    """
    Ingest a saved architecture decision into the CKS database.

    This closes the learning loop: /arch reads CKS for prior context, and now
    also writes back so future /arch queries on the same domain benefit from
    accumulated decisions.

    Fails silently — CKS may not be available in all environments, and this
    must never block the primary save operation.

    Args:
        query: The original user query (used as CKS title prefix).
        template: The template name (e.g., "deep", "python").
        domain: The detected domain (e.g., "python", "cli").
        output: Full /arch output; first 2000 chars stored as CKS content.
        filename: The decision filename (stored in metadata for back-reference).
    """
    try:
        import sqlite3

        db_path = _find_cks_db()
        if db_path is None:
            logger.warning(
                "CKS ingest skipped: database not found\n"
                "Architecture decision was saved to file, but not added to CKS database.\n"
                "Future /arch queries won't benefit from this decision in semantic search.\n"
                "To enable CKS integration:\n"
                "  1. Verify CKS database exists at: P:/__csf/data/cks.db"
            )
            return

        entry_id = str(uuid.uuid4())
        title = f"{template}: {query[:80]}"
        # Truncate output to avoid bloating the DB; 2000 chars is enough for search
        content = output[:2000]
        metadata = json.dumps(
            {
                "source": "arch_decision",
                "template": template,
                "domain": domain,
                "filename": filename,
            }
        )

        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO entries
                    (id, type, title, content, metadata)
                VALUES
                    (?, ?, ?, ?, ?)
                """,
                (entry_id, "arch_decision", title, content, metadata),
            )
            conn.commit()
            logger.debug(f"CKS ingest succeeded: {title!r} → {entry_id}")
        finally:
            conn.close()

    except Exception as exc:  # noqa: BLE001
        # Non-critical — log at WARNING so user is aware of CKS integration status
        logger.warning(
            f"CKS ingest failed (non-critical): {exc}\n"
            "Architecture decision was saved to file, but not added to CKS database.\n"
            "Future /arch queries won't benefit from this decision in semantic search.\n"
            "To enable CKS integration:\n"
            "  1. Verify CKS database exists at: P:/__csf/data/cks.db\n"
            "  2. Ensure write permissions to the database file"
        )


def save_arch_decision(
    query: str,
    template: str,
    domain: str,
    output: str,
    confidence: int,
    research_sources: list[str] | None = None,
    decisions_dir: Path | None = None,
    # Optional metrics logging parameters
    metrics: dict[str, Any] | None = None,
) -> str | None:
    """
    Save an architecture decision to the arch_decisions/ directory.

    This implements the Output Persistence protocol from shared_frameworks.md.

    Args:
        query: The original user query.
        template: The template name used (e.g., "deep", "fast", "python").
        domain: The detected domain or "generic".
        output: The full /arch output content.
        confidence: Confidence level (0-100).
        research_sources: List of URLs consulted during analysis.
        decisions_dir: Override the default decisions directory path.
        metrics: Optional dict containing metrics for logging:
            - pattern: Intent pattern detected (e.g., "pattern.improve_system")
            - high_stakes: Whether this is a high-stakes decision
            - templates: Template info with "primary" and optionally "chained" keys
            - context: Context info including graph_nodes_considered, precedent_count, cks_used
            - vs: Verbalized Sampling metrics (k_generated, k_survivors, lens_survivors, has_tail_candidate)
            - judge: Judge evaluation metrics (any_candidate_invariant_violation, etc.)
            - diversity: Optional diversity metrics (min_structural_distance, mean_structural_distance)
            - candidates: Optional list of candidate dicts for individual candidate logging
            - user_outcome: Optional user outcome tracking (adoption, notes)

    Returns:
        The filepath where the decision was saved, or None if skipped.

    Raises:
        OSError: If unable to create directories or write files.

    Examples:
        >>> save_arch_decision(
        ...     "design a REST API",
        ...     "python",
        ...     "python",
        ...     "Use FastAPI with...",
        ...     85
        ... )
        '.claude/arch_decisions/2026-02-10_python_design-a-rest-api.md'
    """
    # Validate confidence range
    if not isinstance(confidence, int):
        raise TypeError(f"confidence must be an integer, got {type(confidence).__name__}")
    if not 0 <= confidence <= 100:
        raise ValueError(f"confidence must be between 0 and 100, got {confidence}")

    # Check skip conditions
    if should_skip_persistence(query, output):
        return None

    # Use provided directory or default
    if decisions_dir is None:
        decisions_dir = DECISIONS_DIR

    # Create directory if it doesn't exist
    decisions_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    filename = generate_decision_filename(query, template)
    filepath = decisions_dir / filename

    # Format research sources for frontmatter
    if research_sources is None:
        research_sources = []
    sources_str = json.dumps(research_sources)

    # Build YAML frontmatter
    date = datetime.now().strftime("%Y-%m-%d")
    frontmatter = f"""---
date: {date}
template: {template}
query: "{query}"
domain: {domain}
confidence: {confidence}
research_sources: {sources_str}
---

{output}
"""

    # Write decision file
    filepath.write_text(frontmatter, encoding="utf-8")

    # Append to index.jsonl
    index_entry = {
        "date": date,
        "template": template,
        "query": query,
        "domain": domain,
        "confidence": confidence,
        "file": filename,
    }

    # Use the same decisions_dir for index file
    index_path = decisions_dir / "index.jsonl"
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(index_entry) + "\n")

    # Auto-cleanup: Check if index exceeds max entries and rotate if needed
    # Non-critical — failures are logged but don't block the save operation
    try:
        current_entry_count = sum(1 for _ in open(index_path, encoding="utf-8"))
        if current_entry_count > INDEX_MAX_ENTRIES:
            logger.info(
                f"Index has {current_entry_count} entries (threshold: {INDEX_MAX_ENTRIES}), "
                f"triggering rotation to keep {INDEX_ROTATE_KEEP} most recent entries"
            )
            rotate_result = rotate_index(
                keep_entries=INDEX_ROTATE_KEEP,
                index_path=index_path,
                decisions_dir=decisions_dir,
            )
            logger.info(
                f"Index rotation complete: {rotate_result['entries_before']} → "
                f"{rotate_result['entries_after']} entries "
                f"({rotate_result['entries_removed']} removed)"
            )
    except Exception as exc:
        # Non-critical — log and continue
        logger.warning(f"Auto-cleanup failed (non-critical): {exc}")

    # Non-critical: write decision back into CKS so future /arch queries on
    # this domain benefit from accumulated decisions (closes the learning loop).
    # Fails silently — CKS unavailability must never block persistence.
    cks_result = _ingest_into_cks(
        query=query,
        template=template,
        domain=domain,
        output=output,
        filename=filename,
    )

    # Optional: Log decision metrics for analysis and monitoring
    # Non-critical — failures are logged but don't block the save operation
    if metrics is not None:
        try:
            # Build decision_id from timestamp and query slug
            timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%SZ")
            query_slug = re.sub(r"[^\w-]", "-", query.lower())[:30]
            decision_id = f"{timestamp}_{query_slug}"

            # Build persistence info for metrics
            persistence_info = {
                "saved": True,
                "filepath": str(filepath),
                "cks_ingest_attempted": cks_result is not None,
                "cks_ingest_ok": False,
            }

            # Call log_decision_metrics with provided metrics
            log_decision_metrics(
                decision_id=decision_id,
                query=query,
                pattern=metrics.get("pattern", "pattern.unknown"),
                high_stakes=metrics.get("high_stakes", False),
                templates=metrics.get("templates", {"primary": f"skill.arch.{template}"}),
                context=metrics.get("context", {}),
                vs=metrics.get("vs", {}),
                judge=metrics.get("judge", {}),
                diversity=metrics.get("diversity"),
                persistence=persistence_info,
                user_outcome=metrics.get("user_outcome"),
            )

            # Log individual candidates if provided
            candidates = metrics.get("candidates")
            if candidates:
                for candidate in candidates:
                    log_candidate_metrics(
                        decision_id=decision_id,
                        candidate_id=candidate.get("id", "unknown"),
                        vs=candidate.get("vs", {}),
                        critic=candidate.get("critic"),
                        selection=candidate.get("selection"),
                    )
        except Exception as exc:
            # Non-critical — log and continue
            logger.warning(f"Metrics logging failed (non-critical): {exc}")

    return str(filepath)


def load_decision_index(index_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Load the architecture decision index.

    Args:
        index_path: Override the default index file path.

    Returns:
        A list of decision index entries.

    Raises:
        FileNotFoundError: If index file doesn't exist.
        json.JSONDecodeError: If index file contains invalid JSON.
    """
    if index_path is None:
        index_path = INDEX_FILE

    decisions = []
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                decisions.append(json.loads(line))

    return decisions


def search_decisions(
    query: str,
    index_path: Path | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Search prior architecture decisions by query keywords.

    This provides CKS integration for searching prior decisions.

    Args:
        query: Search query string.
        index_path: Override the default index file path.
        limit: Maximum number of results to return.

    Returns:
        A list of matching decision entries.

    Examples:
        >>> search_decisions("hook system")
        [{'date': '2026-02-06', 'template': 'deep', 'query': '...', ...}]
    """
    try:
        decisions = load_decision_index(index_path)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    # Simple keyword matching (could be enhanced with proper search)
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored = []
    for decision in decisions:
        # Search in query and domain fields
        searchable_text = f"{decision.get('query', '')} {decision.get('domain', '')}".lower()
        score = sum(1 for word in query_words if word in searchable_text)
        if score > 0:
            scored.append((score, decision))

    # Sort by score descending and return top results
    scored.sort(key=lambda x: x[0], reverse=True)
    return [decision for _, decision in scored[:limit]]


def cleanup_old_entries(
    days_threshold: int = INDEX_OLD_ENTRY_DAYS,
    index_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Remove index entries older than a specified number of days.

    This helps prevent the index from growing unbounded over time.

    Args:
        days_threshold: Remove entries older than this many days (default: 365).
        index_path: Override the default index file path.
        dry_run: If True, report what would be deleted without actually deleting.

    Returns:
        Dictionary with cleanup statistics:
        - entries_before: Number of entries before cleanup
        - entries_after: Number of entries after cleanup
        - entries_removed: Number of entries removed
        - removed_files: List of decision files that could be deleted (if orphaned)
        - dry_run: True if this was a dry run

    Raises:
        FileNotFoundError: If index file doesn't exist.
        json.JSONDecodeError: If index file contains invalid JSON.
        ValueError: If days_threshold is negative.

    Examples:
        >>> cleanup_old_entries(days_threshold=90)
        {'entries_before': 1500, 'entries_after': 500, 'entries_removed': 1000, ...}
    """
    if days_threshold < 0:
        raise ValueError("days_threshold must be non-negative")

    if index_path is None:
        index_path = INDEX_FILE

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    # Load current index
    decisions = load_decision_index(index_path)

    stats = {
        "entries_before": len(decisions),
        "entries_after": 0,
        "entries_removed": 0,
        "removed_files": [],
        "cutoff_date": cutoff_str,
        "dry_run": dry_run,
    }

    # Filter entries older than cutoff
    filtered = []
    removed = []
    for decision in decisions:
        decision_date = decision.get("date", "")
        if decision_date >= cutoff_str:
            filtered.append(decision)
        else:
            removed.append(decision)

    stats["entries_after"] = len(filtered)
    stats["entries_removed"] = len(removed)

    if not dry_run and removed:
        # Write back filtered index
        with open(index_path, "w", encoding="utf-8") as f:
            for entry in filtered:
                f.write(json.dumps(entry) + "\n")

        # Identify orphaned decision files
        removed_files = [d.get("file") for d in removed if d.get("file")]
        stats["removed_files"] = removed_files

        logger.info(
            f"Index cleanup: removed {len(removed)} entries older than {days_threshold} days "
            f"(before: {stats['entries_before']}, after: {stats['entries_after']})"
        )
    elif dry_run and removed:
        logger.info(
            f"Dry run: would remove {len(removed)} entries older than {days_threshold} days "
            f"(before: {stats['entries_before']}, after: {stats['entries_after']})"
        )
    else:
        logger.debug(f"No entries to remove (cutoff: {cutoff_str})")

    return stats


def rotate_index(
    keep_entries: int = INDEX_ROTATE_KEEP,
    index_path: Path | None = None,
    decisions_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Rotate the index to keep only the N most recent entries.

    This is useful for keeping the index size bounded regardless of age.

    Args:
        keep_entries: Keep this many most recent entries (default: 500).
        index_path: Override the default index file path.
        decisions_dir: Directory where decision files are stored (for cleanup of orphaned files).
        dry_run: If True, report what would be deleted without actually deleting.

    Returns:
        Dictionary with rotation statistics:
        - entries_before: Number of entries before rotation
        - entries_after: Number of entries after rotation
        - entries_removed: Number of entries removed
        - removed_files: List of decision files that were removed from index
        - dry_run: True if this was a dry run

    Raises:
        FileNotFoundError: If index file doesn't exist.
        json.JSONDecodeError: If index file contains invalid JSON.
        ValueError: If keep_entries is negative.

    Examples:
        >>> rotate_index(keep_entries=100)
        {'entries_before': 500, 'entries_after': 100, 'entries_removed': 400, ...}
    """
    if keep_entries < 0:
        raise ValueError("keep_entries must be non-negative")

    if index_path is None:
        index_path = INDEX_FILE
    if decisions_dir is None:
        decisions_dir = DECISIONS_DIR

    # Load current index
    decisions = load_decision_index(index_path)

    stats = {
        "entries_before": len(decisions),
        "entries_after": 0,
        "entries_removed": 0,
        "removed_files": [],
        "keep_entries": keep_entries,
        "dry_run": dry_run,
    }

    # Keep only the most recent entries (last N in file = most recent)
    if len(decisions) > keep_entries:
        # Index is append-only, so last entries are most recent
        filtered = decisions[-keep_entries:]
        removed = decisions[:-keep_entries]

        stats["entries_after"] = len(filtered)
        stats["entries_removed"] = len(removed)

        if not dry_run:
            # Write back filtered index
            with open(index_path, "w", encoding="utf-8") as f:
                for entry in filtered:
                    f.write(json.dumps(entry) + "\n")

            # Identify files removed from index
            removed_files = [d.get("file") for d in removed if d.get("file")]
            stats["removed_files"] = removed_files

            logger.info(
                f"Index rotation: kept {keep_entries} most recent entries, "
                f"removed {len(removed)} older entries "
                f"(before: {stats['entries_before']}, after: {stats['entries_after']})"
            )
        else:
            logger.info(
                f"Dry run: would keep {keep_entries} most recent entries, "
                f"remove {len(removed)} older entries "
                f"(before: {stats['entries_before']}, after: {stats['entries_after']})"
            )
    else:
        stats["entries_after"] = len(decisions)
        logger.debug(
            f"Index has {len(decisions)} entries, no rotation needed "
            f"(threshold: {keep_entries})"
        )

    return stats


def cleanup_orphaned_files(
    index_path: Path | None = None,
    decisions_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Find and optionally delete decision files that are no longer in the index.

    This is useful after running cleanup_old_entries or rotate_index to free disk space.

    Args:
        index_path: Override the default index file path.
        decisions_dir: Directory where decision files are stored.
        dry_run: If True, report what would be deleted without actually deleting.

    Returns:
        Dictionary with cleanup statistics:
        - orphaned_files: List of orphaned file paths
        - orphaned_count: Number of orphaned files
        - total_size_bytes: Total size of orphaned files
        - deleted_count: Number of files actually deleted (0 if dry_run)
        - dry_run: True if this was a dry run

    Raises:
        FileNotFoundError: If decisions directory doesn't exist.

    Examples:
        >>> cleanup_orphaned_files(dry_run=True)
        {'orphaned_files': ['2020-01-01_old_decision.md'], 'orphaned_count': 1, ...}
    """
    if decisions_dir is None:
        decisions_dir = DECISIONS_DIR
    if index_path is None:
        index_path = INDEX_FILE

    stats = {
        "orphaned_files": [],
        "orphaned_count": 0,
        "total_size_bytes": 0,
        "deleted_count": 0,
        "dry_run": dry_run,
    }

    # Get list of files in the index
    try:
        indexed_files = set()
        for entry in load_decision_index(index_path):
            filename = entry.get("file")
            if filename:
                indexed_files.add(filename)
    except (FileNotFoundError, json.JSONDecodeError):
        # Index doesn't exist or is invalid - all files are orphans
        indexed_files = set()

    # Find all .md files in decisions directory
    decision_files = list(decisions_dir.glob("*.md"))

    # Find orphans (files on disk but not in index)
    orphans = []
    for filepath in decision_files:
        if filepath.name not in indexed_files:
            orphans.append(filepath)

    stats["orphaned_files"] = [str(f) for f in orphans]
    stats["orphaned_count"] = len(orphans)
    stats["total_size_bytes"] = sum(f.stat().st_size for f in orphans)

    if not dry_run and orphans:
        # Delete orphaned files
        for filepath in orphans:
            filepath.unlink()
        stats["deleted_count"] = len(orphans)
        logger.info(
            f"Deleted {len(orphans)} orphaned decision files "
            f"(freed {stats['total_size_bytes']} bytes)"
        )
    elif dry_run and orphans:
        logger.info(
            f"Dry run: would delete {len(orphans)} orphaned decision files "
            f"({stats['total_size_bytes']} bytes)"
        )
    else:
        logger.debug("No orphaned decision files found")

    return stats


def track_template_chaining_usage(
    primary_template: str,
    chained_domains: list[str],
    source: str,
    query: str,
    usage_file: Path | None = None,
) -> None:
    """
    Track template chaining usage for monitoring and analytics.

    Args:
        primary_template: The primary template selected (e.g., "deep", "python")
        chained_domains: List of chained domain templates (e.g., ["cli", "data-pipeline"])
        source: Selection source (e.g., "query_override", "parameter_override")
        query: Original user query
        usage_file: Override the default usage tracking file path

    Raises:
        OSError: If unable to write to usage tracking file
    """
    if not chained_domains:
        return  # No chaining to track

    # Use provided directory or default
    if usage_file is None:
        usage_file = CHAINING_USAGE_FILE

    # Create directory if it doesn't exist
    usage_file.parent.mkdir(parents=True, exist_ok=True)

    # Build usage record
    timestamp = datetime.now().isoformat()
    usage_record = {
        "timestamp": timestamp,
        "primary_template": primary_template,
        "chained_domains": chained_domains,
        "chained_count": len(chained_domains),
        "source": source,
        "query": query[:100],  # Truncate query for storage
        "date": datetime.now().strftime("%Y-%m-%d"),
    }

    # Append to usage tracking file
    try:
        with open(usage_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(usage_record) + "\n")
        logger.info(
            f"Template chaining usage tracked: {primary_template}+{'+'.join(chained_domains)} "
            f"(source={source}, chained_count={len(chained_domains)})"
        )
    except OSError as e:
        logger.error(f"Failed to write template chaining usage: {e}")


def check_chaining_usage_monitoring(
    usage_file: Path | None = None,
    days_threshold: int = CHAINING_MONITORING_DAYS,
) -> dict[str, Any]:
    """
    Check template chaining usage monitoring and return usage statistics.

    Args:
        usage_file: Override the default usage tracking file path
        days_threshold: Number of days to check for usage (default: 30)

    Returns:
        Dictionary with usage statistics:
        - total_chains_ever: Total number of chaining events ever recorded
        - chains_last_days: Number of chaining events in the last N days
        - last_chain_date: Most recent chaining event date (or None)
        - days_since_last_chain: Days since most recent chaining (or None)
        - monitoring_alert: True if no chaining in last N days

    Raises:
        FileNotFoundError: If usage file doesn't exist (not an error, returns zeros)
        json.JSONDecodeError: If usage file contains invalid JSON
    """
    if usage_file is None:
        usage_file = CHAINING_USAGE_FILE

    # Initialize default stats
    stats = {
        "total_chains_ever": 0,
        "chains_last_days": 0,
        "last_chain_date": None,
        "days_since_last_chain": None,
        "monitoring_alert": False,
        "threshold_days": days_threshold,
    }

    # Check if usage file exists
    if not usage_file.exists():
        logger.info(f"Template chaining usage file not found: {usage_file}")
        return stats

    # Calculate date threshold
    threshold_date = datetime.now() - timedelta(days=days_threshold)

    # Read usage records
    try:
        with open(usage_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    stats["total_chains_ever"] += 1

                    # Parse timestamp
                    timestamp_str = record.get("timestamp")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str)

                            # Update last chain date
                            if (
                                stats["last_chain_date"] is None
                                or timestamp > stats["last_chain_date"]
                            ):
                                stats["last_chain_date"] = timestamp

                            # Check if within threshold
                            if timestamp >= threshold_date:
                                stats["chains_last_days"] += 1
                        except ValueError:
                            logger.warning(f"Invalid timestamp format: {timestamp_str}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in usage file: {e}")
    except OSError as e:
        logger.error(f"Failed to read template chaining usage file: {e}")
        return stats

    # Calculate days since last chain
    if stats["last_chain_date"] is not None:
        stats["days_since_last_chain"] = (datetime.now() - stats["last_chain_date"]).days

    # Set monitoring alert if no chaining in threshold period
    if stats["chains_last_days"] == 0 and stats["total_chains_ever"] > 0:
        stats["monitoring_alert"] = True
        logger.warning(
            f"Template chaining monitoring alert: No chaining usage detected "
            f"in the last {days_threshold} days. "
            f"Last usage was {stats['days_since_last_chain']} days ago."
        )

    return stats


def log_decision_metrics(
    decision_id: str,
    query: str,
    pattern: str,
    high_stakes: bool,
    templates: dict[str, Any],
    context: dict[str, Any],
    vs: dict[str, Any],
    judge: dict[str, Any],
    diversity: dict[str, Any] | None = None,
    persistence: dict[str, Any] | None = None,
    user_outcome: dict[str, Any] | None = None,
    log_file: Path | None = None,
) -> None:
    """
    Log architecture decision metrics for analysis and monitoring.

    Args:
        decision_id: Unique identifier for this decision (e.g., ISO timestamp slug)
        query: Original user query
        pattern: Intent pattern detected (e.g., "pattern.improve_system")
        high_stakes: Whether this is a high-stakes decision
        templates: Template info with "primary" and optionally "chained" keys
        context: Context info including graph_nodes_considered, precedent_count, cks_used
        vs: Verbalized Sampling metrics (k_generated, k_survivors, lens_survivors, has_tail_candidate)
        judge: Judge evaluation metrics (any_candidate_invariant_violation, etc.)
        diversity: Optional diversity metrics (min_structural_distance, mean_structural_distance)
        persistence: Optional persistence info (saved, filepath, cks_ingest_attempted, cks_ingest_ok)
        user_outcome: Optional user outcome tracking (adoption, notes)
        log_file: Override the default decisions log file path

    Raises:
        OSError: If unable to write to metrics file
    """
    if log_file is None:
        log_file = DECISIONS_LOG_FILE

    # Create directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Build decision record
    timestamp = datetime.now().isoformat()
    decision_record = {
        "timestamp": timestamp,
        "id": decision_id,
        "query": query,
        "pattern": pattern,
        "high_stakes": high_stakes,
        "templates": templates,
        "context": context,
        "vs": vs,
        "judge": judge,
    }

    # Add optional fields
    if diversity is not None:
        decision_record["diversity"] = diversity
    if persistence is not None:
        decision_record["persistence"] = persistence
    if user_outcome is not None:
        decision_record["user_outcome"] = user_outcome

    # Append to decisions log
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(decision_record) + "\n")
        logger.info(f"Decision metrics logged: {decision_id}")
    except OSError as e:
        logger.error(f"Failed to write decision metrics: {e}")


def log_candidate_metrics(
    decision_id: str,
    candidate_id: str,
    vs: dict[str, Any],
    critic: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    log_file: Path | None = None,
) -> None:
    """
    Log individual candidate metrics for analysis and monitoring.

    Args:
        decision_id: Parent decision identifier
        candidate_id: Candidate identifier (e.g., "A", "B", "C", "D")
        vs: Verbalized Sampling data (probability, lens, changes, is_tail)
        critic: Optional critic evaluation (invariants_ok, violated_invariants, risk_score, complexity_score)
        selection: Optional selection data (survivor, recommended)
        log_file: Override the default candidates log file path

    Raises:
        OSError: If unable to write to metrics file
    """
    if log_file is None:
        log_file = CANDIDATES_LOG_FILE

    # Create directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Build candidate record
    candidate_record = {
        "decision_id": decision_id,
        "candidate_id": candidate_id,
        "vs": vs,
    }

    # Add optional fields
    if critic is not None:
        candidate_record["critic"] = critic
    if selection is not None:
        candidate_record["selection"] = selection

    # Append to candidates log
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(candidate_record) + "\n")
        logger.info(f"Candidate metrics logged: {decision_id}/{candidate_id}")
    except OSError as e:
        logger.error(f"Failed to write candidate metrics: {e}")
