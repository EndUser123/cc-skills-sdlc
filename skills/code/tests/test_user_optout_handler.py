#!/usr/bin/env python3
"""Unit tests for user opt-out handler."""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.user_optout_handler import UserOptoutHandler


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    old_cwd = Path.cwd()

    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


class TestUserOptoutHandler:
    """Test user opt-out handler functionality."""

    def test_detects_opt_out_checkbox_when_checked(self, temp_project_dir):
        """
        Test that UserOptoutHandler detects checked opt-out checkbox in plan.md.

        Given: plan.md contains "- [x] Skip Modernization Considerations"
        When: should_skip_modernization() is called
        Then: Returns True (user has opted out)
        """
        # Arrange
        plan_content = """# Plan: Test Feature

## Modernization Considerations

- [x] Skip Modernization Considerations section

## Other Sections

Regular content here.
"""
        plan_file = temp_project_dir / "plan.md"
        plan_file.write_text(plan_content)

        handler = UserOptoutHandler(temp_project_dir)

        # Act
        result = handler.should_skip_modernization()

        # Assert
        assert result is True, "Should return True when opt-out checkbox is checked"

    def test_returns_false_when_opt_out_not_checked(self, temp_project_dir):
        """
        Test that UserOptoutHandler returns False when opt-out checkbox is unchecked.

        Given: plan.md contains "- [ ] Skip Modernization Considerations"
        When: should_skip_modernization() is called
        Then: Returns False (user has NOT opted out)
        """
        # Arrange
        plan_content = """# Plan: Test Feature

## Modernization Considerations

- [ ] Skip Modernization Considerations section

## Other Sections

Regular content here.
"""
        plan_file = temp_project_dir / "plan.md"
        plan_file.write_text(plan_content)

        handler = UserOptoutHandler(temp_project_dir)

        # Act
        result = handler.should_skip_modernization()

        # Assert
        assert result is False, "Should return False when opt-out checkbox is unchecked"

    def test_returns_false_when_opt_out_line_missing(self, temp_project_dir):
        """
        Test that UserOptoutHandler returns False when opt-out line is not in plan.md.

        Given: plan.md does NOT contain opt-out checkbox line
        When: should_skip_modernization() is called
        Then: Returns False (default behavior is to include modernization)
        """
        # Arrange
        plan_content = """# Plan: Test Feature

## Modernization Considerations

Some modernization content here.

## Other Sections

Regular content here.
"""
        plan_file = temp_project_dir / "plan.md"
        plan_file.write_text(plan_content)

        handler = UserOptoutHandler(temp_project_dir)

        # Act
        result = handler.should_skip_modernization()

        # Assert
        assert result is False, "Should return False when opt-out line is missing"

    def test_handles_missing_plan_md_gracefully(self, temp_project_dir):
        """
        Test that UserOptoutHandler handles missing plan.md gracefully.

        Given: plan.md does NOT exist in project directory
        When: should_skip_modernization() is called
        Then: Returns False (default behavior, no crash)
        """
        # Arrange
        # Don't create plan.md
        handler = UserOptoutHandler(temp_project_dir)

        # Act
        result = handler.should_skip_modernization()

        # Assert
        assert result is False, "Should return False when plan.md is missing (default behavior)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
