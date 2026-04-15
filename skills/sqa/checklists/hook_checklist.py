"""Hook-specific verification checklist.

Validates hook completeness:
- Hook file exists
- Hook registration present (decorator or registration)
- Router execution configuration
- Chain completion handler
"""

import re
from typing import Any, Dict, List

from .base_checklist import VerificationChecklist


class HookChecklist(VerificationChecklist):
    """Verification checklist for hook files.

    Checks hook completeness indicators:
    1. Hook file exists
    2. Hook registration (decorator or registration pattern)
    3. Router execution configuration (HOOK_PRIORITY, HOOK_DISPATCH)
    4. Chain completion handler (chain validation logic)
    """

    # Registration patterns to detect
    REGISTRATION_PATTERNS: List[str] = [
        r"@register_hook\s*\(",
        r"@hook\s*\(",
        r"@claude_hook\s*\(",
        r"register.*hook",
        r"HOOK_PRIORITY\s*=",
        r"HOOK_DISPATCH\s*=",
    ]

    # Router configuration patterns
    ROUTER_PATTERNS: List[str] = [
        r"HOOK_PRIORITY\s*=",
        r"HOOK_DISPATCH\s*=",
        r"router\s*=",
        r"@router",
    ]

    # Chain completion patterns
    CHAIN_PATTERNS: List[str] = [
        r"chain.*complete",
        r"validate.*chain",
        r"check.*chain",
        r"chain_handler",
        r"process.*chain",
    ]

    def verify_target(self, target_path: str) -> Dict[str, Any]:
        """Verify a hook file against checklist criteria.

        Args:
            target_path: Path to the hook file

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

        # Check 1: Hook file exists
        items_checked += 1
        if self._file_exists(target_path):
            items_passed += 1
            findings.append(f"✅ hook_file_exists: {target_path}")

            # Read file content for further checks
            content = self._read_file(target_path)

            # Check 2: Hook registration
            items_checked += 1
            if self._check_patterns(content, self.REGISTRATION_PATTERNS):
                items_passed += 1
                findings.append("✅ hook_registration: Registration pattern detected")
            else:
                findings.append("❌ hook_registration: No registration pattern found")

            # Check 3: Router configuration
            items_checked += 1
            if self._check_patterns(content, self.ROUTER_PATTERNS):
                items_passed += 1
                findings.append("✅ router_configuration: Router config detected")
            else:
                findings.append("❌ router_configuration: No router config found")

            # Check 4: Chain completion handler
            items_checked += 1
            if self._check_patterns(content, self.CHAIN_PATTERNS):
                items_passed += 1
                findings.append("✅ chain_completion_handler: Chain handler detected")
            else:
                findings.append("❌ chain_completion_handler: No chain handler found")
        else:
            findings.append(f"❌ hook_file_exists: File not found: {target_path}")

        # Calculate overall status
        status = self._calculate_status(items_checked, items_passed)

        return self._create_result(
            status=status,
            items_checked=items_checked,
            items_passed=items_passed,
            findings=findings,
        )

    def _check_patterns(self, content: str, patterns: List[str]) -> bool:
        """Check if any pattern matches the content.

        Args:
            content: Text content to search within
            patterns: List of regex patterns to match

        Returns:
            True if any pattern matches, False otherwise
        """
        if not content:
            return False

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False
