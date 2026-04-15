"""Skill-specific verification checklist.

Validates skill completeness:
- SKILL.md documentation exists
- Test directory exists with tests
- Skill registered in router
- Path integrity (referenced files exist)
"""

import re
from pathlib import Path
from typing import Any, Dict

from .base_checklist import VerificationChecklist


class SkillChecklist(VerificationChecklist):
    """Verification checklist for skill directories.

    Checks skill completeness indicators:
    1. SKILL.md exists
    2. Tests directory exists
    3. Skill registered in router
    4. Path integrity (referenced files exist)
    """

    # Default router path - can be overridden for testing
    ROUTER_PATH = "P:/.claude/skills/__init__.py"

    # Patterns to exempt from path validation
    EXEMPT_PATTERNS = [
        r"^https?://",  # URLs
        r"^~/",  # User home
        r"\$\{?\w+\}?",  # Environment variables
        r"your-[a-z-]+\.py",  # Placeholder examples
        r"example\.py",  # Example files
        r"<path>|<file>|PATH",  # Angle bracket placeholders
    ]

    def _extract_referenced_paths(self, skill_md_path: str) -> list[tuple[str, int]]:
        """Extract file paths referenced in SKILL.md.

        Returns list of (path, line_number) tuples.
        """
        paths = []
        content = self._read_file(skill_md_path)
        if not content:
            return paths

        # Pattern 1: Backtick paths like `path/to/file.py`
        pattern1 = r"`([a-zA-Z]:\\\.claude\\skills\\[^`]+\.py)`"
        for match in re.finditer(pattern1, content):
            path = match.group(1)
            line_num = content[: match.start()].count("\n") + 1
            paths.append((path, line_num))

        # Pattern 2: Forward-slash paths in code blocks
        pattern2 = r"(?:python|bash)\s+([a-z]/\.claude/skills/[^`\s]+\.py)"
        for match in re.finditer(pattern2, content, re.IGNORECASE):
            path = match.group(1)
            line_num = content[: match.start()].count("\n") + 1
            paths.append((path, line_num))

        # Pattern 3: scripts/ subdirectory references
        pattern3 = r"(?:python|bash)\s+([a-zA-Z]:\\\.claude\\skills\\[^`\s]+\\scripts\\[^`\s]+\.py)"
        for match in re.finditer(pattern3, content, re.IGNORECASE):
            path = match.group(1)
            line_num = content[: match.start()].count("\n") + 1
            paths.append((path, line_num))

        return paths

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path should be exempt from validation."""
        return any(re.match(pattern, path) for pattern in self.EXEMPT_PATTERNS)

    def _check_path_integrity(
        self, skill_md_path: str, skill_dir: Path
    ) -> tuple[int, int, list[str]]:
        """Verify that referenced file paths exist.

        Returns:
            Tuple of (items_checked, items_passed, findings)
        """
        findings = []
        paths = self._extract_referenced_paths(skill_md_path)

        if not paths:
            findings.append("ℹ️  No file paths found in SKILL.md to validate")
            return 0, 0, findings

        checked = 0
        passed = 0

        for path_str, line_num in paths:
            if self._is_exempt_path(path_str):
                continue

            checked += 1
            # Normalize path for validation
            test_path = Path(path_str.replace("/", "\\"))

            if not test_path.is_absolute():
                test_path = skill_dir / path_str

            if test_path.exists():
                passed += 1
                findings.append(f"✅ Referenced file exists: {path_str} (line {line_num})")
            else:
                # Check if files/ subdirectory might be the intended location
                alt_path = skill_dir / "scripts" / Path(path_str).name
                if alt_path.exists():
                    findings.append(
                        f"⚠️  Path mismatch (line {line_num}): {path_str}\n"
                        f"    File exists at: scripts/{Path(path_str).name}"
                    )
                else:
                    findings.append(f"❌ Referenced file not found (line {line_num}): {path_str}")

        return checked, passed, findings

    def verify_target(self, target_path: str) -> Dict[str, Any]:
        """Verify a skill directory against checklist criteria.

        Args:
            target_path: Path to the skill directory

        Returns:
            ChecklistResult with status, counts, and findings

        Raises:
            ValueError: If target_path is invalid
        """
        if not target_path:
            raise ValueError("target_path cannot be empty")

        findings = []
        items_checked = 0
        items_passed = 0

        # Check 1: SKILL.md exists
        items_checked += 1
        skill_md_path = f"{target_path}/SKILL.md"
        if self._file_exists(skill_md_path):
            items_passed += 1
            findings.append(f"✅ SKILL.md exists: {skill_md_path}")
        else:
            findings.append(f"❌ SKILL.md missing: {skill_md_path}")

        # Check 2: Tests directory exists
        items_checked += 1
        tests_path = f"{target_path}/tests"
        if self._file_exists(tests_path):
            items_passed += 1
            findings.append(f"✅ Tests directory exists: {tests_path}")
        else:
            findings.append(f"❌ Tests directory missing: {tests_path}")

        # Check 3: Skill registered in router
        items_checked += 1
        skill_name = Path(target_path).name
        if self._file_exists(self.ROUTER_PATH):
            router_content = self._read_file(self.ROUTER_PATH)
            if skill_name in router_content:
                items_passed += 1
                findings.append(f"✅ Skill registered in router: {skill_name}")
            else:
                findings.append(f"❌ Skill not registered in router: {skill_name}")
        else:
            findings.append(f"⚠️  Router file not found: {self.ROUTER_PATH}")

        # Check 4: Path integrity (referenced files exist)
        skill_md_path = f"{target_path}/SKILL.md"
        if self._file_exists(skill_md_path):
            checked, passed, path_findings = self._check_path_integrity(
                skill_md_path, Path(target_path)
            )
            items_checked += checked
            items_passed += passed
            findings.extend(path_findings)

        # Calculate overall status
        status = self._calculate_status(items_checked, items_passed)

        return self._create_result(
            status=status,
            items_checked=items_checked,
            items_passed=items_passed,
            findings=findings,
        )
