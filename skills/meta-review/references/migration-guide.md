# Migration Guide

## From `//p`

**Old way**:
```
//p
```

**New way**:
```
/meta-review quality
```

What you get:
- All doc consistency checks from /p
- PLUS: Import graph analysis
- PLUS: Cross-file validation

## From `/`ruff` (automatic) + `/p``

**Old way**:
```
/`ruff` (automatic) + `/p` src/myfile.py
```

**New way**:
```
/meta-review security
```

What you get:
- Path traversal detection (taint propagation)
- Import graph for async patterns
- Cross-file async bug detection

## From `/code-standards`

**Old way**:
```
/code-standards
```

**New way**:
```
/meta-review quality
```

What you get:
- Documentation consistency
- Import graph validation
- Cross-file standard compliance
