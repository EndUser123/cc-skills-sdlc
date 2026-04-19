#!/usr/bin/env python3
"""Auto-deduplication of refactoring findings.

Merges findings that flag the same code location, assigns canonical IDs,
and annotates each with an evidence tier.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def deduplicate_findings(
    findings_files: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    """Merge findings from multiple agents, deduplicating by file+line.

    Args:
        findings_files: List of paths to findings JSON files
        output_path: Where to write deduplicated results

    Returns:
        Deduplication report with canonical IDs and evidence tiers
    """
    # Load all findings
    all_findings: list[dict[str, Any]] = []
    agent_names: set[str] = set()

    for fp in findings_files:
        if not fp.exists():
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            findings = data.get("findings", [])
            agent = data.get("agent", fp.stem.replace("findings-", ""))
            agent_names.add(agent)
            for f in findings:
                f["_source_agent"] = agent
            all_findings.extend(findings)
        except (json.JSONDecodeError, OSError):
            continue

    # Group by (normalized_file, line)
    by_location: dict[str, list[dict[str, Any]]] = {}
    for f in all_findings:
        fp = Path(f.get("file", "")).as_posix()
        line = f.get("line", 0)
        key = f"{fp}:{line}"
        by_location.setdefault(key, []).append(f)

    # Build canonical entries
    canonical: list[dict[str, Any]] = []
    canonical_id_counter = {"COMP": 1, "DRY": 1, "CONC": 1, "QUAL": 1, "PY": 1}

    for location, findings_at_location in by_location.items():
        # Primary ID prefix from first agent's type or source agent
        first = findings_at_location[0]
        type_ = first.get("type", "unknown")
        if type_ in ["bug", "race", "error-handling", "toctou"]:
            prefix = "COMP"
        elif type_ in ["duplication", "extraction"]:
            prefix = "DRY"
        elif type_ in ["concurrency"]:
            prefix = "CONC"
        elif type_.startswith("python") or type_ in ["modern idiom", "deprecated", "async"]:
            prefix = "PY"
        else:
            prefix = "QUAL"

        seq = canonical_id_counter[prefix]
        canonical_id = f"{prefix}-{seq:03d}"
        canonical_id_counter[prefix] += 1

        # Merge descriptions (use most severe)
        descriptions = [fo.get("description", "") for fo in findings_at_location]
        description = descriptions[0]  # use first

        # Evidence tier
        confidences = [fo.get("confidence", 0) for fo in findings_at_location]
        max_confidence = max(confidences) if confidences else 0

        # Canonical entry
        entry = {
            "id": canonical_id,
            "file": first.get("file", ""),
            "line": first.get("line", 0),
            "type": type_,
            "severity": first.get("severity", "P2"),
            "description": description,
            "confidence": max_confidence,
            "evidence": first.get("evidence", ""),
            "evidence_tier": _tier_for_confidence(max_confidence),
            "duplicate_count": len(findings_at_location),
            "source_agents": list(set(fo.get("_source_agent", "unknown") for fo in findings_at_location)),
            "all_descriptions": descriptions,
        }
        canonical.append(entry)

    # Sort by severity then confidence
    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    canonical.sort(key=lambda e: (severity_order.get(e["severity"], 3), -e["confidence"]))

    result = {
        "total_unique": len(canonical),
        "total_raw": len(all_findings),
        "agents": sorted(agent_names),
        "findings": canonical,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _tier_for_confidence(confidence: int) -> str:
    """Map confidence score to evidence tier."""
    if confidence >= 90:
        return "[VERIFIED]"
    if confidence >= 80:
        return "[UNVERIFIED]"
    return "[INFERRED]"


def deduplicate_and_save(
    artifacts_dir: Path,
    target_name: str,
) -> Path:
    """Convenience wrapper using standard artifacts path.

    Args:
        artifacts_dir: Base .artifacts directory (e.g. P:/.claude/.artifacts/)
        target_name: Target identifier (e.g. "yt-is")

    Returns:
        Path to deduplicated findings JSON
    """
    refactor_dir = artifacts_dir / target_name / "refactor"
    findings_files = list(refactor_dir.glob("findings-*.json"))
    output_path = refactor_dir / "deduplicated.json"
    if findings_files:
        deduplicate_findings(findings_files, output_path)
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deduplicate refactor findings")
    parser.add_argument("artifacts_dir", type=Path, help="Base .artifacts directory")
    parser.add_argument("target_name", help="Target identifier (e.g. yt-is)")
    args = parser.parse_args()
    result = deduplicate_and_save(args.artifacts_dir, args.target_name)
    print(f"Deduplicated: {result}")
