# Memory Integration (CKS Cross-Session Learning)

UCI integrates with the Constitutional Knowledge System (CKS) for cross-session learning.

## Enhanced Metadata Schema

Three dataclasses capture structured metadata for CKS storage:

### AgentConsensus

(`.claude/skills/uci/lib/memory_integration.py`)

- `confirming_agents`: List of agents that confirmed the finding
- `dissenting_agents`: List of agents that disagreed
- `consensus_level`: unanimous, majority, minority, or none
- `avg_confidence`: Average confidence across confirming agents
- `location_agreement`: Whether agents agree on the same file:line location

### CrossFileMetadata

(`.claude/skills/uci/lib/memory_integration.py`)

- `import_graph_nodes`: Count of nodes in the import graph
- `import_graph_edges`: Count of edges in the import graph
- `circular_dependencies`: List of detected circular dependencies
- `taint_paths`: List of data flow taint paths
- `hot_spots`: List of highly imported/central modules

### ReviewMetadata

(`.claude/skills/uci/lib/memory_integration.py`)

- `mode`: Review mode (triage/standard/deep/comprehensive)
- `file_count`: Number of files reviewed
- `line_count`: Total lines of code reviewed
- `languages`: List of programming languages detected
- `primary_language`: Primary language of the codebase
- `session_id`: Unique session identifier
- `timestamp`: ISO timestamp of the review
- `git_scope`: Git diff scope (branch, commit, PR)
- `branch`: Git branch name
- `file_types`: Dict mapping file extensions to counts

## Storeable Findings Calculation

Findings are stored in CKS only when they meet quality thresholds:
- **Severity**: blocker, high, or critical only
- **Confidence**: >= 80% threshold
- **Location**: Must have `file:line` format evidence

## Cross-Session Learning Loop

1. **Before review**: `retrieve_context()` queries CKS for similar findings
2. **During review**: Agents receive context about past findings
3. **After review**: High-confidence findings stored with enhanced metadata
4. **Future sessions**: Query CKS to retrieve enriched findings

## Implementation

- **Module**: `.claude/skills/uci/lib/memory_integration.py`
- **Integration**: `.claude/skills/uci/lib/orchestrator.py`
- **Tests**: `.claude/skills/uci/tests/test_enhanced_metadata.py`
