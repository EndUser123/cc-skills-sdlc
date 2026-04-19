# Analyzer API Reference

## Step 1: Analysis Unit Creation

```python
from lib.analysis_unit import create_analysis_unit

unit_id = create_analysis_unit(Path("/path/to/package"))
# Returns: analysis unit ID (e.g., "pkg-20260310-abc123")
```

## Step 2: Analyzer Execution

### Path Traversal Analyzer (Security)

```python
from lib.analysis_unit.analyzers.path_traversal import PathTraversalAnalyzer

analyzer = PathTraversalAnalyzer()
result = analyzer.analyze(manifest)

# Returns:
# {
#   "findings": [...],
#   "cfg": {...},
#   "dfg": {...},
#   "sources": [...],
#   "sinks": [...],
#   "summary": {...}
# }
```

### Import Graph Analyzer (Architecture/Performance)

```python
from lib.analysis_unit.analyzers.import_graph import ImportGraphAnalyzer

analyzer = ImportGraphAnalyzer()
result = analyzer.analyze(manifest, layering_policy=None)

# Returns:
# {
#   "findings": [...],
#   "graph": {...},
#   "summary": {...}
# }
```

### Doc Consistency Analyzer (Quality)

```python
from lib.analysis_unit.analyzers.doc_consistency import DocConsistencyAnalyzer

analyzer = DocConsistencyAnalyzer(manifest)
findings = analyzer.analyze()

# Returns: List of findings
```

## Step 3: Perspective-Based Review

```python
from lib.meta_review.prepare_context import prepare_agent_context

# Security perspective (path traversal)
context = prepare_agent_context(unit_id, perspective="security", max_tokens=8000)

# Performance perspective (import graph)
context = prepare_agent_context(unit_id, perspective="performance", max_tokens=8000)

# Quality perspective (doc consistency)
context = prepare_agent_context(unit_id, perspective="quality", max_tokens=8000)

# Architecture perspective (import graph + layering)
context = prepare_agent_context(unit_id, perspective="architecture", max_tokens=8000)

# All perspectives
context = prepare_agent_context(unit_id, perspective="all", max_tokens=16000)
```
