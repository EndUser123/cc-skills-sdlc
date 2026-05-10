# AID Integration (v1.1.0)

**Documentation generation via AI Distiller (AID):**

```bash
# Generate documentation for single file
aid <file> --ai-action prompt-for-single-file-docs

# Generate documentation for multiple files
aid <directory> --ai-action flow-for-multi-file-docs
```

**AID documentation generation provides:**
- **Single File Docs**: Comprehensive documentation with examples
- **Multi-File Docs**: Documentation workflow for file relationships
- **API References**: Function signatures, parameters, return types
- **Usage Examples**: Practical code examples
- **Architecture Notes**: Design patterns and relationships

**When to use AID for documentation:**
- New module documentation (single-file docs)
- API reference generation (multi-file docs)
- Legacy code documentation (automated discovery)
- Documentation updates after refactoring (sync with code)

**Integration module**: `$CLAUDE_ROOT/skills\arch\aid_integration.py`
