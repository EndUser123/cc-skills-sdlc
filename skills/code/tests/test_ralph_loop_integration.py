#!/usr/bin/env python3
"""Tests for Ralph Loop Auto-Detection Integration - RED phase (failing tests)."""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.task_detector import (
        TaskDetectionResult,
        TaskType,
        detect_task_type,
        log_detection_decision,
    )

    TASK_DETECTOR_AVAILABLE = True
except ImportError:
    TASK_DETECTOR_AVAILABLE = False
    detect_task_type = None
    log_detection_decision = None
    TaskDetectionResult = None
    TaskType = None


class TestRalphLoopIntegration:
    """Test Ralph Loop auto-detection integration in /code skill - NEW FUNCTIONALITY."""

    def test_ralph_loop_flags_in_argument_hint(self):
        """Ralph Loop flags should be present in argument-hint."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            lines = []
            in_frontmatter = False
            for line in f:
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                        continue
                    else:
                        break
                if in_frontmatter:
                    lines.append(line)

        frontmatter_text = "".join(lines)
        frontmatter = yaml.safe_load(frontmatter_text)

        argument_hint = frontmatter.get("argument-hint", "")

        # Check for auto-detection flag
        assert (
            "--loop-ralph-auto" in argument_hint
        ), "argument-hint should include --loop-ralph-auto flag"

        # Check for override flags
        assert (
            "--ralph-enable" in argument_hint
        ), "argument-hint should include --ralph-enable override flag"

        assert (
            "--ralph-disable" in argument_hint
        ), "argument-hint should include --ralph-disable override flag"

    def test_ralph_auto_detection_documentation_exists(self):
        """Ralph Loop auto-detection should be documented in skill content."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for auto-detection section
        assert (
            "Ralph Loop Auto-Detection" in content
        ), "Skill should document Ralph Loop Auto-Detection feature"

        # Check for keyword lists
        assert (
            "Implementation tasks" in content
        ), "Documentation should list implementation keywords"

        assert "Research tasks" in content, "Documentation should list research keywords"

    def test_ralph_override_flags_documented(self):
        """Ralph Loop override flags should be documented."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for override flag documentation
        assert "--ralph-enable" in content, "Documentation should explain --ralph-enable flag"

        assert "--ralph-disable" in content, "Documentation should explain --ralph-disable flag"

        assert (
            "Force enable" in content
        ), "Documentation should explain --ralph-enable forces enable"

        assert (
            "Force disable" in content
        ), "Documentation should explain --ralph-disable forces disable"

    def test_ralph_usage_examples_exist(self):
        """Ralph Loop auto-detection should have usage examples."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for example code blocks
        assert "```bash" in content, "Documentation should have bash code examples"

        # Check for auto-detect examples
        assert "Auto-detect" in content, "Documentation should show auto-detect usage"

        # Check for override examples
        assert (
            "Manual override" in content or "override" in content.lower()
        ), "Documentation should show manual override usage"

    def test_ralph_evidence_logging_documented(self):
        """Ralph Loop evidence logging should be documented."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for evidence logging documentation
        assert "evidence" in content.lower(), "Documentation should mention evidence logging"

        assert ".evidence" in content, "Documentation should specify evidence file location"

        assert (
            "ralph_auto_detection.md" in content
        ), "Documentation should specify evidence filename"

    def test_ralph_integration_with_detector_module(self):
        """Integration should use task_detector module."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        # Verify detector module exists
        module_path = Path(__file__).parent.parent / "lib" / "task_detector.py"
        assert module_path.exists(), "task_detector module should exist for integration"

        # Verify detect_task_type function is callable
        assert callable(detect_task_type), "detect_task_type should be a callable function"

    def test_ralph_task_type_detection_works(self):
        """Task type detection should correctly identify implementation vs research tasks."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        # Test implementation task (should enable Ralph Loop)
        impl_result = detect_task_type("implement user authentication")
        assert (
            impl_result.enable_ralph_loop is True
        ), "Implementation tasks should enable Ralph Loop"

        # Test research task (should disable Ralph Loop)
        research_result = detect_task_type("research authentication patterns")
        assert (
            research_result.enable_ralph_loop is False
        ), "Research tasks should disable Ralph Loop"

    def test_ralph_confidence_scores_valid(self):
        """Detection confidence scores should be in valid range."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        assert 0.0 <= result.confidence <= 1.0, "Confidence scores must be between 0 and 1"

    def test_ralph_reasoning_provided(self):
        """Detection should provide reasoning for decision."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        assert result.reasoning, "Detection result should include reasoning"
        assert len(result.reasoning) > 0, "Reasoning should not be empty"


class TestTaskDetection:
    """Test task type detection logic - NEW FUNCTIONALITY."""

    def test_implementation_task_detection_basic(self):
        """Implementation tasks should be detected correctly."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement user authentication")

        assert result.task_type == TaskType.IMPLEMENTATION, "Should detect IMPLEMENTATION task type"
        assert result.enable_ralph_loop is True, "Implementation tasks should enable Ralph Loop"
        assert result.confidence >= 0.6, "Implementation detection should have moderate confidence"

    def test_research_task_detection_basic(self):
        """Research tasks should be detected correctly."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("research authentication patterns")

        assert result.task_type == TaskType.RESEARCH, "Should detect RESEARCH task type"
        assert result.enable_ralph_loop is False, "Research tasks should disable Ralph Loop"
        assert result.confidence >= 0.6, "Research detection should have moderate confidence"

    def test_ambiguous_query_defaults_to_research(self):
        """Ambiguous queries (no clear keywords) should default to research."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("tell me about the project structure")

        assert result.task_type == TaskType.RESEARCH, "Ambiguous queries should default to RESEARCH"
        assert (
            result.enable_ralph_loop is False
        ), "Ambiguous queries should disable Ralph Loop (safer default)"
        assert result.confidence < 0.6, "Ambiguous queries should have low confidence"

    def test_multiple_implementation_keywords(self):
        """Queries with multiple implementation keywords should still detect correctly."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement and refactor authentication module")

        assert (
            result.task_type == TaskType.IMPLEMENTATION
        ), "Should detect IMPLEMENTATION even with multiple keywords"
        assert (
            result.enable_ralph_loop is True
        ), "Multiple implementation keywords should enable Ralph Loop"

    def test_multiple_research_keywords(self):
        """Queries with multiple research keywords should still detect correctly."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("research and analyze existing patterns")

        assert (
            result.task_type == TaskType.RESEARCH
        ), "Should detect RESEARCH even with multiple keywords"
        assert (
            result.enable_ralph_loop is False
        ), "Multiple research keywords should disable Ralph Loop"

    def test_mixed_keywords_tie_defaults_to_research(self):
        """Tied keywords should default to research (safer default)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        # "implement" (impl) vs "analyze" (research) → tie defaults to research
        result = detect_task_type("implement and then analyze the feature")

        assert result.task_type == TaskType.RESEARCH, "Tie should default to RESEARCH (safer)"
        assert result.enable_ralph_loop is False, "Tie should disable Ralph Loop (safer default)"
        assert result.confidence < 0.6, "Tie should have low confidence"

    def test_mixed_keywords_research_wins(self):
        """More research keywords than implementation should disable Ralph Loop."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        # "document" (research) vs "implement" (impl) → research wins
        result = detect_task_type("document and implement the feature")

        assert result.task_type == TaskType.RESEARCH, "Research keywords should dominate"
        assert result.enable_ralph_loop is False, "More research keywords should disable Ralph Loop"


class TestObservabilityLogging:
    """Test observability logging for Ralph Loop auto-detection - NEW FUNCTIONALITY."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_log_detection_decision_function_exists(self):
        """log_detection_decision function should exist."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        assert callable(
            log_detection_decision
        ), "log_detection_decision should be a callable function"

    def test_log_detection_creates_evidence_file(self):
        """Logging should create .evidence/ralph_auto_detection.md file."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        assert evidence_file.exists(), "Evidence file should be created"
        assert (
            evidence_file.name == "ralph_auto_detection.md"
        ), "Evidence file should be named ralph_auto_detection.md"

    def test_log_detection_contains_query(self):
        """Evidence file should contain original query."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        query = "implement user authentication system"
        result = detect_task_type(query)
        evidence_file = log_detection_decision(
            result=result,
            query=query,
            project_root=self.project_root,
        )

        content = evidence_file.read_text()
        assert query in content, "Evidence should contain original query"

    def test_log_detection_contains_task_type(self):
        """Evidence file should contain detected task type."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        content = evidence_file.read_text()
        assert (
            "Task Type:" in content or "task_type" in content
        ), "Evidence should contain task type field"
        assert result.task_type.value in content, "Evidence should contain detected task type value"

    def test_log_detection_contains_ralph_loop_decision(self):
        """Evidence file should contain Ralph Loop enabled/disabled decision."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        content = evidence_file.read_text()
        assert (
            "Ralph Loop:" in content or "ralph_loop" in content
        ), "Evidence should contain Ralph Loop decision field"
        # Check for ENABLED/DISABLED text
        assert ("ENABLED" in content and result.enable_ralph_loop) or (
            "DISABLED" in content and not result.enable_ralph_loop
        ), "Evidence should correctly state if Ralph Loop is enabled or disabled"

    def test_log_detection_contains_confidence(self):
        """Evidence file should contain confidence score."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        content = evidence_file.read_text()
        assert (
            "Confidence:" in content or "confidence" in content
        ), "Evidence should contain confidence field"
        # Check for confidence value (should be 0.70)
        assert (
            "0.70" in content or f"{result.confidence:.2f}" in content
        ), "Evidence should contain confidence score value"

    def test_log_detection_contains_reasoning(self):
        """Evidence file should contain detection reasoning."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        content = evidence_file.read_text()
        assert (
            "Reasoning:" in content or "reasoning" in content
        ), "Evidence should contain reasoning field"
        assert result.reasoning in content, "Evidence should contain detection reasoning text"

    def test_log_detection_appends_to_existing_file(self):
        """Logging should append to existing evidence file with separator."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        # Log first detection
        result1 = detect_task_type("implement feature X")
        log_detection_decision(
            result=result1,
            query="implement feature X",
            project_root=self.project_root,
        )

        # Log second detection
        result2 = detect_task_type("research patterns")
        log_detection_decision(
            result=result2,
            query="research patterns",
            project_root=self.project_root,
        )

        evidence_file = self.project_root / ".evidence" / "ralph_auto_detection.md"
        content = evidence_file.read_text()

        # Check for separator
        assert "---" in content, "Should have separator between entries"

        # Check both queries are present
        assert "implement feature X" in content, "First query should be in evidence"
        assert "research patterns" in content, "Second query should be in evidence"

    def test_log_detection_returns_file_path(self):
        """log_detection_decision should return Path to evidence file."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        assert isinstance(evidence_file, Path), "Should return Path object"
        assert evidence_file.exists(), "Returned path should point to existing file"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
