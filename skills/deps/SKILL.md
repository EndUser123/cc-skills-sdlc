---
name: deps
description: Dependency management for TaskMaster projects - tracks dependencies, prevents breaking changes.
version: "1.0.0"
status: "stable"
category: utilities
triggers:
  - /deps
aliases:
  - /deps

suggest:
  - /build
  - /test
  - /comply
---

# /deps - Dependency Management

Simple dependency management for TaskMaster projects. Tracks which projects depend on others and prevents operations that would break dependencies.

## Purpose

Track dependencies between TaskMaster projects and prevent breaking changes.

## Project Context

### Constitution/Constraints
- Follows CLAUDE.md constitutional principles
- Solo-dev appropriate (Director + AI workforce model)
- Simple tracking (no complex DAG algorithms)
- On-demand only (no background services)

### Technical Context
- SQLite storage integrates with TaskMaster database
- Circular dependency detection
- Projects can have optional dependencies
- Visual dependency tree generation

### Architecture Alignment
- Part of TaskMaster project management
- Integrates with /build and /test workflows
- Supports /comply validation

## Your Workflow

1. Add dependency relationships with description
2. Check dependencies before operations
3. List dependents before removing projects
4. Visualize dependency tree for understanding
5. Remove dependencies when no longer needed

## Validation Rules

- Circular dependencies are prevented
- All dependencies must be verified before removal
- Optional dependencies should be marked appropriately
- SQLite storage must be maintained

## Usage

```bash
/deps <action> [options]
```

## Actions

### `add <dependent> <dependency> <description> [--optional]`
Add a dependency relationship between projects.

**Examples:**
```bash
/deps add my-project core-libraries "Requires core libraries to function"
/deps add ui-project backend-api "Depends on backend API endpoints" --optional
```

### `remove <dependent> <dependency>`
Remove a dependency relationship.

**Example:**
```bash
/deps remove my-project old-dependency
```

### `check <project_id>`
Check if all dependencies for a project are satisfied.

**Example:**
```bash
/deps check my-project
```

### `list <project_id>`
List all dependencies for a project.

**Example:**
```bash
/deps list my-project
```

### `dependents <project_id>`
List all projects that depend on this project.

**Example:**
```bash
/deps dependents core-libraries
```

### `visualize <project_id>`
Generate a text visualization of the dependency tree.

**Example:**
```bash
/deps visualize my-project
```

### `summary`
Show summary statistics about all dependencies.

**Example:**
```bash
/deps summary
```

## Features

- **Simple tracking**: No complex DAG algorithms, just basic dependency relationships
- **Circular dependency detection**: Prevents creating circular dependencies
- **On-demand only**: No background services or continuous monitoring
- **SQLite storage**: Integrates with existing TaskMaster database

## Examples

### Setting up a new project with dependencies
```bash
/deps add my-webapp user-auth "Requires user authentication system"
/deps add my-webapp database "Needs database connectivity"
/deps check my-webapp
/deps visualize my-webapp
```

### Before removing a project
```bash
# Check what depends on this project
/deps dependents old-project
```
