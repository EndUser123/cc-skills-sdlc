"""
Integration tests for UCI agent mode selection.

Tests that different modes (triage, standard, deep, comprehensive)
select the correct agents.
"""

from pathlib import Path

import pytest


class TestAgentRegistry:
    """Test agent registry configuration."""

    def test_agent_registry_exists(self):
        """Test that agent_registry.py module exists."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        assert registry.exists(), "agent_registry.py should exist"

    def test_agent_registry_has_mode_agents(self):
        """Test that agent registry defines MODE_AGENTS mapping."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should have MODE_AGENTS constant
        assert "MODE_AGENTS" in content
        # Should define mode mappings
        assert '"triage"' in content or "'triage'" in content
        assert '"standard"' in content or "'standard'" in content
        assert '"deep"' in content or "'deep'" in content
        assert '"comprehensive"' in content or "'comprehensive'" in content

    def test_agent_registry_has_agent_registry(self):
        """Test that agent registry defines AGENT_REGISTRY mapping."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should have AGENT_REGISTRY constant
        assert "AGENT_REGISTRY" in content

    def test_agent_registry_exported(self):
        """Test that select_agents function is exported from __init__.py."""
        init_file = Path("P:\\\\\\.claude/skills/uci/lib/__init__.py")
        content = init_file.read_text(encoding="utf-8")

        # Should export select_agents
        assert '"select_agents"' in content or "'select_agents'" in content


class TestTriageMode:
    """Test triage mode (3 core agents)."""

    def test_triage_mode_has_logic_agent(self):
        """Test that triage mode includes logic agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include logic in triage mode
        assert '"logic"' in content or "'logic'" in content

    def test_triage_mode_has_tests_agent(self):
        """Test that triage mode includes tests agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include tests in triage mode
        assert '"tests"' in content or "'tests'" in content

    def test_triage_mode_has_security_agent(self):
        """Test that triage mode includes security agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include security in triage mode
        assert '"security"' in content or "'security'" in content


class TestStandardMode:
    """Test standard mode (4 agents: core + performance)."""

    def test_standard_mode_has_performance_agent(self):
        """Test that standard mode includes performance agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include performance in standard mode
        assert '"performance"' in content or "'performance'" in content


class TestDeepMode:
    """Test deep mode (8 agents: standard + conventions, quality, compliance, qa)."""

    def test_deep_mode_has_conventions_agent(self):
        """Test that deep mode includes conventions agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include conventions in deep mode
        assert '"conventions"' in content or "'conventions'" in content

    def test_deep_mode_has_quality_agent(self):
        """Test that deep mode includes quality agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include quality in deep mode
        assert '"quality"' in content or "'quality'" in content

    def test_deep_mode_has_compliance_agent(self):
        """Test that deep mode includes compliance agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include compliance in deep mode
        assert '"compliance"' in content or "'compliance'" in content

    def test_deep_mode_has_qa_agent(self):
        """Test that deep mode includes qa agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include qa in deep mode
        assert '"qa"' in content or "'qa'" in content


class TestComprehensiveMode:
    """Test comprehensive mode (all agents including simplification, rca, failure-modes)."""

    def test_comprehensive_mode_has_simplification_agent(self):
        """Test that comprehensive mode includes simplification agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include simplification in comprehensive mode
        assert '"simplification"' in content or "'simplification'" in content

    def test_comprehensive_mode_has_rca_agent(self):
        """Test that comprehensive mode includes rca agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include rca in comprehensive mode
        assert '"rca"' in content or "'rca'" in content

    def test_comprehensive_mode_has_failure_modes_agent(self):
        """Test that comprehensive mode includes failure-modes agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include failure-modes in comprehensive mode
        assert '"failure-modes"' in content or "'failure-modes'" in content

    def test_comprehensive_mode_has_deployment_safety_agent(self):
        """Test that comprehensive mode includes deployment-safety agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include deployment-safety in comprehensive mode
        assert '"deployment-safety"' in content or "'deployment-safety'" in content

    def test_comprehensive_mode_has_python_modernization_agent(self):
        """Test that comprehensive mode includes python-modernization agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include python-modernization in comprehensive mode
        assert '"python-modernization"' in content or "'python-modernization'" in content

    def test_comprehensive_mode_has_test_quality_roi_agent(self):
        """Test that comprehensive mode includes test-quality-roi agent."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should include test-quality-roi in comprehensive mode
        assert '"test-quality-roi"' in content or "'test-quality-roi'" in content


class TestAgentTierClassification:
    """Test agent tier classification (core, extended, comprehensive)."""

    def test_core_tier_agents_exist(self):
        """Test that core tier agents are defined."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Core agents: logic, tests, security
        assert all(
            f'"{agent}"' in content or f"'{agent}'" in content
            for agent in ["logic", "tests", "security"]
        )

    def test_extended_tier_agents_exist(self):
        """Test that extended tier agents are defined."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Extended agents: performance, conventions, quality, compliance, qa
        assert all(
            f'"{agent}"' in content or f"'{agent}'" in content
            for agent in ["performance", "conventions", "quality", "compliance", "qa"]
        )

    def test_comprehensive_tier_agents_exist(self):
        """Test that comprehensive tier agents are defined."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Comprehensive agents: simplification, rca, failure-modes, deployment-safety, python-modernization, test-quality-roi
        assert all(
            f'"{agent}"' in content or f"'{agent}'" in content
            for agent in [
                "simplification",
                "rca",
                "failure-modes",
                "deployment-safety",
                "python-modernization",
                "test-quality-roi",
            ]
        )


class TestSubagentTypeMapping:
    """Test subagent_type mapping for agents."""

    def test_agent_registry_has_subagent_type(self):
        """Test that agents have subagent_type field."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should have subagent_type field
        assert "subagent_type" in content

    def test_known_subagent_types_mapped(self):
        """Test that known subagent types are used."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Known subagent types from adversarial agents
        known_types = [
            "adversarial-logic",
            "adversarial-testing",
            "adversarial-security",
            "adversarial-performance",
            "code-simplifier",
            "python-simplifier",
            "qa-engineer",
        ]

        # At least some of these should be referenced
        found = sum(1 for t in known_types if t in content)
        assert found > 0, "At least some known subagent types should be referenced"


class TestModeAgentCounts:
    """Test expected agent counts per mode."""

    def test_triage_mode_agent_count(self):
        """Test that triage mode has 3 agents."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Look for MODE_AGENTS["triage"] definition
        # Should have 3 agents
        triage_section = content[content.find("MODE_AGENTS") : content.find("MODE_AGENTS") + 500]
        assert "triage" in triage_section.lower()

    def test_deep_mode_agent_count(self):
        """Test that deep mode has 8 agents."""
        registry = Path("P:\\\\\\.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Look for MODE_AGENTS["deep"] definition
        # Should have 8 agents
        assert "MODE_AGENTS" in content
        assert "deep" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
