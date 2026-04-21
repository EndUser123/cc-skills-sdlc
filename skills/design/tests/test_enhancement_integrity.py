"""Cross-reference integrity tests for design-enhancements.md and SKILL.md pointers.

Verifies that:
1. SKILL.md section pointers match actual sections in design-enhancements.md
2. Template formats are structurally valid (weights, fields, thresholds)
3. FRAGILE-RANK threshold is consistent across both files
4. No stale /arch references remain in reference files
5. All 12 enhancement sections exist
6. Enhancement stage labels use consistent naming
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
ENHANCEMENTS_MD = SKILL_DIR / "references" / "design-enhancements.md"


@pytest.fixture(scope="module")
def skill_content() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def enhancements_content() -> str:
    return ENHANCEMENTS_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def enhancement_sections(enhancements_content: str) -> dict[int, str]:
    """Parse enhancement sections by number."""
    sections: dict[int, str] = {}
    pattern = re.compile(r"^## (\d+)\. ", re.MULTILINE)
    matches = list(pattern.finditer(enhancements_content))
    for i, match in enumerate(matches):
        section_num = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(enhancements_content)
        sections[section_num] = enhancements_content[start:end]
    return sections


class TestSectionPointers:
    """SKILL.md pointers must reference existing enhancement sections."""

    POINTER_PATTERN = re.compile(
        r"`?references/design-enhancements\.md`?\s+Sections?\s+([\d, ]+and\s+[\d]+|[\d, ]+)"
    )

    def test_all_pointers_reference_valid_sections(
        self, skill_content: str, enhancement_sections: dict[int, str]
    ) -> None:
        pointers = self.POINTER_PATTERN.findall(skill_content)
        assert pointers, "No enhancement section pointers found in SKILL.md"

        for pointer_text in pointers:
            nums = [int(n) for n in re.findall(r"\d+", pointer_text)]
            for num in nums:
                assert num in enhancement_sections, (
                    f"SKILL.md references Section {num} but no such section exists "
                    f"in design-enhancements.md"
                )

    def test_all_12_sections_exist(self, enhancement_sections: dict[int, str]) -> None:
        for i in range(1, 13):
            assert i in enhancement_sections, (
                f"Section {i} missing from design-enhancements.md"
            )

    def test_no_orphaned_sections(
        self, skill_content: str, enhancement_sections: dict[int, str]
    ) -> None:
        referenced: set[int] = set()
        pointers = self.POINTER_PATTERN.findall(skill_content)
        for pointer_text in pointers:
            referenced.update(int(n) for n in re.findall(r"\d+", pointer_text))

        for section_num in enhancement_sections:
            assert section_num in referenced, (
                f"Section {section_num} exists in design-enhancements.md "
                f"but is never referenced from SKILL.md"
            )


class TestDecisionMatrixFormat:
    """Decision matrix template must have valid weights and scoring."""

    def test_weights_sum_to_1(self, enhancement_sections: dict[int, str]) -> None:
        section = enhancement_sections.get(2, "")
        assert section, "Section 2 (Weighted Decision Matrix) missing"

        # Extract weights from criterion column: values in (0.XX) format in first column
        weights: list[float] = []
        for line in section.split("\n"):
            if not line.startswith("|"):
                continue
            # First column only: between first | and second |
            cells = line.split("|")
            if len(cells) < 3:
                continue
            first_cell = cells[1]
            match = re.search(r"\(0\.\d+\)", first_cell)
            if match:
                weights.append(float(match.group()[1:-1]))

        assert len(weights) >= 4, f"Found only {len(weights)} weights, expected >= 4"
        total = sum(weights[:5])
        assert abs(total - 1.0) < 0.05, (
            f"Decision matrix weights sum to {total:.2f}, expected ~1.0"
        )

    def test_scores_in_valid_range(self, enhancement_sections: dict[int, str]) -> None:
        section = enhancement_sections.get(2, "")
        scores: list[int] = []
        for match in re.finditer(r"\|\s*(\d{1,2})\s*\(", section):
            scores.append(int(match.group(1)))

        for score in scores:
            assert 1 <= score <= 10, f"Score {score} outside valid range 1-10"


class TestATAMTemplate:
    """ATAM quality attribute scenario template must have all 5 fields."""

    REQUIRED_FIELDS = ["Stimulus", "Source", "Environment", "Response", "Response Measure"]

    def test_template_has_all_fields(self, enhancement_sections: dict[int, str]) -> None:
        section = enhancement_sections.get(1, "")
        assert section, "Section 1 (Quality Attribute Scenarios) missing"

        for field in self.REQUIRED_FIELDS:
            assert field in section, (
                f"ATAM template missing required field: {field}"
            )

    def test_example_scenario_is_complete(self, enhancement_sections: dict[int, str]) -> None:
        section = enhancement_sections.get(1, "")
        example_match = re.search(r"Example:(.+?)(?=---|\Z)", section, re.DOTALL)
        if not example_match:
            pytest.skip("No ATAM example found")

        example = example_match.group(1)
        for field in self.REQUIRED_FIELDS:
            assert field in example, f"ATAM example missing field: {field}"


class TestFragileRankConsistency:
    """FRAGILE-RANK threshold must be consistent between SKILL.md and enhancements."""

    def test_threshold_consistent(self, skill_content: str, enhancements_content: str) -> None:
        skill_matches = re.findall(r"delta\s*<\s*([\d.]+)", skill_content)
        enhancement_matches = re.findall(r"within\s*([\d.]+)\s*points", enhancements_content)

        skill_thresholds = set(float(m) for m in skill_matches)
        enhancement_thresholds = set(float(m) for m in enhancement_matches)

        if skill_thresholds and enhancement_thresholds:
            all_thresholds = skill_thresholds | enhancement_thresholds
            assert len(all_thresholds) == 1, (
                f"FRAGILE-RANK thresholds inconsistent: "
                f"SKILL.md={skill_thresholds}, enhancements={enhancement_thresholds}"
            )


class TestStaleReferences:
    """No deprecated command names or stale versions in reference files."""

    def test_no_arch_references_in_enhancements(self, enhancements_content: str) -> None:
        assert "/arch" not in enhancements_content, (
            "Found deprecated /arch reference in design-enhancements.md"
        )

    def test_no_arch_references_in_adr_doc(self) -> None:
        adr_doc = SKILL_DIR / "references" / "adr-and-enhancements.md"
        if not adr_doc.exists():
            pytest.skip("adr-and-enhancements.md not found")
        content = adr_doc.read_text(encoding="utf-8")
        assert "/arch" not in content, (
            "Found deprecated /arch reference in adr-and-enhancements.md"
        )

    def test_enhancement_version_matches_skill(
        self, skill_content: str, enhancements_content: str
    ) -> None:
        skill_version = re.search(r'version:\s*"([\d.]+)"', skill_content)
        enh_version = re.search(r"Design Enhancements \(v([\d.]+)\)", enhancements_content)

        if skill_version and enh_version:
            assert skill_version.group(1) == enh_version.group(1), (
                f"Version mismatch: SKILL.md={skill_version.group(1)}, "
                f"design-enhancements.md={enh_version.group(1)}"
            )


class TestStageLabelConsistency:
    """Enhancement stage labels should use SKILL.md stage numbering."""

    def test_stage_labels_use_numbered_format(self, enhancement_sections: dict[int, str]) -> None:
        vague_patterns = [
            (1, "After precedent analysis, before ADR drafting"),
            (9, "Precedent analysis (Stage"),
        ]
        for section_num, vague_text in vague_patterns:
            if section_num in enhancement_sections:
                assert vague_text not in enhancement_sections[section_num], (
                    f"Section {section_num} uses vague stage label "
                    f"instead of numbered format"
                )

    def test_section_7_references_claim_verification_gate(
        self, enhancement_sections: dict[int, str]
    ) -> None:
        section = enhancement_sections.get(7, "")
        assert section, "Section 7 (RICE/MoSCoW) missing"
        assert "0.4" in section or "0.3" in section, (
            "Section 7 should reference a valid stage number (0.3 or 0.4)"
        )


class TestAntiPatternChecklist:
    """Anti-pattern checklist must have all 10 entries with severity levels."""

    EXPECTED_PATTERNS = [
        "God Object",
        "Distributed Monolith",
        "Premature Optimization",
        "Resume-Driven Architecture",
        "Golden Hammer",
        "Leaky Abstraction",
        "Circular Dependencies",
        "Big Ball of Mud",
        "Sunk Cost Fallacy",
        "Analysis Paralysis",
    ]

    def test_all_anti_patterns_present(self, enhancement_sections: dict[int, str]) -> None:
        section = enhancement_sections.get(6, "")
        assert section, "Section 6 (Anti-Pattern Checklist) missing"

        for pattern in self.EXPECTED_PATTERNS:
            assert pattern in section, f"Anti-pattern '{pattern}' missing from checklist"

    def test_all_have_severity(self, enhancement_sections: dict[int, str]) -> None:
        section = enhancement_sections.get(6, "")
        high_count = section.count("High")
        medium_count = section.count("Medium")
        low_count = section.count("Low")

        assert high_count + medium_count + low_count >= 10, (
            f"Anti-pattern checklist has {high_count + medium_count + low_count} "
            f"severity labels, expected >= 10"
        )
