"""
Test suite for ToT (Tree-of-Thought) branch generation for Phase 8 (TRACE).

These tests verify that the ToT tracer can correctly:
- Generate branching reasoning patterns (2-3 branches per step)
- Score branches (sure/maybe/unlikely)
- Prune to high-value branches
- Track branch hierarchy
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from tot_tracer import BranchGenerator

# Test fixtures


@pytest.fixture
def sample_trace_scenario() -> str:
    """Sample code trace scenario for branching"""
    return """
def process_user_request(user_id, request_data):
    # Step 1: Validate user
    if not user_exists(user_id):
        return error('User not found')

    # Step 2: Check permissions
    if not has_permission(user_id, 'write'):
        return error('Permission denied')

    # Step 3: Process request
    result = process_data(request_data)
    return success(result)
"""


@pytest.fixture
def simple_linear_trace() -> str:
    """Simple linear trace with no branching"""
    return """
def add_numbers(a, b):
    result = a + b
    return result
"""


@pytest.fixture
def conditional_trace() -> str:
    """Trace with conditional branches"""
    return """
def handle_request(request):
    if request.method == 'GET':
        return handle_get(request)
    elif request.method == 'POST':
        return handle_post(request)
    else:
        return error('Method not allowed')
"""


@pytest.fixture
def nested_branching_trace() -> str:
    """Trace with nested branching logic"""
    return """
def process_payment(user, amount):
    # Branch 1: Check user balance
    if user.balance < amount:
        if user.has_credit:
            return use_credit(user, amount)
        else:
            return error('Insufficient funds')
    else:
        # Branch 2: Check fraud detection
        if is_suspicious(user, amount):
            return hold_for_review(user, amount)
        else:
            return process_directly(user, amount)
"""


# Tests


def test_generate_branches_for_linear_trace(simple_linear_trace):
    """Test that linear traces generate minimal branches"""
    generator = BranchGenerator(simple_linear_trace)

    branches = generator.generate_branches()

    # Linear code should generate at least 1 branch (the main path)
    assert len(branches) >= 1

    # All branches should have IDs
    for branch in branches:
        assert "id" in branch
        assert "description" in branch
        assert "score" in branch


def test_generate_branches_for_conditional_trace(conditional_trace):
    """Test that conditional traces generate 2-3 branches per decision point"""
    generator = BranchGenerator(conditional_trace)

    branches = generator.generate_branches()

    # Should generate branches for GET, POST, and else paths
    assert len(branches) >= 2

    # Each branch should have valid structure
    for branch in branches:
        assert "id" in branch
        assert "description" in branch
        assert "score" in branch
        assert branch["score"] in ["sure", "maybe", "unlikely"]


def test_generate_branches_for_nested_traces(nested_branching_trace):
    """Test that nested branching generates hierarchical branches"""
    generator = BranchGenerator(nested_branching_trace)

    branches = generator.generate_branches()

    # Should generate branches for balance check and fraud detection
    assert len(branches) >= 2

    # Check that branch hierarchy is tracked
    for branch in branches:
        if "parent_id" in branch:
            assert branch["parent_id"] in [b["id"] for b in branches]


def test_branch_scoring_classification(conditional_trace):
    """Test that branches are scored as sure/maybe/unlikely"""
    generator = BranchGenerator(conditional_trace)

    branches = generator.generate_branches()

    # At least one branch should have a score
    scored_branches = [b for b in branches if b.get("score")]
    assert len(scored_branches) >= 1

    # All scores should be valid
    valid_scores = {"sure", "maybe", "unlikely"}
    for branch in branches:
        if "score" in branch:
            assert branch["score"] in valid_scores


def test_branch_pruning_removes_unlikely_branches():
    """Test that pruning removes 'unlikely' scored branches"""
    generator = BranchGenerator("dummy code")

    branches = [
        {"id": "b_1", "description": "Main path", "score": "sure", "parent_id": None},
        {"id": "b_2", "description": "Edge case", "score": "maybe", "parent_id": None},
        {"id": "b_3", "description": "Rare error", "score": "unlikely", "parent_id": None},
        {"id": "b_4", "description": "Another path", "score": "sure", "parent_id": "b_1"},
    ]

    pruned = generator.prune_branches(branches)

    # Should remove 'unlikely' branches
    pruned_ids = [b["id"] for b in pruned]
    assert "b_1" in pruned_ids
    assert "b_2" in pruned_ids
    assert "b_3" not in pruned_ids  # Unlikely branch pruned
    assert "b_4" in pruned_ids


def test_branch_pruning_preserves_hierarchy():
    """Test that pruning maintains parent-child relationships"""
    generator = BranchGenerator("dummy code")

    branches = [
        {"id": "b_1", "description": "Main path", "score": "sure", "parent_id": None},
        {"id": "b_2", "description": "Sub-branch", "score": "sure", "parent_id": "b_1"},
        {"id": "b_3", "description": "Another sub", "score": "unlikely", "parent_id": "b_1"},
    ]

    pruned = generator.prune_branches(branches)

    # Should preserve b_2 (child of b_1, sure score)
    pruned_ids = [b["id"] for b in pruned]
    assert "b_1" in pruned_ids
    assert "b_2" in pruned_ids
    assert "b_3" not in pruned_ids  # Unlikely branch pruned


def test_generate_2_to_3_branches_per_decision(conditional_trace):
    """Test that each decision point generates 2-3 branches"""
    generator = BranchGenerator(conditional_trace)

    branches = generator.generate_branches()

    # The conditional trace has if/elif/else (3 separate conditionals)
    # Each generates 2 branches (true/false), total 5-6 branches
    assert 2 <= len(branches) <= 6  # Allow flexibility for different conditional types


def test_branch_description_quality(conditional_trace):
    """Test that branches have meaningful descriptions"""
    generator = BranchGenerator(conditional_trace)

    branches = generator.generate_branches()

    for branch in branches:
        # Descriptions should not be empty
        assert branch["description"]
        assert len(branch["description"]) > 0

        # Descriptions should mention the path taken
        assert any(
            keyword in branch["description"].lower()
            for keyword in ["path", "branch", "case", "if", "else", "then"]
        )


def test_branch_ids_are_unique(nested_branching_trace):
    """Test that each branch has a unique ID"""
    generator = BranchGenerator(nested_branching_trace)

    branches = generator.generate_branches()

    branch_ids = [b["id"] for b in branches]

    # All IDs should be unique
    assert len(branch_ids) == len(set(branch_ids))


def test_handle_empty_trace():
    """Test that empty traces are handled gracefully"""
    generator = BranchGenerator("")

    branches = generator.generate_branches()

    # Should return empty list or single branch
    assert isinstance(branches, list)


def test_handle_trace_without_branching(simple_linear_trace):
    """Test that traces without branching still generate at least one branch"""
    generator = BranchGenerator(simple_linear_trace)

    branches = generator.generate_branches()

    # Linear code should still generate at least the main path branch
    assert len(branches) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
