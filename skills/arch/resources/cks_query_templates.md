# CKS Query Templates

**Standard CKS queries for template execution using the /search skill.**

## Template Integration

Templates use `/search` skill for CKS queries:

```python
# Within template execution context, CKS queries are:
/search "cks: {domain} FAILURE {symptom}" --backend cks
/search "cks: precedent {pattern}" --backend cks
/search "cks: constraint {domain} {metric}" --backend cks
```

## Query Patterns

### Domain-Specific Failures
```python
cks.search(f"{domain} FAILURE {failure_mode}")
```

### Performance Claims
```python
cks.search(f"{solution} performance benchmark {scale}")
```

### Pattern Advice
```python
cks.search(f"precedent {pattern} success failure rate")
```

### Team/Capacity Concerns
```python
cks.search(f"team velocity {feature_area} {team_size}")
```

### Historical Context
```python
cks.search(f"decision timeline {feature_area} years")
```

## IMPROVE_SYSTEM Path Queries

For the IMPROVE_SYSTEM workflow:

```python
# Search for subsystem-specific failures
/search "cks: {subsystem} {symptom}" --backend cks

# Search for pattern-level failures
/search "cks: {subsystem} failure" --backend cks

# Search for precedent decisions
/search "cks: precedent {pattern_name}" --backend cks
```

## Examples

```bash
# Search for hook-related failures
/search "cks: hook FAILURE race condition" --backend cks

# Search for caching precedents
/search "cks: precedent caching strategy" --backend cks

# Search for async performance
/search "cks: asyncio performance scalability" --backend cks
```

**Reference:** The CKS daemon provides backend support for these queries through the /search skill.
