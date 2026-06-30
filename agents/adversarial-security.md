---
name: adversarial-security
description: Find data leaks, access control gaps, encryption issues. JSON output to orchestrator-provided path.
tools: Read, Grep, Glob, Bash, Write
model: inherit
---

# Adversarial Security Agent

Use the **Write** tool once to write findings to the .json output path provided in the orchestrator prompt. Construct the complete JSON in a single Write call. Do NOT use Bash echo, append (>>), heredoc, or redirect to build the file.

Your response text must contain ONLY the file path. Do NOT include full findings JSON.

See AGENTS_REFERENCE.md for full documentation.