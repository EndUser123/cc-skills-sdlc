"""
Unit tests for new agent registry functionality.

Tests for TASK-012, TASK-013:
- Registration of 3 new agents (state-machine, invariants, io-validation)
- Tier-based mode activation (cognitive load mitigation)
- Agent spec file existence
"""

from pathlib import Path

import pytest


class TestNewAgentRegistration:
    """Test registration of 3 new adversarial agents (TASK-012)."""

    def test_state_machine_agent_registered(self):
        """Test that adversarial-state-machine agent is registered."""
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should have state-machine in AGENT_REGISTRY
        assert "state-machine" in content or "state_machine" in content

    def test_invariants_agent_registered(self):
        """Test that adversarial-invariants agent is registered."""
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should have invariants in AGENT_REGISTRY
        assert "invariants" in content

    def test_io_validation_agent_registered(self):
        """Test that adversarial-io-validation agent is registered."""
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Should have io-validation in AGENT_REGISTRY
        assert "io-validation" in content or "io_validation" in content


class TestNewAgentTierClassification:
    """Test that new agents have tier='extended" classification."""

    def test_new_agents_have_extended_tier(self):
        """Test that all 3 new agents are classified as tier="extended"."""
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Look for tier classification around new agents
        # Should have "extended" tier for new agents
        assert '"extended"' in content or "'extended'" in content


class TestTierBasedModeActivation:
    """Test tier-based mode activation (TASK-013 - cognitive load mitigation).

    Based on Phase 0.5 findings, tier-based activation reduces cognitive load:
    - triage (3 agents): No new agents
    - standard (4 agents): No new agents
    - deep (8 agents): state-machine only
    - comprehensive (11+ agents): All 3 new agents
    """

    def test_triage_mode_excludes_new_agents(self):
        """Test that triage mode does NOT include new agents (cognitive load mitigation)."""
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Find MODE_AGENTS["triage"] definition
        # Look for: "triage": [list of agents]
        import re

        triage_match = re.search(r'"triage":\s*\[(.*?)\]', content, re.DOTALL)
        assert triage_match is not None, "triage mode should be defined as list"

        triage_agents = triage_match.group(1)

        # Should NOT have state-machine, invariants, or io-validation in triage
        assert "state-machine" not in triage_agents and "state_machine" not in triage_agents
        assert "invariants" not in triage_agents
        assert "io-validation" not in triage_agents and "io_validation" not in triage_agents

    def test_standard_mode_excludes_new_agents(self):
        """Test that standard mode does NOT include new agents (cognitive load mitigation)."""
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Find MODE_AGENTS["standard"] definition
        import re

        standard_match = re.search(r'"standard":\s*\[(.*?)\]', content, re.DOTALL)
        assert standard_match is not None, "standard mode should be defined as list"

        standard_agents = standard_match.group(1)

        # Should NOT have new agents in standard mode
        assert "state-machine" not in standard_agents and "state_machine" not in standard_agents
        assert "invariants" not in standard_agents
        assert "io-validation" not in standard_agents and "io_validation" not in standard_agents

    def test_deep_mode_includes_state_machine_only(self):
        """Test that deep mode includes state-machine agent only (cognitive load mitigation).

        Deep mode (8 agents) should include state-machine but NOT invariants or io-validation.
        This is the mitigation strategy to reduce cognitive load while preserving
        critical state-transition detection.
        """
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Find MODE_AGENTS["deep"] section
        deep_start = content.find('"deep"')
        if deep_start == -1:
            deep_start = content.find("'deep'")

        assert deep_start != -1, "deep mode should exist in MODE_AGENTS"

        # Extract deep section
        deep_section = content[deep_start : deep_start + 800]

        # Should have state-machine in deep mode
        assert (
            "state-machine" in deep_section or "state_machine" in deep_section
        ), "deep mode should include state-machine agent"

        # Should NOT have invariants or io-validation in deep mode (mitigation)
        # Extract the deep mode list more precisely
        deep_list_start = deep_section.find("[")
        deep_list_end = deep_section.rfind("]") + 1
        if deep_list_start != -1 and deep_list_end > deep_list_start:
            deep_list = deep_section[deep_list_start:deep_list_end]

            # Count occurrences of new agents in deep mode
            state_machine_count = deep_list.count("state-machine") + deep_list.count(
                "state_machine"
            )
            invariants_count = deep_list.count("invariants")
            io_validation_count = deep_list.count("io-validation") + deep_list.count(
                "io_validation"
            )

            # state-machine should be present (1)
            assert state_machine_count >= 1, "deep mode should include state-machine agent"

            # invariants and io-validation should NOT be present (0) - mitigation
            assert (
                invariants_count == 0
            ), "deep mode should NOT include invariants agent (cognitive load mitigation)"
            assert (
                io_validation_count == 0
            ), "deep mode should NOT include io-validation agent (cognitive load mitigation)"

    def test_comprehensive_mode_includes_all_new_agents(self):
        """Test that comprehensive mode includes all 3 new agents.

        Comprehensive mode uses "all" which means _get_all_agents() returns ALL agents.
        This should include:
        - adversarial-state-machine
        - adversarial-invariants
        - adversarial-io-validation
        """
        registry = Path("P:/.claude/skills/uci/lib/agent_registry.py")
        content = registry.read_text(encoding="utf-8")

        # Find comprehensive mode definition - it should be "all"
        import re

        comprehensive_match = re.search(r'"comprehensive":\s*"(.*?)"', content)
        assert comprehensive_match is not None, "comprehensive mode should be defined"
        assert comprehensive_match.group(1) == "all", "comprehensive mode should be 'all'"

        # Also verify the 3 new agents are in AGENT_REGISTRY
        # (since "all" means all agents from the registry)
        assert "adversarial-state-machine" in content, "state-machine should be in AGENT_REGISTRY"
        assert "adversarial-invariants" in content, "invariants should be in AGENT_REGISTRY"
        assert "adversarial-io-validation" in content, "io-validation should be in AGENT_REGISTRY"


class TestNewAgentSpecFiles:
    """Test that new agent spec files exist (TASK-009, TASK-010, TASK-011)."""

    def test_state_machine_agent_spec_exists(self):
        """Test that adversarial-state-machine.md spec file exists."""
        spec_file = Path("P:/.claude/agents/adversarial-state-machine.md")
        assert spec_file.exists(), "adversarial-state-machine.md should exist"

    def test_invariants_agent_spec_exists(self):
        """Test that adversarial-invariants.md spec file exists."""
        spec_file = Path("P:/.claude/agents/adversarial-invariants.md")
        assert spec_file.exists(), "adversarial-invariants.md should exist"

    def test_io_validation_agent_spec_exists(self):
        """Test that adversarial-io-validation.md spec file exists."""
        spec_file = Path("P:/.claude/agents/adversarial-io-validation.md")
        assert spec_file.exists(), "adversarial-io-validation.md should exist"


class TestNewAgentSpecContent:
    """Test that new agent specs have required content."""

    def test_state_machine_spec_has_focus(self):
        """Test that state-machine agent spec defines focus area."""
        spec_file = Path("P:/.claude/agents/adversarial-state-machine.md")
        content = spec_file.read_text(encoding="utf-8")

        # Should mention state transition focus
        assert "state" in content.lower(), "state-machine spec should mention state"
        assert "transition" in content.lower(), "state-machine spec should mention transitions"

    def test_invariants_spec_has_focus(self):
        """Test that invariants agent spec defines focus area."""
        spec_file = Path("P:/.claude/agents/adversarial-invariants.md")
        content = spec_file.read_text(encoding="utf-8")

        # Should mention invariants focus
        assert "invariant" in content.lower(), "invariants spec should mention invariants"
        assert (
            "id" in content.lower() or "identity" in content.lower()
        ), "invariants spec should mention ID/identity"

    def test_io_validation_spec_has_focus(self):
        """Test that io-validation agent spec defines focus area."""
        spec_file = Path("P:/.claude/agents/adversarial-io-validation.md")
        content = spec_file.read_text(encoding="utf-8")

        # Should mention I/O focus
        assert (
            "i/o" in content.lower() or "io" in content.lower() or "input/output" in content.lower()
        ), "io-validation spec should mention I/O"
        assert "validation" in content.lower(), "io-validation spec should mention validation"


class TestAdversarialFraming:
    """Test adversarial framing enhancement (TASK-014)."""

    def test_orchestrator_has_adversarial_framework(self):
        """Test that orchestrator.py includes adversarial framing section."""
        orchestrator = Path("P:/.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have adversarial framework in prompts
        assert "adversarial" in content.lower(), "orchestrator should include adversarial framing"
        assert (
            "critical" in content.lower() and "pass" in content.lower()
        ), "orchestrator should mention 'critical pass' framing"
        assert (
            "failure" in content.lower() and "mode" in content.lower()
        ), "orchestrator should mention failure mode detection"


class TestTOCTOUEnhancement:
    """Test TOCTOU enhancement to performance agent (TASK-015)."""

    def test_performance_agent_has_toctou_detection(self):
        """Test that adversarial-performance.md includes TOCTOU detection."""
        perf_agent = Path("P:/.claude/agents/adversarial-performance.md")
        content = perf_agent.read_text(encoding="utf-8")

        # Should mention TOCTOU
        assert (
            "toctou" in content.lower() or "time-of-check-time-of-use" in content.lower()
        ), "performance agent should mention TOCTOU detection"
        assert (
            "race condition" in content.lower()
        ), "performance agent should mention race conditions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
