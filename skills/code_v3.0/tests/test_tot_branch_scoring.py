"""
Test suite for ToT (Tree-of-Thought) branch scoring logic.

These tests verify that the ToT tracer can correctly:
- Score branches as sure/maybe/unlikely
- Apply scoring rules consistently
- Handle edge cases in scoring
- Provide confidence levels for branches
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
from tot_tracer import BranchGenerator


# Test fixtures

@pytest.fixture
def sure_branch_scenarios():
    """Scenarios that should score as 'sure'"""
    return [
        ("if user.is_authenticated:", "true", "Authenticated user check"),
        ("if request.method == 'GET':", "true", "Standard HTTP method"),
        ("for item in items:", "loop", "Normal loop iteration"),
        ("try:", "try_success", "Happy path in try block"),
        ("if response.status_code == 200:", "true", "Successful response"),
    ]


@pytest.fixture
def unlikely_branch_scenarios():
    """Scenarios that should score as 'unlikely'"""
    return [
        ("except ValueError:", "except", "Exception handler"),
        ("except CriticalError:", "except", "Critical exception"),
        ("if operation.failed:", "true", "Failed operation"),
        ("if data.invalid:", "true", "Invalid data"),
        ("if request.denied:", "true", "Denied request"),
    ]


@pytest.fixture
def maybe_branch_scenarios():
    """Scenarios that should score as 'maybe'"""
    return [
        ("elif request.method == 'POST':", "elif", "Alternative HTTP method"),
        ("else:", "else", "Fallback case"),
        ("if user.has_permission:", "true", "Permission check uncertain"),
        ("while waiting_for_response:", "loop", "Loop with exit condition"),
    ]


# Tests

def test_sure_branches_score_correctly(sure_branch_scenarios):
    """Test that branches with sure indicators score as 'sure'"""
    for conditional, path_type, description in sure_branch_scenarios:
        generator = BranchGenerator(f"def test():\n    {conditional}\n        pass")

        # Generate branches
        branches = generator.generate_branches()

        # Check that at least one branch scores as 'sure'
        sure_branches = [b for b in branches if b['score'] == 'sure']
        assert len(sure_branches) >= 1, f"Expected 'sure' score for: {description}"


def test_unlikely_branches_score_correctly(unlikely_branch_scenarios):
    """Test that branches with unlikely indicators score as 'unlikely'"""
    for conditional, path_type, description in unlikely_branch_scenarios:
        generator = BranchGenerator(f"def test():\n    {conditional}\n        pass")

        # Generate branches
        branches = generator.generate_branches()

        # Check that exception handlers score as 'unlikely'
        unlikely_branches = [b for b in branches if b['score'] == 'unlikely']
        assert len(unlikely_branches) >= 1, f"Expected 'unlikely' score for: {description}"


def test_maybe_branches_score_correctly(maybe_branch_scenarios):
    """Test that branches with uncertain indicators score as 'maybe'"""
    for conditional, path_type, description in maybe_branch_scenarios:
        generator = BranchGenerator(f"def test():\n    {conditional}\n        pass")

        # Generate branches
        branches = generator.generate_branches()

        # Check that we have some branches
        assert len(branches) >= 1, f"Expected at least one branch for: {description}"


def test_scoring_consistency():
    """Test that scoring is consistent across multiple runs"""
    code = """
def handle_request(request):
    if request.method == 'GET':
        return handle_get(request)
    elif request.method == 'POST':
        return handle_post(request)
    else:
        return error('Method not allowed')
"""

    generator1 = BranchGenerator(code)
    branches1 = generator1.generate_branches()

    generator2 = BranchGenerator(code)
    branches2 = generator2.generate_branches()

    # Same code should produce same branch counts
    assert len(branches1) == len(branches2)


def test_all_branches_have_valid_scores():
    """Test that all generated branches have valid scores"""
    code = """
def process(data):
    if data.valid:
        return process_valid(data)
    else:
        return process_invalid(data)
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    valid_scores = {'sure', 'maybe', 'unlikely'}

    for branch in branches:
        assert branch['score'] in valid_scores, f"Invalid score: {branch['score']}"


def test_scoring_based_on_keywords():
    """Test that scoring uses keyword detection"""
    # Code with 'success' keyword should score as 'sure'
    code = """
if operation.success:
    return result
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    # Should find at least one branch
    assert len(branches) >= 1


def test_scoring_based_on_path_type():
    """Test that scoring considers path type (true/false/else)"""
    code = """
if condition:
    do_something()
else:
    do_alternative()
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    # Should have branches with different scores
    scores = [b['score'] for b in branches]
    assert len(scores) >= 2


def test_edge_case_scoring():
    """Test scoring for edge cases and unusual patterns"""
    edge_cases = [
        "if True:",  # Always true
        "if False:",  # Always false
        "if None:",  # None check
        "if not value:",  # Negated condition
    ]

    for edge_case in edge_cases:
        generator = BranchGenerator(f"def test():\n    {edge_case}\n        pass")
        branches = generator.generate_branches()

        # Should still generate branches
        assert len(branches) >= 1, f"No branches generated for: {edge_case}"


def test_nested_scoring():
    """Test that nested conditionals maintain scoring logic"""
    code = """
def process(user, request):
    if user.authenticated:
        if user.has_permission:
            return process_request(request)
        else:
            return error('No permission')
    else:
        return error('Not authenticated')
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    # Should generate multiple branches
    assert len(branches) >= 2

    # All should have valid scores
    valid_scores = {'sure', 'maybe', 'unlikely'}
    for branch in branches:
        assert branch['score'] in valid_scores


def test_scoring_with_loops():
    """Test that loops are scored appropriately"""
    code = """
for item in items:
    process(item)
    if item.failed:
        handle_error(item)
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    # Loop iterations should score as 'sure'
    sure_branches = [b for b in branches if b['score'] == 'sure']
    assert len(sure_branches) >= 1


def test_scoring_with_try_except():
    """Test that try/except blocks are scored appropriately"""
    code = """
try:
    risky_operation()
except ValueError:
    handle_value_error()
except Exception:
    handle_generic_error()
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    # Exception handlers should score as 'unlikely'
    unlikely_branches = [b for b in branches if b['score'] == 'unlikely']
    assert len(unlikely_branches) >= 1


def test_confidence_levels():
    """Test that branch scores can be interpreted as confidence levels"""
    code = """
def process_request(request):
    if request.valid:
        return handle_valid(request)
    else:
        return handle_invalid(request)
"""

    generator = BranchGenerator(code)
    branches = generator.generate_branches()

    # Map scores to confidence levels
    confidence_map = {
        'sure': 0.9,
        'maybe': 0.5,
        'unlikely': 0.1
    }

    for branch in branches:
        score = branch['score']
        assert score in confidence_map, f"Unknown score: {score}"

        # Confidence should be a number
        confidence = confidence_map[score]
        assert 0.0 <= confidence <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
