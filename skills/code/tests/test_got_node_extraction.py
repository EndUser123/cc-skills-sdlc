"""
Test suite for GoT (Graph-of-Thought) node extraction from plan.md architecture sections.

These tests verify that the GoT planner can correctly extract:
- Constraints: Requirements and limitations
- Ideas: Proposed solutions and approaches
- Risks: Potential failure modes and concerns
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
from got_planner import GotPlanner


# Test fixtures

@pytest.fixture
def sample_plan_with_architecture() -> str:
    """Sample plan.md with architecture section containing nodes"""
    return """
# Implementation Plan

## Overview
Add user authentication to the application.

## Architecture

### Constraints
- Must use JWT tokens for session management
- Database must be PostgreSQL (company standard)
- API response time < 200ms (SLA requirement)

### Ideas
- Implement OAuth 2.0 for third-party login
- Use bcrypt for password hashing
- Add rate limiting to prevent brute force attacks

### Risks
- JWT secret key management is critical
- OAuth integration may introduce latency
- Rate limiting could block legitimate users
"""

@pytest.fixture
def sample_plan_minimal() -> str:
    """Minimal plan with sparse architecture"""
    return """
# Plan

## Architecture
Use PostgreSQL for data storage.
"""

@pytest.fixture
def sample_plan_empty_architecture() -> str:
    """Plan with empty architecture section"""
    return """
# Plan

## Architecture
*No specific architecture decisions documented*
"""


# Tests

def test_extract_constraints_from_sample_plan(sample_plan_with_architecture):
    """Test that constraints are correctly identified and extracted"""
    planner = GotPlanner(sample_plan_with_architecture)

    nodes = planner.extract_nodes()

    assert 'constraints' in nodes
    assert len(nodes['constraints']) == 3

    constraint_texts = [c['text'] for c in nodes['constraints']]
    assert 'Must use JWT tokens for session management' in constraint_texts
    assert 'Database must be PostgreSQL (company standard)' in constraint_texts
    assert 'API response time < 200ms (SLA requirement)' in constraint_texts

    # Verify metadata
    for constraint in nodes['constraints']:
        assert 'id' in constraint
        assert 'text' in constraint
        assert 'source_line' in constraint


def test_extract_ideas_from_sample_plan(sample_plan_with_architecture):
    """Test that ideas are correctly identified and extracted"""
    planner = GotPlanner(sample_plan_with_architecture)

    nodes = planner.extract_nodes()

    assert 'ideas' in nodes
    assert len(nodes['ideas']) == 3

    idea_texts = [i['text'] for i in nodes['ideas']]
    assert 'Implement OAuth 2.0 for third-party login' in idea_texts
    assert 'Use bcrypt for password hashing' in idea_texts
    assert 'Add rate limiting to prevent brute force attacks' in idea_texts


def test_extract_risks_from_sample_plan(sample_plan_with_architecture):
    """Test that risks are correctly identified and extracted"""
    planner = GotPlanner(sample_plan_with_architecture)

    nodes = planner.extract_nodes()

    assert 'risks' in nodes
    assert len(nodes['risks']) == 3

    risk_texts = [r['text'] for r in nodes['risks']]
    assert 'JWT secret key management is critical' in risk_texts
    assert 'OAuth integration may introduce latency' in risk_texts
    assert 'Rate limiting could block legitimate users' in risk_texts


def test_handle_minimal_plan(sample_plan_minimal):
    """Test that minimal plans with sparse architecture are handled"""
    planner = GotPlanner(sample_plan_minimal)

    nodes = planner.extract_nodes()

    # Should still return all three categories
    assert 'constraints' in nodes
    assert 'ideas' in nodes
    assert 'risks' in nodes

    # Should extract at least one idea (the PostgreSQL line)
    assert len(nodes['ideas']) >= 1
    assert any('PostgreSQL' in i['text'] for i in nodes['ideas'])


def test_handle_empty_architecture(sample_plan_empty_architecture):
    """Test that empty architecture sections are handled gracefully"""
    planner = GotPlanner(sample_plan_empty_architecture)

    nodes = planner.extract_nodes()

    # Should return empty lists, not fail
    assert nodes['constraints'] == []
    assert nodes['ideas'] == []
    assert nodes['risks'] == []


def test_node_ids_are_unique(sample_plan_with_architecture):
    """Test that each node has a unique ID"""
    planner = GotPlanner(sample_plan_with_architecture)

    nodes = planner.extract_nodes()

    all_nodes = nodes['constraints'] + nodes['ideas'] + nodes['risks']
    node_ids = [n['id'] for n in all_nodes]

    # All IDs should be unique
    assert len(node_ids) == len(set(node_ids))


def test_node_ids_follow_pattern(sample_plan_with_architecture):
    """Test that node IDs follow expected pattern (category_number)"""
    planner = GotPlanner(sample_plan_with_architecture)

    nodes = planner.extract_nodes()

    # Constraint IDs should start with 'c_'
    for constraint in nodes['constraints']:
        assert constraint['id'].startswith('c_')

    # Idea IDs should start with 'i_'
    for idea in nodes['ideas']:
        assert idea['id'].startswith('i_')

    # Risk IDs should start with 'r_'
    for risk in nodes['risks']:
        assert risk['id'].startswith('r_')


def test_source_lines_are_tracked(sample_plan_with_architecture):
    """Test that source line numbers are tracked for each node"""
    planner = GotPlanner(sample_plan_with_architecture)

    nodes = planner.extract_nodes()

    all_nodes = nodes['constraints'] + nodes['ideas'] + nodes['risks']

    for node in all_nodes:
        assert 'source_line' in node
        assert isinstance(node['source_line'], int)
        assert node['source_line'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
