#!/usr/bin/env python3
"""Regression tests for the RCA investigation report template."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "investigation_report.md"
OUTPUT_FORMAT = ROOT / "references" / "output-format.md"
SKILL = ROOT / "SKILL.md"

REQUIRED_SECTIONS = [
    "Observable Definition",
    "Evidence Buckets",
    "Executed Path",
    "Competing Hypothesis",
    "Falsifier",
    "First Divergence",
    "RCA Think Pass",
    "Root Cause",
    "Verification",
]


def _assert_sections_present(text: str, source: Path) -> None:
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    assert not missing, f"{source} is missing required RCA sections: {missing}"


def test_investigation_report_template_is_strict() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    _assert_sections_present(text, TEMPLATE)
    assert "do not name a root cause yet" in text.lower()
    assert "smallest discriminating check" in text.lower()


def test_output_format_template_is_strict() -> None:
    text = OUTPUT_FORMAT.read_text(encoding="utf-8")
    _assert_sections_present(text, OUTPUT_FORMAT)
    assert "anti-lazy conclusion rule" in text.lower()
    assert "rca think pass" in text.lower()


def test_skill_doc_mentions_anti_lazy_rule() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "anti-lazy rule" in text
    assert "executed path" in text
    assert "falsifier" in text
    assert "rca think pass" in text
