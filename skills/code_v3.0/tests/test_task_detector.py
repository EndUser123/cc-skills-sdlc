#!/usr/bin/env python3
"""Tests for Task Type Detection - RED phase (failing tests)."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import task detector module (doesn't exist yet - will cause import error)
try:
    from lib.task_detector import TaskDetectionResult, TaskType, detect_task_type

    TASK_DETECTOR_AVAILABLE = True
except ImportError:
    TASK_DETECTOR_AVAILABLE = False
    TaskType = None
    detect_task_type = None
    TaskDetectionResult = None


class TestTaskDetector:
    """Test task type detection - NEW FUNCTIONALITY."""

    def test_task_detector_module_exists(self):
        """Task detector module should exist."""
        module_path = Path(__file__).parent.parent / "__lib" / "task_detector.py"

        assert module_path.exists(), f"Task detector module should exist at {module_path}"

    def test_detect_task_type_function_exists(self):
        """detect_task_type function should exist and be callable."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        assert callable(detect_task_type), "detect_task_type should be a callable function"

    def test_detect_implementation_task(self):
        """Should detect implementation tasks (enable Ralph Loop)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        # Test implementation keywords
        result = detect_task_type("implement user authentication")

        assert result.task_type == TaskType.IMPLEMENTATION, "Should detect implementation task"
        assert result.enable_ralph_loop is True, "Implementation tasks should enable Ralph Loop"
        assert result.confidence > 0.5, "Should have moderate to high confidence"

    def test_detect_refactor_task(self):
        """Should detect refactor tasks (enable Ralph Loop)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("refactor authentication module")

        assert (
            result.task_type == TaskType.IMPLEMENTATION
        ), "Should detect implementation task for refactor"
        assert result.enable_ralph_loop is True, "Refactor tasks should enable Ralph Loop"

    def test_detect_fix_task(self):
        """Should detect fix tasks (enable Ralph Loop)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("fix login bug")

        assert (
            result.task_type == TaskType.IMPLEMENTATION
        ), "Should detect implementation task for fix"
        assert result.enable_ralph_loop is True, "Fix tasks should enable Ralph Loop"

    def test_detect_research_task(self):
        """Should detect research tasks (disable Ralph Loop)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("research authentication patterns")

        assert result.task_type == TaskType.RESEARCH, "Should detect research task"
        assert result.enable_ralph_loop is False, "Research tasks should disable Ralph Loop"

    def test_detect_analyze_task(self):
        """Should detect analyze tasks (disable Ralph Loop)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("analyze code structure")

        assert result.task_type == TaskType.RESEARCH, "Should detect research task for analyze"
        assert result.enable_ralph_loop is False, "Analyze tasks should disable Ralph Loop"

    def test_detect_document_task(self):
        """Should detect document tasks (disable Ralph Loop)."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("document API usage")

        assert result.task_type == TaskType.RESEARCH, "Should detect research task for document"
        assert result.enable_ralph_loop is False, "Document tasks should disable Ralph Loop"

    def test_confidence_score_range(self):
        """Confidence scores should be between 0 and 1."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task_detector module not available - expected for RED phase")

        result = detect_task_type("implement feature")

        assert 0.0 <= result.confidence <= 1.0, "Confidence score must be between 0 and 1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
