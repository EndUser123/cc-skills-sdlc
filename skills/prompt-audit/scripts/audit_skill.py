#!/usr/bin/env python3
"""Audit a target skill against the prompt-patterns-catalog.

Produces prompt-audit_{skill}_{run_id}.json with P1-P8 coverage verdicts.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any

CATALOG_PATH = os.environ.get(
    "CATALOG", "P:/packages/cc-skills-sdlc/prompt-patterns-catalog.md"
)
SKILLS_ROOT = os.environ.get(
    "SKILLS_ROOT", "P:/packages/cc-skills-sdlc/skills"
)
STATE_DIR = pathlib.Path(os.environ.get(
    "GO_STATE_DIR", ".claude/.artifacts/{}/prompt-audit"
).format(os.environ.get("TERMINAL_ID", "unknown")))


def audit_skill(target: str) -> dict[str, Any]:
    skill_dir = pathlib.Path(SKILLS_ROOT) / target
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"Skill '{target}' not found in {SKILLS_ROOT}")

    state_dir = pathlib.Path(os.environ.get(
        "GO_STATE_DIR",
        f".claude/.artifacts/{os.environ.get('TERMINAL_ID','unknown')}/prompt-audit"
    ))
    state_dir.mkdir(parents=True, exist_ok=True)

    run_id = os.environ.get("RUN_ID", "audit")

    skill_md = skill_dir / "SKILL.md"
    scripts_dir = skill_dir / "scripts"

    # Read SKILL.md
    skill_md_text = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""

    # Read all scripts
    script_contents: dict[str, str] = {}
    if scripts_dir.is_dir():
        for py_file in scripts_dir.glob("*.py"):
            script_contents[py_file.name] = py_file.read_text(encoding="utf-8")

    patterns: dict[str, dict[str, Any]] = {}

    patterns["P1"] = _check_p1(script_contents)
    patterns["P2"] = _check_p2(script_contents, skill_md_text)
    patterns["P3"] = _check_p3(script_contents, skill_md_text)
    patterns["P4"] = _check_p4(script_contents, skill_md_text)
    patterns["P5"] = _check_p5(script_contents, skill_md_text)
    patterns["P6"] = _check_p6(skill_md_text)
    patterns["P7"] = _check_p7(script_contents)
    patterns["P8"] = _check_p8(skill_md_text)

    result = {
        "audit_run_id": run_id,
        "target_skill": target,
        "catalog_path": str(CATALOG_PATH),
        "patterns": patterns,
    }

    out_path = state_dir / f"prompt-audit_{target}_{run_id}.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Audit written to {out_path}")

    _print_summary(target, patterns)
    return result


# ─── P1: [FACT]/[INFERENCE]/[RECOMMENDATION] ──────────────────────────────────

def _check_p1(scripts: dict[str, str]) -> dict[str, Any]:
    """Check for P1: structured evidence blocks in script output."""
    found_in: list[str] = []
    for name, text in scripts.items():
        if "[FACT]" in text or "[FACT]" in text:
            found_in.append(name)

    # Also check verify-task.py specifically
    if "verify-task.py" in scripts:
        text = scripts["verify-task.py"]
        has_fact = "[FACT]" in text
        has_inference = "[INFERENCE]" in text
        has_recommendation = "[RECOMMENDATION]" in text
        if has_fact and has_inference and has_recommendation:
            return _verdict("PRESENT", "verify-task.py", "evidence blocks present")
        if has_fact and has_inference:
            return _verdict("PARTIAL", "verify-task.py", "only [FACT]/[INFERENCE] present")
        if has_fact:
            return _verdict("PARTIAL", "verify-task.py", "only [FACT] present")

    if found_in:
        return _verdict("PARTIAL", found_in[0], "evidence tag found but incomplete format")
    return _verdict("MISSING", None, "no [FACT]/[INFERENCE] blocks found")


# ─── P2: Adversarial Break-Case Enumeration ───────────────────────────────────

def _check_p2(scripts: dict[str, str], md_text: str) -> dict[str, Any]:
    """Check for P2: 5 adversarial break cases in scope pass."""
    CASES = [
        "pure-plan-only", "fake-plan-analytical",
        "marker-camouflage", "rationalale-camouflage",
        "minimal-malformed-plan",
    ]
    found_cases: list[str] = []
    for name, text in scripts.items():
        for case in CASES:
            if case in text:
                found_cases.append(case)

    if len(found_cases) == 5:
        return _verdict("PRESENT", "review-passes.py", "all 5 break cases present")
    if len(found_cases) >= 2:
        return _verdict("PARTIAL", "review-passes.py", f"only {found_cases} cases present")
    return _verdict("MISSING", None, "no adversarial break-case check found")


# ─── P3: Gap → Opportunity 6-Dimension Scan ────────────────────────────────────

def _check_p3(scripts: dict[str, str], md_text: str) -> dict[str, Any]:
    """Check for P3: scope drift / gap detection before verification."""
    found_in: list[str] = []
    for name, text in scripts.items():
        if "scope_drift" in text or "scope_in" in text or "_check_scope" in text:
            found_in.append(name)

    gap_keywords = [
        "hook lifecycle", "user experience", "learning & adaptation",
        "safety & policy", "composability", "framework & tooling",
    ]
    gap_scan_in_md = sum(1 for kw in gap_keywords if kw.lower() in md_text.lower())

    if found_in and gap_scan_in_md >= 3:
        return _verdict("PRESENT", found_in[0], "scope drift check + 6-dim scan in MD")
    if found_in:
        return _verdict("PARTIAL", found_in[0], "scope drift check exists, no 6-dim scan")
    return _verdict("MISSING", None, "no gap or scope drift detection found")


# ─── P4: Evidence Requirement Framing ─────────────────────────────────────────

def _check_p4(scripts: dict[str, str], md_text: str) -> dict[str, Any]:
    """Check for P4: file path + line number required per finding."""
    evidence_keywords = ["file path", "line number", "cite", "evidence", "where:"]
    md_has_evidence = sum(1 for kw in evidence_keywords if kw.lower() in md_text.lower())

    # Check if review-passes.py has structured findings format
    has_findings_format = False
    for name, text in scripts.items():
        if "review-pass" in name and "## Findings" in text:
            has_findings_format = True

    if md_has_evidence >= 2 and has_findings_format:
        return _verdict("PRESENT", "SKILL.md + review-passes.py", "evidence framing found")
    if md_has_evidence >= 1 or has_findings_format:
        return _verdict("PARTIAL", "SKILL.md" if md_has_evidence else "review-passes.py",
                        "partial evidence framing")
    return _verdict("MISSING", None, "no evidence requirement framing found")


# ─── P5: Forensic ADR Review Matrix ────────────────────────────────────────────

def _check_p5(scripts: dict[str, str], md_text: str) -> dict[str, Any]:
    """Check for P5: ADR-vs-reality matrix in PR artifacts or review passes."""
    matrix_keywords = ["matrix", "adr", "forensic", "implementation.*diff",
                      "design element", "adr intent"]
    script_has_matrix = any(
        any(kw.lower() in text.lower() for kw in matrix_keywords)
        for text in scripts.values()
    )
    md_has_matrix = any(kw.lower() in md_text.lower() for kw in matrix_keywords)

    if script_has_matrix or md_has_matrix:
        return _verdict("PRESENT", "pr-artifacts.py or SKILL.md",
                        "ADR matrix referenced")
    return _verdict("MISSING", None, "no forensic ADR matrix found")


# ─── P6: Success Criteria Checklist ───────────────────────────────────────────

def _check_p6(md_text: str) -> dict[str, Any]:
    """Check for P6: numbered must-do list with failure conditions."""
    checklist_signals = [
        "success criteria", "must do", "before asking", "failure condition",
        "numbered", "checklist",
    ]
    found_signals = [s for s in checklist_signals if s.lower() in md_text.lower()]
    has_numbered = bool("1." in md_text or "1)" in md_text)

    if len(found_signals) >= 2 and has_numbered:
        return _verdict("PRESENT", "SKILL.md", "numbered success criteria found")
    if found_signals:
        return _verdict("PARTIAL", "SKILL.md", f"checklist signals: {found_signals}")
    return _verdict("MISSING", None, "no explicit success criteria checklist found")


# ─── P7: Root Cause Tracing F1–Fn ─────────────────────────────────────────────

def _check_p7(scripts: dict[str, str]) -> dict[str, Any]:
    """Check for P7: F1/F2 numbering + causal inference chain in output."""
    rca_signals = ["F1", "F2", "F3", "root cause", "causal", "RCA"]
    found_in: list[str] = []
    for name, text in scripts.items():
        for signal in rca_signals:
            if signal in text:
                found_in.append(f"{name}: {signal}")

    if len(found_in) >= 3:
        return _verdict("PRESENT", found_in[0], f"multiple RCA signals: {found_in}")
    if found_in:
        return _verdict("PARTIAL", found_in[0], "RCA signals present but not fully structured")
    return _verdict("MISSING", None, "no F1/Fn root cause tracing found")


# ─── P8: External LLM Judge ────────────────────────────────────────────────────

def _check_p8(md_text: str) -> dict[str, Any]:
    """Check for P8: external judge subagent with 5-axis JSON output."""
    judge_signals = [
        "external judge", "external review", "review subagent",
        "5-axis", "verdict.*json", "severity.*critical",
    ]
    found = [s for s in judge_signals if s.lower() in md_text.lower()]

    if len(found) >= 2:
        return _verdict("PRESENT", "SKILL.md", f"external judge references: {found}")
    if found:
        return _verdict("PARTIAL", "SKILL.md", f"partial judge reference: {found}")
    return _verdict("MISSING", None, "no external judge subagent found")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _verdict(status: str, file: str | None, note: str) -> dict[str, Any]:
    return {"status": status, "file": file, "note": note}


def _print_summary(target: str, patterns: dict[str, dict[str, Any]]) -> None:
    print(f"\n# /prompt-audit — {target}")
    print("\nPattern Coverage:")
    for p_id, result in patterns.items():
        status = result["status"]
        file = result["file"] or ""
        note = result["note"]
        print(f"  {p_id}  {'PRESENT  ' if status=='PRESENT' else 'PARTIAL  ' if status=='PARTIAL' else 'MISSING   '}  {file}")
        if note:
            print(f"        {note}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python audit_skill.py <target_skill>", file=sys.stderr)
        sys.exit(1)

    target = sys.argv[1]
    try:
        audit_skill(target)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()