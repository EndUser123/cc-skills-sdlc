---
name: code-flow-visualizer
description: Convert code to Mermaid flowchart for understanding logic flow.
version: 1.0.0
status: stable
category: visualization
---

# Code Flow Visualizer

Convert code into Mermaid flowchart representation for understanding code logic flow.

## Features

- Analyze code logic structure
- Generate Mermaid flowcharts
- Supports Python, JavaScript, TypeScript

## Usage

When the user says "visualize code" or "generate flowchart", use this skill.

## Examples

```
User: Generate a flowchart for this Python function
Assistant: (use code_flow_visualizer skill)
```

## Tools

Use Mermaid JS or PlantUML to generate diagrams.

## Limitations

- Processes only single function/method
- Does not support goto statements
- Complex loops may be simplified
