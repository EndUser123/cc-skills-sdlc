# Output Format and Usage Examples

## Output Format

```json
{
  "context": "# Meta-Review Analysis: mypackage\n...",
  "findings": [
    {
      "analyzer": "path_traversal",
      "type": "taint_flow",
      "severity": "HIGH",
      "message": "User input flows to filesystem sink without validation",
      "file_path": "src/handler.py"
    }
  ],
  "token_usage": {
    "budget": 8000,
    "used": 2341,
    "remaining": 5659
  }
}
```

## Integration Points

### `/package` PHASE 4.5

Meta-review is automatically integrated into `/package` validation:

```python
# In /package PHASE 4.5:
from lib.meta_review.prepare_context import prepare_agent_context
from lib.analysis_unit import create_analysis_unit

unit_id = create_analysis_unit(Path("{{TARGET_DIR}}"))
context = prepare_agent_context(unit_id, perspective="all", max_tokens=8000)

# Run code review plugin + meta-review
Skill(skill="code-review:code-review", args="{{TARGET_DIR}}")
# Meta-review runs in parallel
```

### `/p` PHASE 4.5

Meta-review is also integrated into `/p` Python package validation.

## Example Usage

### Basic Security Review

```python
from lib.meta_review.prepare_context import prepare_agent_context

# Create analysis unit from package directory
unit_id = create_analysis_unit(Path("src/myapp"))

# Run security analysis
context = prepare_agent_context(unit_id, perspective="security", max_tokens=8000)

# Review findings
for finding in context["findings"]:
    if finding["severity"] == "HIGH":
        print(f"HIGH: {finding['message']}")
        print(f"  File: {finding.get('file_path', 'unknown')}")
```

### Custom Layering Policy

```python
from lib.analysis_unit.analyzers.import_graph import ImportGraphAnalyzer

# Define layering rules
layering_policy = {
    "layers": {
        "models": ["models/**/*.py"],
        "controllers": ["controllers/**/*.py"],
        "views": ["views/**/*.py"]
    },
    "rules": [
        {"from": "models", "cannot_import": "controllers"},
        {"from": "models", "cannot_import": "views"},
        {"from": "controllers", "cannot_import": "views"}
    ]
}

analyzer = ImportGraphAnalyzer()
result = analyzer.analyze(manifest, layering_policy=layering_policy)
```
