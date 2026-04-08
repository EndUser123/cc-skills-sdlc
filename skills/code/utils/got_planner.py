"""
Graph-of-Thought (GoT) Planner for Phase 4 (PLAN) enhancement.

Extracts nodes (constraints, ideas, risks) from plan.md architecture sections
and analyzes relationships between them (supports, contradicts, unrelated).
"""

import re
from typing import Dict, List, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class Node:
    """Represents a node in the thought graph."""
    id: str
    text: str
    category: str  # 'constraint', 'idea', 'risk'
    source_line: int


@dataclass
class Edge:
    """Represents a relationship between two nodes."""
    from_node: str
    to_node: str
    relationship: str  # 'supports', 'contradicts', 'unrelated'
    reasoning: str


class GotPlanner:
    """
    Graph-of-Thought planner for architecture analysis.

    Extracts nodes from plan.md and analyzes relationships between them.
    """

    # Keywords that indicate different node categories
    CONSTRAINT_KEYWORDS = ['must', 'shall', 'required', 'mandatory', 'constraint', 'standard']
    IDEA_KEYWORDS = ['implement', 'add', 'create', 'use', 'build', 'design', 'approach']
    RISK_KEYWORDS = ['risk', 'failure', 'issue', 'problem', 'concern', 'may', 'could']

    # Keywords that indicate relationships
    SUPPORTS_KEYWORDS = ['enables', 'supports', 'allows', 'facilitates', 'helps', 'improves']
    CONTRADICTS_KEYWORDS = ['conflicts', 'incompatible', 'cannot', 'prevents', 'blocks', 'vs']

    def __init__(self, plan_content: str):
        """
        Initialize GoT planner with plan content.

        Args:
            plan_content: Full text of plan.md file
        """
        self.plan_content = plan_content
        self.lines = plan_content.split('\n')

    def extract_nodes(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract nodes from plan.md architecture section.

        Returns:
            Dict with keys: 'constraints', 'ideas', 'risks'
            Each value is a list of node dicts with 'id', 'text', 'source_line'
        """
        nodes = {
            'constraints': [],
            'ideas': [],
            'risks': []
        }

        # Find architecture section
        in_architecture = False
        current_subsection = None

        for line_num, line in enumerate(self.lines, start=1):
            stripped = line.strip()

            # Check for architecture section
            if re.match(r'^##+\s*Architecture', stripped, re.IGNORECASE):
                in_architecture = True
                continue

            # Exit architecture section at next major section (## but not ### subsections)
            if in_architecture and re.match(r'^##\s+', stripped) and not re.match(r'^##\s*Architecture', stripped, re.IGNORECASE):
                break

            if not in_architecture:
                continue

            # Check for subsections
            if re.match(r'^###+\s+Constraints?', stripped, re.IGNORECASE):
                current_subsection = 'constraints'
                continue
            elif re.match(r'^###+\s+Ideas?', stripped, re.IGNORECASE):
                current_subsection = 'ideas'
                continue
            elif re.match(r'^###+\s+Risks?', stripped, re.IGNORECASE):
                current_subsection = 'risks'
                continue

            # Extract list items
            if current_subsection and stripped.startswith('-'):
                node_text = stripped[1:].strip()
                if node_text:
                    node = Node(
                        id=self._generate_node_id(current_subsection, len(nodes[current_subsection]) + 1),
                        text=node_text,
                        category=current_subsection.rstrip('s'),  # Remove plural 's'
                        source_line=line_num
                    )
                    nodes[current_subsection].append({
                        'id': node.id,
                        'text': node.text,
                        'source_line': node.source_line
                    })

            # Handle free-form text (not in subsection, not a list item, not empty)
            elif in_architecture and stripped and not stripped.startswith('#'):
                # Skip non-node text (filler, placeholders, etc.)
                skip_patterns = [
                    'no specific', 'none', 'tbd', 'todo', 'n/a', 'not documented',
                    'to be determined', 'to be decided', 'decisions documented'
                ]
                stripped_lower = stripped.lower()
                if any(pattern in stripped_lower for pattern in skip_patterns):
                    continue

                # Classify the node based on content
                category = self._classify_node(stripped)

                node = Node(
                    id=self._generate_node_id(category, len(nodes[category]) + 1),
                    text=stripped,
                    category=category.rstrip('s'),  # Remove plural 's'
                    source_line=line_num
                )
                nodes[category].append({
                    'id': node.id,
                    'text': node.text,
                    'source_line': node.source_line
                })

        return nodes

    def _classify_node(self, text: str) -> str:
        """
        Classify a node into constraint, idea, or risk based on keywords.

        Args:
            text: Node text to classify

        Returns:
            'constraints', 'ideas', or 'risks'
        """
        text_lower = text.lower()

        # Check for risk keywords first (most specific)
        if any(keyword in text_lower for keyword in self.RISK_KEYWORDS):
            return 'risks'

        # Check for constraint keywords
        if any(keyword in text_lower for keyword in self.CONSTRAINT_KEYWORDS):
            return 'constraints'

        # Default to idea
        return 'ideas'

    def _generate_node_id(self, category: str, index: int) -> str:
        """
        Generate a unique node ID.

        Args:
            category: Node category ('constraints', 'ideas', 'risks')
            index: Node index within category

        Returns:
            Node ID (e.g., 'c_1', 'i_1', 'r_1')
        """
        prefix_map = {
            'constraints': 'c',
            'constraint': 'c',
            'ideas': 'i',
            'idea': 'i',
            'risks': 'r',
            'risk': 'r'
        }
        prefix = prefix_map.get(category.lower(), 'n')
        return f"{prefix}_{index}"


class GotEdgeAnalyzer:
    """
    Graph-of-Thought edge analyzer for relationship detection.

    Analyzes relationships between nodes and detects circular dependencies.
    """

    def __init__(self, nodes: Dict[str, List[Dict[str, Any]]]):
        """
        Initialize edge analyzer with extracted nodes.

        Args:
            nodes: Node dictionary from GotPlanner.extract_nodes()
        """
        self.nodes = nodes

    def analyze_edges(self) -> List[Dict[str, Any]]:
        """
        Analyze relationships between nodes.

        Returns:
            List of edge dicts with 'from_node', 'to_node', 'relationship', 'reasoning'
        """
        edges = []

        # Flatten all nodes into a single list
        all_nodes = []
        for category, node_list in self.nodes.items():
            all_nodes.extend(node_list)

        # Analyze pairwise relationships
        for i, node_a in enumerate(all_nodes):
            for node_b in all_nodes[i+1:]:
                edge = self._analyze_relationship(node_a, node_b)
                if edge:
                    edges.append(edge)

        return edges

    def _analyze_relationship(self, node_a: Dict[str, Any], node_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze relationship between two nodes.

        Args:
            node_a: First node
            node_b: Second node

        Returns:
            Edge dict or None if no clear relationship
        """
        text_a = node_a['text'].lower()
        text_b = node_b['text'].lower()

        # Check for contradiction indicators
        if self._check_contradiction(text_a, text_b):
            return {
                'from_node': node_a['id'],
                'to_node': node_b['id'],
                'relationship': 'contradicts',
                'reasoning': f"Contradictory requirements between {node_a['id']} and {node_b['id']}"
            }

        # Check for support indicators
        if self._check_support(text_a, text_b):
            return {
                'from_node': node_a['id'],
                'to_node': node_b['id'],
                'relationship': 'supports',
                'reasoning': f"{node_a['id']} enables {node_b['id']}"
            }

        # Check reverse support
        if self._check_support(text_b, text_a):
            return {
                'from_node': node_b['id'],
                'to_node': node_a['id'],
                'relationship': 'supports',
                'reasoning': f"{node_b['id']} enables {node_a['id']}"
            }

        # No clear relationship
        return None

    def _check_contradiction(self, text_a: str, text_b: str) -> bool:
        """Check if two texts contain contradictory keywords."""
        # Simple heuristic: check for opposite technologies or approaches
        contradiction_pairs = [
            ('postgresql', 'mysql'),
            ('serverless', 'rds'),
            ('jwt', 'session'),
            ('oauth', 'basic auth'),
            ('redis', 'memcached'),
        ]

        for term1, term2 in contradiction_pairs:
            if term1 in text_a and term2 in text_b:
                return True
            if term2 in text_a and term1 in text_b:
                return True

        return False

    def _check_support(self, text_a: str, text_b: str) -> bool:
        """Check if text_a supports text_b."""
        # Simple heuristic: check for enabling relationships
        support_patterns = [
            (r'\bredis\b', r'\bcach'),
            (r'\bjwt\b', r'\bsession'),
            (r'\boauth\b', r'\blogin'),
            (r'\brate limit\b', r'\bbrute force'),
        ]

        for pattern1, pattern2 in support_patterns:
            if re.search(pattern1, text_a) and re.search(pattern2, text_b):
                return True

        return False

    def detect_cycles(self, edges: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Detect circular dependencies in the graph.

        Args:
            edges: List of edge dictionaries

        Returns:
            List of cycles (each cycle is a list of node IDs)
        """
        # Build adjacency list
        graph = defaultdict(list)
        for edge in edges:
            if edge['relationship'] in ['supports', 'contradicts']:
                graph[edge['from_node']].append(edge['to_node'])

        # Detect cycles using DFS
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        # Run DFS from each node
        all_nodes = set()
        for edge in edges:
            all_nodes.add(edge['from_node'])
            all_nodes.add(edge['to_node'])

        for node in all_nodes:
            if node not in visited:
                dfs(node)

        return cycles

    def break_cycles(self, cycles: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Break detected cycles by removing weakest edges.

        Args:
            cycles: List of cycles to break

        Returns:
            List of cycle-breaking decisions with reasoning
        """
        decisions = []

        for cycle in cycles:
            # Strategy: Remove the last edge in the cycle
            # (heuristic: later edges are often downstream dependencies)
            if len(cycle) >= 2:
                removed_edge = (cycle[-2], cycle[-1])
                decisions.append({
                    'removed_edge': {
                        'from_node': removed_edge[0],
                        'to_node': removed_edge[1]
                    },
                    'reasoning': f"Weakest link in cycle detected between {removed_edge[0]} and {removed_edge[1]}"
                })

        return decisions


if __name__ == '__main__':
    # Example usage
    sample_plan = """
# Implementation Plan

## Architecture

### Constraints
- Must use JWT tokens for session management
- Database must be PostgreSQL (company standard)
- API response time < 200ms (SLA requirement)

### Ideas
- Implement OAuth 2.0 for third-party login
- Use Redis for token caching
- Add rate limiting to prevent brute force attacks

### Risks
- JWT secret key management is critical
- OAuth integration may introduce latency
"""

    planner = GotPlanner(sample_plan)
    nodes = planner.extract_nodes()

    print("Extracted Nodes:")
    for category, node_list in nodes.items():
        print(f"\n{category.title()}:")
        for node in node_list:
            print(f"  {node['id']}: {node['text']}")

    analyzer = GotEdgeAnalyzer(nodes)
    edges = analyzer.analyze_edges()

    print("\nEdges:")
    for edge in edges:
        print(f"  {edge['from_node']} --[{edge['relationship']}]--> {edge['to_node']}")
        print(f"    Reasoning: {edge['reasoning']}")
