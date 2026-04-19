---
name: staging-protocol
description: Required staging protocol for complex file modifications via bash.
version: "1.0.0"
status: stable
category: operations
triggers:
  - 'bash file write'
  - 'heredoc'
  - 'python -c'
  - 'complex file modification'
aliases:
  - '/staging'
suggest:
  - /research
---

## Code Editing Patterns

For Python code editing patterns and anti-patterns:
- **Authority**: /p Neural Cache
- **Example**: `/search "ThreadPoolExecutor KeyboardInterrupt immediate cleanup"`
- **Example**: `/search "string manipulation AST LibCST code editing"`

Reflect automatically propagates code editing learnings to /p. Query CKS for patterns.


## Purpose

For file modifications >10 lines or containing special characters, use staging to avoid corruption from shell escaping issues.

## PROHIBITED Execution Patterns

- `python -c "..."` with embedded multiline strings
- `sed` with complex regex substitution patterns
- Bash heredocs (`cat << EOF`)
- `echo -e` with escape sequences

## REASON

Shell escaping complexity exceeds reliable handling. Creates Tier 4 evidence ceiling—cannot verify what actually executed.

## CONSEQUENCE

Subtle corruption that manifests as "mysterious" bugs later. Debugging time far exceeds time saved by direct writes.

## REQUIRED: Staging Protocol

For any file modification >10 lines or containing special characters:

1. **Write** complete content to staging: `P:/__csf/.staging/<descriptive_name>.<ext>`
2. **Verify** file was written correctly:
   ```bash
   head -10 P:/__csf/.staging/<filename>
   tail -10 P:/__csf/.staging/<filename>
   wc -l P:/__csf/.staging/<filename>
   ```
3. **Only after verification:** move/copy to destination
4. **Clean up** staging file after successful deployment

**Staging directory:** `P:/__csf/.staging/` (auto-created if needed)

## SCOPE

- **Applies to:** bash_tool file writes, multi-line edits via shell
- **Does NOT apply to:** Write tool, Edit tool, str_replace (these handle escaping correctly)
- **Permitted:** Simple one-liners (`echo "single line" > file`)

## Trigger

Activate when:
- Writing files >10 lines via bash
- Using heredocs, python -c, or sed with complex patterns
- File contains special characters (quotes, escapes, unicode)
- Previous file writes had corruption issues
