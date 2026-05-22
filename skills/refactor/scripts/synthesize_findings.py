"""Synthesize findings from specialist agents into consolidated report with Health Score.

This module implements the synthesis phase that consolidates findings from
the 5-agent discovery phase and calculates a Health Score for the codebase.

Health Score formula: 100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)
Score is capped at 0-100 range.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def calculate_health_score(findings: List[Dict[str, Any]]) -> int:
    """Calculate code health score from findings.

    Args:
        findings: List of finding dictionaries with 'severity' field

    Returns:
        Health score from 0-100, where higher is better

    Examples:
        >>> calculate_health_score([
        ...     {'severity': 'CRITICAL'},
        ...     {'severity': 'HIGH'},
        ... ])
        70
        >>> calculate_health_score([])
        100
    """
    critical = sum(1 for f in findings if f.get('severity') == 'CRITICAL')
    high = sum(1 for f in findings if f.get('severity') == 'HIGH')
    medium = sum(1 for f in findings if f.get('severity') == 'MEDIUM')
    low = sum(1 for f in findings if f.get('severity') == 'LOW')

    score = 100 - (critical * 20 + high * 10 + medium * 5 + low * 2)
    return max(0, min(100, score))


def load_agent_findings(findings_dir: Path) -> List[Dict[str, Any]]:
    """Load and combine findings from all agent output files.

    Args:
        findings_dir: Directory containing findings-*.json files

    Returns:
        Consolidated list of all findings from all agents
    """
    findings = []
    for findings_file in findings_dir.glob("findings-*.json"):
        try:
            agent_findings = json.loads(findings_file.read_text())
            if isinstance(agent_findings, list):
                findings.extend(agent_findings)
        except (json.JSONDecodeError, IOError) as e:
            # Log but continue - partial findings better than none
            print(f"Warning: Failed to load {findings_file}: {e}")
    return findings


def deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate findings based on file, line, and description.

    Args:
        findings: List of findings to deduplicate

    Returns:
        Deduplicated list of findings
    """
    seen = set()
    deduplicated = []

    for finding in findings:
        # Create a unique key from file, line, and description
        file_path = finding.get('file', '')
        line = finding.get('line', 0)
        description = finding.get('description', '')

        key = (file_path, line, description[:100])  # Truncate description for key
        if key not in seen:
            seen.add(key)
            deduplicated.append(finding)

    return deduplicated


def group_by_severity(findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group findings by severity level.

    Args:
        findings: List of findings to group

    Returns:
        Dictionary with severity levels as keys and finding lists as values
    """
    grouped = {
        'CRITICAL': [],
        'HIGH': [],
        'MEDIUM': [],
        'LOW': [],
    }

    for finding in findings:
        severity = finding.get('severity', 'LOW')
        if severity in grouped:
            grouped[severity].append(finding)

    return grouped


def synthesize_report(
    findings: List[Dict[str, Any]],
    target: str,
    session_id: str
) -> Dict[str, Any]:
    """Generate synthesis report with Health Score and severity counts.

    Args:
        findings: List of deduplicated findings
        target: Target path or file being analyzed
        session_id: Session identifier

    Returns:
        Synthesis report dictionary with health score and grouped findings
    """
    health_score = calculate_health_score(findings)
    by_severity = group_by_severity(findings)

    return {
        'target': target,
        'session_id': session_id,
        'health_score': health_score,
        'severity_counts': {
            'CRITICAL': len(by_severity['CRITICAL']),
            'HIGH': len(by_severity['HIGH']),
            'MEDIUM': len(by_severity['MEDIUM']),
            'LOW': len(by_severity['LOW']),
        },
        'total_findings': len(findings),
        'findings_by_severity': by_severity,
    }


def write_synthesis_report(
    synthesis: Dict[str, Any],
    output_path: Path
) -> None:
    """Write synthesis report to file.

    Args:
        synthesis: Synthesis report dictionary
        output_path: Path to write the report
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(synthesis, indent=2))


def format_synthesis_for_display(synthesis: Dict[str, Any]) -> str:
    """Format synthesis report for human-readable display.

    Args:
        synthesis: Synthesis report dictionary

    Returns:
        Formatted markdown string
    """
    health_score = synthesis['health_score']
    counts = synthesis['severity_counts']

    # Determine health interpretation
    if health_score >= 80:
        interpretation = "Healthy — Low risk, minor improvements possible"
    elif health_score >= 50:
        interpretation = "Warning — Significant issues, address HIGH items first"
    else:
        interpretation = "Critical — Systemic problems, do not deploy without fixes"

    output = [
        f"## Synthesis Report",
        f"",
        f"**Target:** {synthesis['target']}",
        f"**Session:** {synthesis['session_id']}",
        f"",
        f"## Health Score: {health_score}% ({interpretation})",
        f"",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| CRITICAL | {counts['CRITICAL']} |",
        f"| HIGH | {counts['HIGH']} |",
        f"| MEDIUM | {counts['MEDIUM']} |",
        f"| LOW | {counts['LOW']} |",
        f"",
        f"**Total findings:** {synthesis['total_findings']}",
    ]

    return "\n".join(output)


def main(findings_dir: str, output_path: str, target: str, session_id: str) -> None:
    """Main synthesis workflow.

    Args:
        findings_dir: Directory containing agent findings
        output_path: Path to write synthesis report
        target: Target being analyzed
        session_id: Session identifier
    """
    findings_path = Path(findings_dir)

    # Load and consolidate findings
    findings = load_agent_findings(findings_path)

    # Deduplicate
    findings = deduplicate_findings(findings)

    # Generate synthesis report
    synthesis = synthesize_report(findings, target, session_id)

    # Write to file
    write_synthesis_report(synthesis, Path(output_path))

    # Display summary
    print(format_synthesis_for_display(synthesis))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 5:
        print("Usage: synthesize_findings.py <findings_dir> <output_path> <target> <session_id>")
        sys.exit(1)

    main(
        findings_dir=sys.argv[1],
        output_path=sys.argv[2],
        target=sys.argv[3],
        session_id=sys.argv[4],
    )
