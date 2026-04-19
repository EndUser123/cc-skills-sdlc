#!/usr/bin/env python3
"""Code map visualization wrapper for codemap."""

from __future__ import annotations

from typing import Any


class CodeMapVisualizer:
    """
    Visualization wrapper for existing codemap infrastructure.

    Takes the codemap from enhance_command.create_codemap() and
    generates visual, director-friendly representations.
    """

    def __init__(self, codemap: dict[str, Any]):
        self.codemap = codemap

    def generate_layer_view(self) -> str:
        """
        Generate layered architecture view from codemap.

        Returns:
            ASCII art or markdown showing layers (presentation/business/data)
        """
        layers = self._extract_layers()
        return self._format_layers_ascii(layers)

    def generate_dependency_graph(self) -> str:
        """
        Generate dependency graph from codemap.relationships.

        Returns:
            ASCII art or mermaid-compatible graph showing dependencies
        """
        relationships = self.codemap.get("relationships", {})
        return self._format_dependencies(relationships)

    def generate_test_heatmap(self, test_results: dict) -> str:
        """
        Overlay test results on codemap structure.

        Args:
            test_results: Test execution results per module

        Returns:
            Visual heatmap showing test coverage by module
        """
        file_structure = self.codemap.get("file_structure", {})
        return self._format_test_heatmap(file_structure, test_results)

    def _extract_layers(self) -> dict[str, list[str]]:
        """Extract architectural layers from codemap file structure."""
        layers = {
            "presentation": [],
            "business": [],
            "data": [],
            "infrastructure": [],
        }

        file_structure = self.codemap.get("file_structure", {})
        all_files = (
            file_structure.get("main_files", [])
            + file_structure.get("test_files", [])
            + file_structure.get("help_files", [])
        )

        for file_path in all_files:
            path_lower = file_path.lower()
            if any(keyword in path_lower for keyword in ("ui", "view", "present", "interface")):
                layers["presentation"].append(file_path)
            elif any(keyword in path_lower for keyword in ("service", "business", "logic", "domain")):
                layers["business"].append(file_path)
            elif any(keyword in path_lower for keyword in ("data", "model", "repository", "storage")):
                layers["data"].append(file_path)
            elif any(keyword in path_lower for keyword in ("infra", "config", "util")):
                layers["infrastructure"].append(file_path)

        return layers

    def _format_layers_ascii(self, layers: dict[str, list[str]]) -> str:
        """Format layers as ASCII art box diagram."""
        lines = ["## Layer Architecture View", ""]

        for layer_name, files in layers.items():
            if files:
                lines.append(f"### {layer_name.title()} Layer")
                for file_path in files[:5]:
                    lines.append(f"- {file_path}")
                if len(files) > 5:
                    lines.append(f"- ... and {len(files) - 5} more")
                lines.append("")

        return "\n".join(lines)

    def _format_dependencies(self, relationships: dict) -> str:
        """Format dependency graph."""
        lines = ["## Dependency Graph", ""]
        lines.append("```mermaid")
        lines.append("graph TD")

        python_imports = relationships.get("python_imports", {})

        for module, imports in python_imports.items():
            for imp in imports[:5]:  # Limit to 5 imports per module
                lines.append(f"    {module.replace('/', '_').replace('.', '_')} --> {imp.replace('/', '_').replace('.', '_')}")

        lines.append("```")
        return "\n".join(lines)

    def _format_test_heatmap(self, file_structure: dict, test_results: dict) -> str:
        """Format test coverage heatmap."""
        lines = ["## Test Coverage Heatmap", ""]

        for file_path in file_structure.get("main_files", [])[:10]:
            coverage = test_results.get(file_path, {}).get("coverage_percent", 0)
            emoji = "🟢" if coverage >= 80 else "🟡" if coverage >= 50 else "🔴"
            lines.append(f"{emoji} {file_path}: {coverage:.1f}%")

        return "\n".join(lines)
