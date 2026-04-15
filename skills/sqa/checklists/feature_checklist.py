"""Feature-specific verification checklist.

Validates feature completeness:
- Feature documented in spec.md
- Tests exist
- Integration verified
"""

from typing import Any, Dict

from .base_checklist import VerificationChecklist


class FeatureChecklist(VerificationChecklist):
    """Verification checklist for feature directories.

    Checks feature completeness indicators:
    1. spec.md exists
    2. Tests directory exists
    3. Integration documentation exists
    """

    def verify_target(self, target_path: str) -> Dict[str, Any]:
        """Verify a feature directory against checklist criteria.

        Args:
            target_path: Path to the feature directory

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

        # Check 1: spec.md exists
        items_checked += 1
        spec_path = f"{target_path}/spec.md"
        if self._file_exists(spec_path):
            items_passed += 1
            findings.append(f"✅ spec.md exists: {spec_path}")
        else:
            findings.append(f"❌ spec.md missing: {spec_path}")

        # Check 2: Tests directory exists
        items_checked += 1
        tests_path = f"{target_path}/tests"
        if self._file_exists(tests_path):
            items_passed += 1
            findings.append(f"✅ Tests directory exists: {tests_path}")
        else:
            findings.append(f"❌ Tests directory missing: {tests_path}")

        # Check 3: Integration documentation exists
        items_checked += 1
        integration_path = f"{target_path}/INTEGRATION.md"
        if self._file_exists(integration_path):
            items_passed += 1
            findings.append(f"✅ Integration documentation exists: {integration_path}")
        else:
            findings.append(f"❌ Integration documentation missing: {integration_path}")

        # Calculate overall status
        status = self._calculate_status(items_checked, items_passed)

        return self._create_result(
            status=status,
            items_checked=items_checked,
            items_passed=items_passed,
            findings=findings,
        )
