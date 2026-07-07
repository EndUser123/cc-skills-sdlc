"""Complexity scanning using radon — cyclomatic complexity analysis.

Scans Python files for high-complexity functions and methods, returning
findings in the same format as code_scanner.py for unified deduplication.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from radon.complexity import cc_visit
from radon.visitors import Class

logger = logging.getLogger(__name__)


# CC risk mapping (CC value -> (risk_score, rollback_complexity, severity))
_CC_RISK_MAP = [
    (5, 1, "low", "low"),      # CC 1-5: low complexity
    (10, 2, "medium", "medium"),  # CC 6-10: medium complexity
    (20, 3, "medium", "medium"),  # CC 11-20: high complexity
    (float("inf"), 4, "high", "high"),  # CC 21+: very high complexity
]


def _cc_to_risk(cc: int) -> tuple[int, str, str]:
    """Map cyclomatic complexity to risk metadata."""
    for threshold, risk_score, rollback, severity in _CC_RISK_MAP:
        if cc <= threshold:
            return risk_score, rollback, severity
    return 4, "high", "high"


def scan_complexity(
    file_paths: list[str | Path],
    min_cc: int = 5,
) -> list[dict[str, Any]]:
    """Scan Python files for high-cyclomatic-complexity functions.

    Args:
        file_paths: List of Python file paths to scan.
        min_cc: Minimum cyclomatic complexity to report (default 5).
                Functions with CC below this threshold are ignored.

    Returns:
        List of complexity findings, each containing:
            - type: "HIGH_CC"
            - file_path: Path to the file
            - line_number: Line where function is defined
            - description: "CC=N function_name (method of ClassName)"
            - complexity: The cyclomatic complexity value
            - risk_score: 1-4 scale
            - rollback_complexity: "low" | "medium" | "high"
            - state_impact: "low" (CC alone doesn't affect runtime state)
            - severity: "low" | "medium" | "high"
            - finding_type: "complexity"

    Example:
        >>> findings = scan_complexity(["example.py"], min_cc=10)
        >>> for f in findings:
        ...     print(f"{f['description']} CC={f['complexity']}")
    """
    findings = []

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            logger.debug(f"Skipping non-existent file: {file_path}")
            continue

        if not str(file_path).endswith(".py"):
            logger.debug(f"Skipping non-Python file: {file_path}")
            continue

        try:
            source = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            continue

        try:
            blocks = cc_visit(source)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            continue

        for block in blocks:
            # Skip Class blocks — they aggregate method CCs, not refactorable units
            if isinstance(block, Class):
                continue
            cc = block.complexity
            if cc < min_cc:
                continue

            risk_score, rollback_complexity, severity = _cc_to_risk(cc)

            # Format description
            classname = getattr(block, "classname", None)
            func_name = getattr(block, "name", None)
            if classname:
                func_desc = f"method {func_name} of class {classname}"
            else:
                func_desc = f"function {func_name}"

            finding = {
                "type": "HIGH_CC",
                "file_path": str(path),
                "line_number": block.lineno,
                "description": f"CC={cc} {func_desc}",
                "complexity": cc,
                "risk_score": risk_score,
                "rollback_complexity": rollback_complexity,
                "state_impact": "low",
                "severity": severity,
                "finding_type": "complexity",
            }
            findings.append(finding)
            logger.debug(
                f"High-CC finding: {path}:{block.lineno} {func_desc} CC={cc} "
                f"(risk={risk_score}, severity={severity})"
            )

    return findings




# ----------------------------------------------------------------------------
# Churn x complexity hotspot ranking (Gap 1)
# ----------------------------------------------------------------------------
# Rank files by a rank-product of cyclomatic complexity and git churn (commit
# frequency over a window) to surface refactoring hotspots. Churn is collected
# per-repo via `git -C <repo>` so files inside gitlink-without-.gitmodules
# embedded repos (submodules) are scored against their OWN history, not the
# parent's (which returns gitlink pointers, not file commits).


def _git_root(path: Path) -> Path | None:
    """Nearest ancestor of ``path`` containing a ``.git`` entry (dir or file).

    For a file inside an embedded/submodule repo this returns THAT repo's
    root, not the parent's.
    """
    p = path.resolve()
    if p.is_file():
        p = p.parent
    while True:
        if (p / ".git").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent


_VENDORED_SEGMENTS = frozenset(
    {"site-packages", "node_modules", "__pycache__", ".venv", "venv", "vendor"}
)


def _is_vendored(path: Path) -> bool:
    """True if ``path`` runs through a vendored/dependency tree."""
    return any(part in _VENDORED_SEGMENTS for part in path.parts)


def _file_churn(path: Path, since_expr: str) -> int:
    """Commit count touching ``path`` since ``since_expr`` (git rev-list --count).

    Per-repo via ``git -C <root>``. Returns 0 if outside any repo or git fails.
    """
    root = _git_root(path)
    if root is None:
        return 0
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return 0
    result = subprocess.run(
        ["git", "-C", str(root), "rev-list", "--count",
         f"--since={since_expr}", "HEAD", "--", str(rel)],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0
    out = result.stdout.strip()
    return int(out) if out.isdigit() else 0


def _max_cc(path: Path, min_cc: int) -> int:
    """Highest cyclomatic complexity among non-Class blocks in ``path`` (0 if none)."""
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return 0
    try:
        blocks = cc_visit(source)
    except Exception:
        return 0
    return max(
        (b.complexity for b in blocks
         if not isinstance(b, Class) and b.complexity >= min_cc),
        default=0,
    )


def rank_hotspots(
    file_paths: list[str | Path],
    since_days: int = 90,
    min_churn: int = 1,
    min_cc: int = 5,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Rank files by churn x complexity (rank-product) to surface hotspots.

    For each file: complexity = max cyclomatic complexity of its functions
    (>= ``min_cc``); churn = commits in the last ``since_days`` touching it
    (per-repo ``git -C``). Files below ``min_cc``/``min_churn`` or in vendored
    paths are skipped. Lower ``hotspot_score`` (rank-product) = higher priority.

    Returns up to ``top_n`` dicts: {file_path, max_cc, churn, complexity_rank,
    churn_rank, hotspot_score}.
    """
    since_expr = f"{since_days} days ago"
    rows: list[dict[str, Any]] = []
    for fp in file_paths:
        path = Path(fp)
        if not path.exists() or not str(fp).endswith(".py"):
            continue
        if _is_vendored(path):
            continue
        cc = _max_cc(path, min_cc)
        if cc < min_cc:
            continue
        churn = _file_churn(path, since_expr)
        if churn < min_churn:
            continue
        rows.append({"file_path": str(path), "max_cc": cc, "churn": churn})
    if not rows:
        return []
    cc_rank = {id(r): i for i, r in enumerate(sorted(rows, key=lambda r: -r["max_cc"]), 1)}
    ch_rank = {id(r): i for i, r in enumerate(sorted(rows, key=lambda r: -r["churn"]), 1)}
    for r in rows:
        r["complexity_rank"] = cc_rank[id(r)]
        r["churn_rank"] = ch_rank[id(r)]
        r["hotspot_score"] = cc_rank[id(r)] * ch_rank[id(r)]
    rows.sort(key=lambda r: r["hotspot_score"])
    return rows[:top_n]


# CLI for testing
if __name__ == "__main__":
    import argparse, json, sys

    parser = argparse.ArgumentParser(description="Scan for cyclomatic complexity")
    parser.add_argument("files", nargs="+", help="Python files to scan")
    parser.add_argument("--min-cc", type=int, default=5, help="Minimum CC to report")
    parser.add_argument(
        "--churn", action="store_true",
        help="Rank files by churn x complexity (hotspots) instead of listing HIGH_CC findings",
    )
    parser.add_argument("--since", type=int, default=90, help="Churn window in days (default 90)")
    parser.add_argument("--top", type=int, default=10, help="Top-N hotspots to report (default 10)")
    args = parser.parse_args()

    if args.churn:
        hotspots = rank_hotspots(
            args.files, since_days=args.since, min_cc=args.min_cc, top_n=args.top
        )
        print(json.dumps(hotspots, indent=2))
        print(f"\n{len(hotspots)} hotspots (churn x complexity, last {args.since}d)", file=sys.stderr)
    else:
        findings = scan_complexity(args.files, min_cc=args.min_cc)
        print(json.dumps(findings, indent=2))
        print(f"\n{len(findings)} findings above CC={args.min_cc}", file=sys.stderr)
