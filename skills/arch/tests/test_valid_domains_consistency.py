"""
Test VALID_DOMAINS consistency between config.py and routing.py.

These tests verify that VALID_DOMAINS is defined identically across both modules
to prevent validation failures due to configuration inconsistencies.

Quality Issue: QUAL-002
Run with: pytest P:/.claude/skills/arch/tests/test_valid_domains_consistency.py -v
"""

import sys
from pathlib import Path

import pytest

# Add parent directories to path for package imports
test_dir = Path(__file__).parent
arch_dir = test_dir.parent
skills_dir = arch_dir.parent
sys.path.insert(0, str(skills_dir))


def test_valid_domains_identical():
    """
    Test that VALID_DOMAINS in config.py and routing.py are identical sets.

    Given: Both config.py and routing.py define VALID_DOMAINS
    When: Comparing the sets
    Then: They must contain exactly the same elements

    This test ensures consistency prevents validation failures where:
    - config.py validates against one set of domains
    - routing.py validates against a different set
    - This causes "Invalid domain" errors for valid domains

    QUAL-002: VALID_DOMAINS inconsistency between config.py and routing.py
    - config.py VALID_DOMAINS: {'python', 'data-pipeline', 'precedent', 'cli'}
    - routing.py VALID_DOMAINS: {'cli', 'python', 'data-pipeline', 'precedent', 'auto'}
    - Difference: routing.py has 'auto', config.py does not
    """
    # Arrange - Import via package path for relative imports to work
    from skill.config import VALID_DOMAINS as CONFIG_DOMAINS
    from skill.routing import VALID_DOMAINS as ROUTING_DOMAINS

    # Act - Calculate the differences
    missing_in_routing = CONFIG_DOMAINS - ROUTING_DOMAINS
    missing_in_config = ROUTING_DOMAINS - CONFIG_DOMAINS

    # Assert - Both sets must be identical
    assert CONFIG_DOMAINS == ROUTING_DOMAINS, (
        f"VALID_DOMAINS mismatch between modules:\n"
        f"  Domains only in config.py: {missing_in_routing}\n"
        f"  Domains only in routing.py: {missing_in_config}\n"
        f"  config.py VALID_DOMAINS: {sorted(CONFIG_DOMAINS)}\n"
        f"  routing.py VALID_DOMAINS: {sorted(ROUTING_DOMAINS)}"
    )


def test_valid_domains_contains_expected_core_domains():
    """
    Test that VALID_DOMAINS in both modules contains expected core domains.

    Given: The architecture system has core domains
    When: Checking VALID_DOMAINS in both modules
    Then: Both must contain at least the core domains

    This is a weaker test that ensures basic functionality even if
    the exact sets don't match.
    """
    # Arrange - Import via package path for relative imports to work
    from skill.config import VALID_DOMAINS as CONFIG_DOMAINS
    from skill.routing import VALID_DOMAINS as ROUTING_DOMAINS

    # Define core domains that should exist in both
    CORE_DOMAINS = {"python", "data-pipeline", "precedent", "cli"}

    # Act & Assert
    assert CORE_DOMAINS.issubset(CONFIG_DOMAINS), (
        f"config.py VALID_DOMAINS missing core domains. "
        f"Expected: {CORE_DOMAINS}, Got: {CONFIG_DOMAINS}"
    )

    assert CORE_DOMAINS.issubset(ROUTING_DOMAINS), (
        f"routing.py VALID_DOMAINS missing core domains. "
        f"Expected: {CORE_DOMAINS}, Got: {ROUTING_DOMAINS}"
    )
