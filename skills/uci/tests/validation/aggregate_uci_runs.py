#!/usr/bin/env python3
"""
Aggregate existing agent outputs into consolidated /uci run logs.

This script scans .claude/state/ for individual agent output files
and groups them into consolidated uci_run_*.json files for analysis.
"""

import json
import re
from collections import defaultdict
from pathlib import Path


def extract_timestamp(filename: str) -> str | None:
    """Extract timestamp from agent output filename."""
    # Pattern: adversarial-{agent}-{timestamp}.json
    # Example: adversarial-critic-20260316-143001.json
    match = re.search(r"(\d{8})-(\d{6})", filename)
    if match:
        date_part, time_part = match.groups()
        return f"{date_part}T{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
    return None


def get_agent_name(filename: str) -> str:
    """Extract agent name from filename."""
    # Pattern: adversarial-{agent}-{timestamp}.json
    # Example: adversarial-compliance-20260310-150928.json
    # Note: No separator between agent name and timestamp
    match = re.match(r"adversarial-([^-]+)-?\d{8}", filename)
    if match:
        agent = match.group(1)
        # Map to standard agent names
        agent_map = {
            "critic": "adversarial-critic",
            "logic": "adversarial-logic",
            "testing": "adversarial-testing",
            "security": "adversarial-security",
            "performance": "adversarial-performance",
            "quality": "adversarial-quality",
            "compliance": "adversarial-compliance",
            "qa": "adversarial-qa",
            "rca": "adversarial-rca",
            "review": "adversarial-review",
        }
        return agent_map.get(agent, f"adversarial-{agent}")
    return "unknown"


def load_agent_output(filepath: Path) -> dict:
    """Load agent output from JSON file."""
    try:
        with open(filepath) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def extract_findings(agent_output: dict, agent_name: str) -> list[dict]:
    """Extract findings from agent output."""
    findings = []

    # Handle different output formats
    # First check for meta_analysis wrapper
    if "meta_analysis" in agent_output and "consensus_findings" in agent_output["meta_analysis"]:
        # Adversarial critic meta-analysis format
        for cf in agent_output["meta_analysis"]["consensus_findings"]:
            findings.append(
                {
                    "id": f"{agent_name.upper()}-{len(findings)}",
                    "category": cf.get("category", "general"),
                    "severity": map_severity(cf.get("confidence", "medium")),
                    "problem": cf.get("description", ""),
                    "confidence": cf.get("confidence", "medium"),
                    "supporting_agents": cf.get("supporting_agents", []),
                    "source_agent": agent_name,
                }
            )
    elif "consensus_findings" in agent_output:
        # Direct consensus_findings (no meta_analysis wrapper)
        for cf in agent_output["consensus_findings"]:
            findings.append(
                {
                    "id": f"{agent_name.upper()}-{len(findings)}",
                    "category": cf.get("category", "general"),
                    "severity": map_severity(cf.get("confidence", "medium")),
                    "problem": cf.get("description", ""),
                    "confidence": cf.get("confidence", "medium"),
                    "supporting_agents": cf.get("supporting_agents", []),
                    "source_agent": agent_name,
                }
            )
    elif "findings" in agent_output:
        # Standard findings format
        for i, f in enumerate(agent_output["findings"]):
            findings.append(
                {
                    "id": f"{agent_name.upper()}-{i}",
                    "category": f.get("category", "general"),
                    "severity": f.get("severity", "medium"),
                    "problem": f.get("problem", f.get("description", "")),
                    "location": f.get("location", ""),
                    "recommendation": f.get("recommendation", ""),
                    "source_agent": agent_name,
                }
            )

    return findings


def map_severity(confidence: str) -> str:
    """Map confidence to severity."""
    mapping = {"high": "high", "medium": "medium", "low": "low"}
    return mapping.get(confidence.lower(), "medium")


def detect_mode_from_agents(agents: list[str]) -> str:
    """Detect /uci mode from agent list."""
    # Mode detection based on agent count and types
    agent_count = len(agents)
    if agent_count <= 3:
        return "triage"
    elif agent_count <= 6:
        return "standard"
    elif agent_count <= 9:
        return "deep"
    return "comprehensive"


def aggregate_runs(state_dir: Path, output_dir: Path) -> int:
    """
    Aggregate individual agent outputs into consolidated /uci runs.

    Args:
        state_dir: Path to .claude/state/ directory
        output_dir: Path to output directory for consolidated runs

    Returns:
        Number of aggregated runs created
    """
    # Group files by exact timestamp (not hour-based)
    runs_by_timestamp = defaultdict(lambda: {"timestamp": None, "agents": [], "findings": []})

    # Scan for agent output files
    for filepath in state_dir.glob("adversarial-*.json"):
        timestamp = extract_timestamp(filepath.name)
        if not timestamp:
            continue

        agent_name = get_agent_name(filepath.name)
        agent_output = load_agent_output(filepath)

        # Group by exact timestamp
        run_data = runs_by_timestamp[timestamp]
        run_data["timestamp"] = timestamp
        if agent_name not in run_data["agents"]:
            run_data["agents"].append(agent_name)

        # Extract findings
        findings = extract_findings(agent_output, agent_name)
        run_data["findings"].extend(findings)

    # Create consolidated run files
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_created = 0

    for timestamp, run_data in runs_by_timestamp.items():
        if not run_data["timestamp"]:
            continue

        mode = detect_mode_from_agents(run_data["agents"])

        uci_run = {
            "timestamp": run_data["timestamp"],
            "mode": mode,
            "agents": run_data["agents"],
            "findings": run_data["findings"],
            "total_findings": len(run_data["findings"]),
        }

        # Write to output file (sanitize timestamp for filename)
        safe_timestamp = timestamp.replace(":", "-")
        output_file = output_dir / f"uci_run_{safe_timestamp}.json"
        with open(output_file, "w") as f:
            json.dump(uci_run, f, indent=2)

        runs_created += 1

    return runs_created


def main():
    """Main entry point."""
    # Resolve paths relative to project root (P:\\\\\\)
    project_root = Path(__file__).resolve().parents[3]  # Go from tests/validation/ to project root
    state_dir = project_root / ".claude" / "state"
    output_dir = state_dir / "uci"

    print(f"Scanning {state_dir} for agent outputs...")
    runs_created = aggregate_runs(state_dir, output_dir)

    print(f"\nCreated {runs_created} consolidated /uci runs in {output_dir}")

    # List created files
    if runs_created > 0:
        print("\nConsolidated runs:")
        for f in sorted(output_dir.glob("uci_run_*.json")):
            print(f"  {f.name}")


if __name__ == "__main__":
    main()
