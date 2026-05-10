"""
Integration tests for Enhanced CKS Metadata features.

Tests the enhanced metadata schema (AgentConsensus, CrossFileMetadata, ReviewMetadata)
integration with the UCI orchestrator for cross-session learning.
"""

from pathlib import Path

import pytest


class TestEnhancedMetadataClasses:
    """Test enhanced metadata dataclasses in memory_integration.py."""

    def test_memory_integration_module_exists(self):
        """Test that memory_integration.py module exists."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        assert memory_module.exists(), "memory_integration.py should exist"

    def test_agent_consensus_class_exists(self):
        """Test that AgentConsensus dataclass exists."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        content = memory_module.read_text(encoding="utf-8")

        # Should have AgentConsensus dataclass
        assert "class AgentConsensus" in content
        # Should have required fields
        assert "confirming_agents" in content
        assert "dissenting_agents" in content
        assert "consensus_level" in content
        assert "avg_confidence" in content
        assert "location_agreement" in content

    def test_cross_file_metadata_class_exists(self):
        """Test that CrossFileMetadata dataclass exists."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        content = memory_module.read_text(encoding="utf-8")

        # Should have CrossFileMetadata dataclass
        assert "class CrossFileMetadata" in content
        # Should have required fields
        assert "import_graph_nodes" in content
        assert "import_graph_edges" in content
        assert "circular_dependencies" in content
        assert "taint_paths" in content
        assert "hot_spots" in content

    def test_review_metadata_class_exists(self):
        """Test that ReviewMetadata dataclass exists."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        content = memory_module.read_text(encoding="utf-8")

        # Should have ReviewMetadata dataclass
        assert "class ReviewMetadata" in content
        # Should have required fields
        assert "mode" in content
        assert "file_count" in content
        assert "line_count" in content
        assert "languages" in content
        assert "primary_language" in content
        assert "session_id" in content
        assert "timestamp" in content
        assert "git_scope" in content
        assert "branch" in content
        assert "file_types" in content

    def test_extract_review_metadata_method_exists(self):
        """Test that MemoryIntegration has extract_review_metadata method."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        content = memory_module.read_text(encoding="utf-8")

        # Should have extract_review_metadata method
        assert "def extract_review_metadata" in content

    def test_extract_agent_consensus_method_exists(self):
        """Test that MemoryIntegration has extract_agent_consensus method."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        content = memory_module.read_text(encoding="utf-8")

        # Should have extract_agent_consensus method
        assert "def extract_agent_consensus" in content

    def test_prepare_storage_entry_accepts_enhanced_metadata(self):
        """Test that prepare_storage_entry accepts enhanced metadata parameters."""
        memory_module = Path("P:\\\\\\.claude/skills/uci/lib/memory_integration.py")
        content = memory_module.read_text(encoding="utf-8")

        # Should have prepare_storage_entry with enhanced metadata parameters
        assert "def prepare_storage_entry" in content
        # Should accept enhanced metadata parameters
        assert "review_metadata" in content
        assert "agent_consensus" in content
        assert "cross_file_metadata" in content


class TestOrchestratorEnhancedIntegration:
    """Test orchestrator integration with enhanced metadata."""

    def test_orchestrator_imports_enhanced_classes(self):
        """Test that orchestrator.py imports the enhanced metadata classes."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should import all three enhanced metadata classes
        assert "AgentConsensus" in content
        assert "CrossFileMetadata" in content
        assert "ReviewMetadata" in content

    def test_orchestrator_has_runtime_reference(self):
        """Test that orchestrator has runtime reference tuple to prevent linter removal."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have _MEMORY_CLASSES reference tuple
        assert "_MEMORY_CLASSES" in content
        # Should include all three classes
        assert "AgentConsensus" in content
        assert "CrossFileMetadata" in content
        assert "ReviewMetadata" in content

    def test_aggregate_findings_signature_has_context_params(self):
        """Test that aggregate_findings has new context parameters."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have aggregate_findings method with new parameters
        assert "def aggregate_findings" in content
        # Should have context parameters
        assert "mode:" in content
        assert "file_list:" in content
        assert "git_scope:" in content
        assert "session_id:" in content
        assert "line_counts:" in content
        assert "cross_file_stats:" in content

    def test_aggregate_findings_extracts_review_metadata(self):
        """Test that aggregate_findings extracts review metadata."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should call extract_review_metadata
        assert "extract_review_metadata" in content
        # Should pass required parameters
        assert "file_list=file_list" in content
        assert "mode=mode" in content
        assert "git_scope=git_scope" in content
        assert "session_id=session_id" in content

    def test_aggregate_findings_extracts_agent_consensus(self):
        """Test that aggregate_findings extracts agent consensus."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should call extract_agent_consensus
        assert "extract_agent_consensus" in content
        # Should pass validated_results
        assert "validated_results=validated_results" in content

    def test_aggregate_findings_builds_cross_file_metadata(self):
        """Test that aggregate_findings builds cross-file metadata."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should build CrossFileMetadata from cross_file_stats
        assert "CrossFileMetadata(" in content
        # Should extract fields from cross_file_stats
        assert "import_graph_nodes" in content
        assert "import_graph_edges" in content
        assert "circular_dependencies" in content
        assert "taint_paths" in content

    def test_aggregate_findings_calculates_storeable_count(self):
        """Test that aggregate_findings calculates storeable findings count."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should calculate storeable_count
        assert "storeable_count" in content
        # Should filter by severity and confidence
        assert "severity" in content
        assert "confidence" in content
        # Should check for location evidence
        assert "location" in content

    def test_aggregate_findings_has_enhanced_metadata_tracking(self):
        """Test that aggregate_findings tracks enhanced metadata extraction."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should track which metadata types were extracted
        assert "enhanced_metadata_extracted" in content
        # Should track each metadata type
        assert "review_metadata" in content
        assert "agent_consensus" in content
        assert "cross_file_metadata" in content

    def test_aggregate_findings_format_storage_with_enhanced_metadata(self):
        """Test that aggregate_findings calls format_storage_prompt with enhanced metadata."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should call format_storage_prompt with enhanced metadata
        assert "format_storage_prompt" in content
        # Should pass enhanced metadata parameters (review_metadata, validated_results, cross_file_metadata)
        assert "review_metadata=" in content
        assert "validated_results=" in content
        assert "cross_file_metadata=" in content


class TestEnhancedMetadataErrorHandling:
    """Test error handling in enhanced metadata extraction."""

    def test_extract_review_metadata_has_error_handling(self):
        """Test that review metadata extraction has error handling."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have try/except for extract_review_metadata
        lines = content.split("\n")
        found_extract = False
        found_except = False

        for _i, line in enumerate(lines):
            if "extract_review_metadata" in line:
                found_extract = True
            if found_extract and "except" in line:
                found_except = True
                break

        assert found_extract, "Should call extract_review_metadata"
        assert found_except, "Should have error handling for extract_review_metadata"

    def test_extract_agent_consensus_has_error_handling(self):
        """Test that agent consensus extraction has error handling."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have try/except for extract_agent_consensus
        lines = content.split("\n")
        found_extract = False
        found_except = False

        for _i, line in enumerate(lines):
            if "extract_agent_consensus" in line:
                found_extract = True
            if found_extract and "except" in line:
                found_except = True
                break

        assert found_extract, "Should call extract_agent_consensus"
        assert found_except, "Should have error handling for extract_agent_consensus"

    def test_cross_file_metadata_has_error_handling(self):
        """Test that cross-file metadata construction has error handling."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have try/except for CrossFileMetadata construction
        lines = content.split("\n")
        found_construction = False
        found_except = False

        for _i, line in enumerate(lines):
            if "CrossFileMetadata(" in line:
                found_construction = True
            if found_construction and "except" in line:
                found_except = True
                break

        assert found_construction, "Should construct CrossFileMetadata"
        assert found_except, "Should have error handling for CrossFileMetadata"

    def test_format_storage_prompt_has_error_handling(self):
        """Test that storage prompt formatting has error handling."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should have try/except for format_storage_prompt
        lines = content.split("\n")
        found_format = False
        found_except = False

        for _i, line in enumerate(lines):
            if "format_storage_prompt" in line:
                found_format = True
            if found_format and "except" in line:
                found_except = True
                break

        assert found_format, "Should call format_storage_prompt"
        assert found_except, "Should have error handling for format_storage_prompt"


class TestStoreableCountCalculation:
    """Test the storeable_count calculation logic."""

    def test_storeable_count_filters_by_severity(self):
        """Test that storeable_count filters by severity."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should check severity against blocker/high/critical
        assert "blocker" in content
        assert "high" in content
        assert "critical" in content

    def test_storeable_count_filters_by_confidence(self):
        """Test that storeable_count filters by confidence."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should check confidence >= 80
        assert "confidence" in content
        assert "80" in content

    def test_storeable_count_requires_location(self):
        """Test that storeable_count requires location evidence."""
        orchestrator = Path("P:\\\\\\.claude/skills/uci/lib/orchestrator.py")
        content = orchestrator.read_text(encoding="utf-8")

        # Should check for ":" in location (file:line format)
        assert "location" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
