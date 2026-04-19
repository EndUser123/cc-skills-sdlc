---
name: dpef
version: "1.0.0"
status: "stable"
description: Deterministic Prompt Execution Framework - command template generation with gw.ask/gw.exec metadata
category: framework
triggers:
  - /dpef
aliases:
  - /dpef

suggest:
  - /prompt_refiner
  - /design
  - /build
---

# DPEF - Deterministic Prompt Execution Framework

Generate command templates and specs with gw.ask/gw.exec compatible metadata.

## Purpose

Generate command templates and specs with gw.ask/gw.exec compatible metadata for deterministic prompt execution.

## Project Context

### Constitution/Constraints
- Follows CLAUDE.md constitutional principles
- Solo-dev appropriate (Director + AI workforce model)
- Evidence-first instructions required
- Input quality gates for vague requests

### Technical Context
- Shared metadata standard for all commands
- Core fields: id, aliases, category, handles, orchestrator mode
- Optional fields: dependencies, quality_gates, completion_status
- gw.ask/gw.exec compatibility required

### Architecture Alignment
- Integrates with /prompt_refiner workflow
- Part of CSF NIP command generation tools
- Supports /design and /build

## Your Workflow

1. Identify command requirements
2. Generate YAML frontmatter with proper metadata
3. Define orchestrator mode and capabilities
4. Add quality gates if needed
5. Validate gw.ask/gw.exec compatibility

## Validation Rules

- Evidence-first instructions required
- Input quality gates for vague requests
- Clear error/refusal patterns
- Honest capabilities (no fictional behavior)
- gw.ask/gw.exec compatibility

## Quick Usage

```bash
/dpef "Create command for user management with validation"
```

## Shared Metadata Standard

### Core Fields (Required)

```yaml
---
id: unique-identifier
aliases: ["/command", "/alias"]
category: one-word-category
handles:
  - "primary keyword phrase"
orchestrator:
  mode: operation-mode
  plan_capable: boolean
  execute_capable: boolean
---
```

### Optional Fields

```yaml
# For complex commands
dependencies:
  required_tools: [list]
  required_files: [list]
  required_prompts: [list]

# For orchestration commands
quality_gates:
  gate_name: "requirement description"

# Production indicator
completion_status:
  current_level: "🟢🟢"

# Framework definitions
metadata_standard:
  standard_name: "description"
```

## Command Patterns

### Pattern 1: Minimal

```yaml
---
id: health
aliases: ["/health"]
category: health
handles: ["health", "status"]
orchestrator: {mode: health, plan_capable: true, execute_capable: true}
---
```

### Pattern 2: Integrated

```yaml
---
id: wo-advisory
aliases: ["/wo-advisory"]
category: advisory
handles: ["complex coordination"]
orchestrator: {mode: advisory, plan_capable: true, execute_capable: true}
dependencies:
  required_tools: ["Task", "AskUserQuestion"]
---
```

### Pattern 3: Production

```yaml
---
id: intel
aliases: ["/intel"]
category: research
handles: ["strategic intelligence"]
orchestrator: {mode: research, plan_capable: true, execute_capable: true}
completion_status:
  current_level: "🟢🟢"
---
```

## DPEF Capabilities

1. Generate command templates with proper metadata
2. Validate existing command metadata for gw.* compatibility
3. Convert scripts to gw.ask/gw.exec compatible commands
4. Create framework specifications
5. Provide quality validation for prompt suites

## Quality Gates

Generated commands MUST include:
- Evidence-first instructions
- Input quality gates for vague requests
- Clear error/refusal patterns
- gw.ask/gw.exec compatibility
- Honest capabilities (no fictional behavior)
