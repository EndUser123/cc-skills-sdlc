"""
Backward compatibility tests for UCI unified code inspection.

Tests that /review and /adversarial-review wrappers correctly delegate to /uci
with appropriate modes.
"""

from pathlib import Path

import pytest


class TestBackwardCompatibility:
    """Test backward compatibility wrapper behavior."""

    def test_review_skill_exists(self):
        """Test that /review skill wrapper exists."""
        review_skill = Path("P:/.claude/skills/review/SKILL.md")
        assert review_skill.exists(), "/review skill wrapper should exist"

    def test_review_skill_delegates_to_uci_triage(self):
        """Test that /review skill delegates to /uci --mode=triage."""
        review_skill = Path("P:/.claude/skills/review/SKILL.md")
        content = review_skill.read_text(encoding="utf-8")

        # Should mention UCI delegation
        assert "uci" in content.lower() or "unified" in content.lower()
        # Should mention triage mode
        assert "triage" in content.lower()
        # Should be marked as deprecated
        assert "deprecated" in content.lower()

    def test_review_skill_triggers(self):
        """Test that /review skill has correct triggers."""
        review_skill = Path("P:/.claude/skills/review/SKILL.md")
        content = review_skill.read_text(encoding="utf-8")

        # Should have /review trigger
        assert '"/review"' in content or "review:" in content.lower()

    def test_adversarial_review_skill_exists(self):
        """Test that /adversarial-review skill wrapper exists."""
        adv_skill = Path("P:/.claude/skills/adversarial-review/SKILL.md")
        assert adv_skill.exists(), "/adversarial-review skill wrapper should exist"

    def test_adversarial_review_skill_delegates_to_uci_deep(self):
        """Test that /adversarial-review skill delegates to /uci --mode=deep."""
        adv_skill = Path("P:/.claude/skills/adversarial-review/SKILL.md")
        content = adv_skill.read_text(encoding="utf-8")

        # Should mention UCI delegation
        assert "uci" in content.lower() or "unified" in content.lower()
        # Should mention deep mode
        assert "deep" in content.lower()
        # Should be marked as deprecated
        assert "deprecated" in content.lower()

    def test_adversarial_review_skill_triggers(self):
        """Test that /adversarial-review skill has correct triggers."""
        adv_skill = Path("P:/.claude/skills/adversarial-review/SKILL.md")
        content = adv_skill.read_text(encoding="utf-8")

        # Should have /adversarial-review trigger
        assert "/adversarial-review" in content or "adversarial-review:" in content.lower()

    def test_migration_guidance_present(self):
        """Test that both skills provide migration guidance."""
        review_skill = Path("P:/.claude/skills/review/SKILL.md")
        adv_skill = Path("P:/.claude/skills/adversarial-review/SKILL.md")

        review_content = review_skill.read_text(encoding="utf-8")
        adv_content = adv_skill.read_text(encoding="utf-8")

        # Both should mention migration to /uci
        assert "/uci" in review_content or "unified" in review_content.lower()
        assert "/uci" in adv_content or "unified" in adv_content.lower()


class TestUCISkillExists:
    """Test that the UCI skill itself exists and is properly configured."""

    def test_uci_skill_exists(self):
        """Test that /uci skill exists."""
        uci_skill = Path("P:/.claude/skills/uci/SKILL.md")
        assert uci_skill.exists(), "/uci skill should exist"

    def test_uci_skill_has_triggers(self):
        """Test that /uci skill has expected triggers."""
        uci_skill = Path("P:/.claude/skills/uci/SKILL.md")
        content = uci_skill.read_text(encoding="utf-8")

        # Should have main triggers
        assert "/uci" in content or "unified-code-inspection" in content.lower()
        # Should mention code-review alias
        assert "code-review" in content.lower() or "/code-review" in content

    def test_uci_skill_has_mode_parameter(self):
        """Test that /uci skill supports mode parameter."""
        uci_skill = Path("P:/.claude/skills/uci/SKILL.md")
        content = uci_skill.read_text(encoding="utf-8")

        # Should mention mode parameter
        assert "--mode" in content or "mode=" in content


class TestModeMapping:
    """Test mode mapping from old skills to UCI."""

    def test_review_maps_to_triage(self):
        """Test that /review maps to triage mode (3 core agents)."""
        review_skill = Path("P:/.claude/skills/review/SKILL.md")
        content = review_skill.read_text(encoding="utf-8")

        # Should mention triage mode
        assert "triage" in content.lower()
        # Should mention 3 core agents (logic, tests, security)
        assert any(term in content.lower() for term in ["logic", "tests", "security"])

    def test_adversarial_review_maps_to_deep(self):
        """Test that /adversarial-review maps to deep mode (8 agents)."""
        adv_skill = Path("P:/.claude/skills/adversarial-review/SKILL.md")
        content = adv_skill.read_text(encoding="utf-8")

        # Should mention deep mode
        assert "deep" in content.lower()
        # Should mention extended agents
        assert any(
            term in content.lower()
            for term in ["performance", "conventions", "quality", "compliance", "qa"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
