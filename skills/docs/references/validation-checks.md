# Validation Checks Reference

## Circular References

**Detection**: Files A and B reference each other with "See [other file]" patterns, both under 50 lines of substantive content.

**Why This Matters**: Circular stub files create navigation traps. Users clicking between references never find substantive content.

**Fix**: Expand one file to include the actual content, remove the reference from the other.

**Example**:
```
BAD: a.md (10 lines): "See b.md for details"
BAD: b.md (10 lines): "See a.md for overview"

GOOD: a.md (100 lines): Full documentation with complete details
GOOD: b.md: Removed or merged into a.md
```

## Incomplete Content

**Detection**: File under 50 lines contains "See [other-file]" reference without substantive content.

**Why This Matters**: Stub files violate progressive disclosure. Users must load multiple files to get complete information.

**Fix**: Include essential content in the main file. Move auxiliary details to references/ only if truly optional.

**Example**:
```
BAD: guide.md (17 lines): "See full-guide.md for complete workflow"

GOOD: guide.md (200 lines): Complete workflow overview with key steps
   -> See references/advanced.md for edge cases and optimization
```

## Version Conflicts

**Detection**: Documentation references outdated versions (v5.1) in current codebase (v5.2+).

**Why This Matters**: Outdated documentation confuses users and causes failed conversions or migrations.

**Fix**: Update version references, archive old documentation, or add version-specific notices.

**Example**:
```
BAD: "This guide is for v5.1" (in v5.2 codebase)

GOOD: "This guide is for v5.2+"
GOOD: Archive: .archive/v5.1/legacy-guide.md
```

## Broken Cross-References

**Detection**: "See [file](path.md)" references point to non-existent files.

**Why This Matters**: Broken links create dead ends. Users cannot access referenced information.

**Fix**: Create missing files, update references to existing files, or remove stale references.

**Example**:
```
BAD: "See [advanced guide](advanced.md)" (advanced.md doesn't exist)

GOOD: "See [advanced guide](references/advanced.md)" (file exists)
GOOD: Or remove reference if content not critical
```

## Best Practices

### Progressive Disclosure

Keep SKILL.md lean (~1,500-2,000 words). Move detailed content to references/:

```
SKILL.md: Core workflow and essential steps
references/advanced.md: Edge cases and optimization
references/examples.md: Real-world usage examples
```

### Substantive Content Threshold

Minimum 50 lines of substantive content for files that reference other documentation. Substantive content excludes:
- Frontmatter
- Blank lines
- Section headers
- Reference lists

### Version Tracking

Always include version in documentation:
- Code examples: Specify compatible version
- Migration guides: Source and target versions
- API references: Version introduction/removal

## Troubleshooting

**False Positives**: If validation flags non-issues:
- Check file actually meets substantive content threshold
- Verify "See X" reference pattern isn't inline explanation
- Review version context (intentional legacy references)

**Missing Issues**: If validation doesn't catch obvious problems:
- Ensure target directory includes all documentation files
- Check file extensions are .md or .SKILL.md
- Verify DocumentationValidator has access to file system

**Import Errors**: If DocumentationValidator import fails:
- Confirm /package skill exists in skills directory
- Check Python path includes /package skill location
- Verify validate_docs.py exists in /package/resources/
