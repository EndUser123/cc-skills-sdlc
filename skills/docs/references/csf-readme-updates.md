# CSF NIP Main README Updates

**Special case: $__CSF_ROOT/README.md**

When working in the CSF NIP codebase (`$__CSF_ROOT/`), the main project README serves as the central index for all documentation.

## When to Update $__CSF_ROOT/README.md

1. **Adding new top-level documentation** - Add link to "Documentation" section
2. **Creating new module READMEs** - Add to "Project Structure" if core module
3. **Significant new features** - Add to "Key Systems" section
4. **New configuration requirements** - Update "Configuration" section

## README Structure

```markdown
## Documentation
| Document | Description |
|----------|-------------|
| [Existing Doc](path/to/doc.md) | Description |
| [NEW DOC HERE](path/to/new.md) | New description |
```

## Automatic Update Pattern

When creating new documentation in `$__CSF_ROOT/`:

1. Create the document (e.g., `src/modules/new_module/README.md`)
2. **Immediately update** `$__CSF_ROOT/README.md` with:
   - Link in Documentation section (for docs)
   - Entry in Project Structure (for core modules)
   - Description in Key Systems (for major features)
3. Commit both files together

## Example

```bash
# After creating new documentation
/confirm "Created src/modules/observability/CONFIGURATION.md, updating main README"
# Edit $__CSF_ROOT/README.md to add link
/commit "Add system health configuration documentation"
```

## Documentation File Requirements

| File | Purpose | When Required |
|------|---------|---------------|
| `CLAUDE.md` | Module context for Claude Code | All code modules |
| `README.md` | General documentation for humans | All public packages |
| `$__CSF_ROOT/README.md` | **Main project index** | Update when adding docs to CSF NIP |
| `P:\\\\\\README.md` | **CSF documentation hub** | Update when adding major components |
| `P:\\\\\\packages\README.md` | **Packages catalog** | Update when adding new packages |
| `ARCHITECTURE.md` | System design and components | Complex systems |
| `CHANGELOG.md` | Version history | Libraries/packages |
| `API.md` | API reference | Libraries with external API |
| `DEVELOPING.md` | Development setup | Multi-contributor projects |
