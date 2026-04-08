"""Test verify_plan_compliance.py - Plan compliance checker.

Tests the script that detects incomplete test coverage.
Related: unverified_stance_detector.py had 5/9 planned tests.
"""

import sys
from pathlib import Path

# Add parent scripts directory to path for import
# ruff: noqa: E402
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from verify_plan_compliance import extract_implemented_tests, extract_planned_tests


class TestExtractPlannedTests:
    """Test extraction of planned test counts from plan.md files."""

    def test_extract_from_numbered_strategy(self):
        """Extract count from numbered list in Test Strategy section."""
        plan_content = """## Overview

Test plan for feature X.

## Test Strategy

1. Test case one
2. Test case two
3. Test case three

## Implementation
"""
        plan_path = Path("/tmp/test_plan.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 3

    def test_extract_from_bold_format(self):
        """Extract count from bold test name format."""
        plan_content = """## Test Strategy

1. **test_validate_no_patterns**: Empty pattern list returns no issues
2. **test_validate_context_conflict**: Pattern matches context keyword
3. **test_extract_implemented_tests**: Count pytest functions

"""
        plan_path = Path("/tmp/test_plan.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 3

    def test_extract_from_bullet_format(self):
        """Extract count from bullet list test case format."""
        plan_content = """## Test Strategy

- test case 1: Verify basic functionality
- test case 2: Check error handling
- test case 3: Test edge cases
- test case 4: Integration test

"""
        plan_path = Path("/tmp/test_plan.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 4

    def test_extract_from_scenario_format(self):
        """Extract count from scenario keyword format."""
        plan_content = """## Test Strategy

1. Scenario: User login with valid credentials
2. Scenario: User login with invalid password
3. Scenario: User logout

"""
        plan_path = Path("/tmp/test_plan.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 3

    def test_extract_no_test_strategy(self):
        """Return 0 when no Test Strategy section found."""
        plan_content = """## Overview

Feature implementation plan.

## Architecture

System design description.
"""
        plan_path = Path("/tmp/test_plan.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 0

    def test_extract_empty_strategy(self):
        """Return 0 when Test Strategy section is empty."""
        plan_content = """## Test Strategy

## Implementation

Code goes here.
"""
        plan_path = Path("/tmp/test_plan.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 0

    def test_extract_missing_plan_file(self):
        """Raise FileNotFoundError when plan file doesn't exist."""
        plan_path = Path("/tmp/nonexistent_plan.md")

        try:
            extract_planned_tests(plan_path)
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError as e:
            assert "Plan not found" in str(e)


class TestExtractImplementedTests:
    """Test extraction of implemented test counts from test files."""

    def test_extract_pytest_functions(self):
        """Count standard pytest test functions."""
        test_content = '''"""Test module."""

def test_feature_one():
    """Test first feature."""
    assert True

def test_feature_two():
    """Test second feature."""
    assert True

def test_feature_three():
    """Test third feature."""
    assert True
'''
        test_path = Path("/tmp/test_module.py")
        test_path.write_text(test_content)

        count = extract_implemented_tests(test_path)
        assert count == 3

    def test_extract_class_based_tests(self):
        """Count test methods in test classes."""
        test_content = '''"""Test module with class-based tests."""

class TestFeature:
    def test_method_one(self):
        assert True

    def test_method_two(self):
        assert True

class TestAnotherFeature:
    def test_method_three(self):
        assert True
'''
        test_path = Path("/tmp/test_class.py")
        test_path.write_text(test_content)

        count = extract_implemented_tests(test_path)
        assert count == 3

    def test_extract_no_tests(self):
        """Return 0 for files with no test functions."""
        test_content = '''"""Module with no tests."""

def helper_function():
    pass

class NotATest:
    def regular_method(self):
        pass
'''
        test_path = Path("/tmp/no_tests.py")
        test_path.write_text(test_content)

        count = extract_implemented_tests(test_path)
        assert count == 0

    def test_extract_mixed_functions(self):
        """Count only test functions, ignore regular functions."""
        test_content = '''"""Mixed module."""

def regular_function():
    pass

def test_actual_test():
    assert True

def another_regular():
    pass

def test_second_test():
    assert True
'''
        test_path = Path("/tmp/mixed.py")
        test_path.write_text(test_content)

        count = extract_implemented_tests(test_path)
        assert count == 2

    def test_extract_missing_test_file(self):
        """Raise FileNotFoundError when test file doesn't exist."""
        test_path = Path("/tmp/nonexistent_test.py")

        try:
            extract_implemented_tests(test_path)
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError as e:
            assert "Test file not found" in str(e)


class TestComplianceIntegration:
    """Test compliance checking logic comparing planned vs implemented."""

    def test_compliance_pass_match(self):
        """Pass when planned count matches implemented count."""
        plan_content = """## Test Strategy

1. Test one
2. Test two
3. Test three
"""
        test_content = """
def test_one(): pass
def test_two(): pass
def test_three(): pass
"""
        plan_path = Path("/tmp/plan_match.md")
        test_path = Path("/tmp/test_match.py")
        plan_path.write_text(plan_content)
        test_path.write_text(test_content)

        planned = extract_planned_tests(plan_path)
        implemented = extract_implemented_tests(test_path)

        assert planned == 3
        assert implemented == 3
        assert planned == implemented

    def test_compliance_fail_mismatch(self):
        """Detect when implemented count doesn't match planned."""
        plan_content = """## Test Strategy

1. Test one
2. Test two
3. Test three
4. Test four
5. Test five
"""
        test_content = """
def test_one(): pass
def test_two(): pass
def test_three(): pass
"""
        plan_path = Path("/tmp/plan_mismatch.md")
        test_path = Path("/tmp/test_mismatch.py")
        plan_path.write_text(plan_content)
        test_path.write_text(test_content)

        planned = extract_planned_tests(plan_path)
        implemented = extract_implemented_tests(test_path)

        assert planned == 5
        assert implemented == 3
        assert planned != implemented
        assert planned - implemented == 2  # 2 missing tests

    def test_compliance_no_plan(self):
        """Handle case where plan file doesn't exist."""
        test_content = """
def test_one(): pass
def test_two(): pass
"""
        plan_path = Path("/tmp/nonexistent_plan.md")
        test_path = Path("/tmp/test_no_plan.py")
        test_path.write_text(test_content)

        try:
            extract_planned_tests(plan_path)
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError:
            pass  # Expected

    def test_compliance_no_test_file(self):
        """Handle case where test file doesn't exist."""
        plan_content = """## Test Strategy

1. Test one
2. Test two
"""
        plan_path = Path("/tmp/plan_no_test.md")
        test_path = Path("/tmp/nonexistent_test.py")
        plan_path.write_text(plan_content)

        try:
            extract_implemented_tests(test_path)
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError:
            pass  # Expected

    def test_compliance_zero_planned(self):
        """Handle case where plan has no detectable test count."""
        plan_content = """## Overview

Feature plan.

## Architecture

Design details.
"""
        test_content = """
def test_one(): pass
def test_two(): pass
"""
        plan_path = Path("/tmp/plan_zero.md")
        test_path = Path("/tmp/test_zero.md")
        plan_path.write_text(plan_content)
        test_path.write_text(test_content)

        planned = extract_planned_tests(plan_path)
        implemented = extract_implemented_tests(test_path)

        # When planned is 0, script assumes complete and passes
        assert planned == 0
        assert implemented == 2


class TestRealWorldScenarios:
    """Test with real-world plan and test file patterns."""

    def test_unverified_stance_detector_scenario(self):
        """Detect incomplete coverage like unverified_stance_detector.py bug."""
        # Real scenario: 5 tests implemented out of 9 planned
        plan_content = """## Test Strategy

Task: Implement unverified stance detector

1. test_pattern_issue_creation
2. test_pattern_issue_severity_levels
3. test_validate_no_patterns
4. test_validate_no_issues
5. test_validate_context_conflict_exact_match
6. test_validate_context_conflict_partial_match
7. test_validate_overmatching_common_words
8. test_validate_regex_syntax_error
9. test_validate_real_world_patterns
"""
        test_content = """
def test_pattern_issue_creation(): pass
def test_pattern_issue_severity_levels(): pass
def test_validate_no_patterns(): pass
def test_validate_context_conflict_exact_match(): pass
def test_validate_overmatching_common_words(): pass
"""
        plan_path = Path("/tmp/plan_incomplete.md")
        test_path = Path("/tmp/test_incomplete.py")
        plan_path.write_text(plan_content)
        test_path.write_text(test_content)

        planned = extract_planned_tests(plan_path)
        implemented = extract_implemented_tests(test_path)

        # This is the bug: 5/9 tests implemented
        assert planned == 9
        assert implemented == 5
        assert planned != implemented  # Should fail compliance check

    def test_complete_coverage_scenario(self):
        """Verify complete coverage scenario passes."""
        plan_content = """## Test Strategy

1. test_extract_planned_tests
2. test_extract_implemented_tests
3. test_compliance_check
"""
        test_content = """
def test_extract_planned_tests(): pass
def test_extract_implemented_tests(): pass
def test_compliance_check(): pass
"""
        plan_path = Path("/tmp/plan_complete.md")
        test_path = Path("/tmp/test_complete.py")
        plan_path.write_text(plan_content)
        test_path.write_text(test_content)

        planned = extract_planned_tests(plan_path)
        implemented = extract_implemented_tests(test_path)

        assert planned == 3
        assert implemented == 3
        assert planned == implemented  # Should pass compliance check


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_empty_plan_file(self):
        """Handle completely empty plan file."""
        plan_path = Path("/tmp/empty_plan.md")
        plan_path.write_text("")

        count = extract_planned_tests(plan_path)
        assert count == 0

    def test_empty_test_file(self):
        """Handle completely empty test file."""
        test_path = Path("/tmp/empty_test.py")
        test_path.write_text("")

        count = extract_implemented_tests(test_path)
        assert count == 0

    def test_plan_with_no_numbers(self):
        """Handle plan with text but no numbered lists."""
        plan_content = """## Test Strategy

We should test the following features:
- Login functionality
- Logout functionality
- User registration

But no numbered list format.
"""
        plan_path = Path("/tmp/plan_no_numbers.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        # Should fall back to matching test/scenario keywords
        # In this case, 0 because the format doesn't match patterns
        assert count == 0

    def test_test_with_other_def_patterns(self):
        """Only count test_ functions, not other def patterns."""
        test_content = """
def test_one(): pass
def setup_function(): pass
def teardown_function(): pass
def test_two(): pass
def helper_not_test(): pass
"""
        test_path = Path("/tmp/test_patterns.py")
        test_path.write_text(test_content)

        count = extract_implemented_tests(test_path)
        # Should only count test_ functions
        assert count == 2

    def test_multiline_plan_strategy(self):
        """Handle multi-line Test Strategy section."""
        plan_content = """## Test Strategy

This section describes the test approach.

We will test the following scenarios:

1. First test case
2. Second test case
3. Third test case

Additional notes here.
"""
        plan_path = Path("/tmp/plan_multiline.md")
        plan_path.write_text(plan_content)

        count = extract_planned_tests(plan_path)
        assert count == 3
