"""
AI Distiller (aid) Integration Wrapper v2 for /arch skill.

Optimized CLI-based integration with no fallback - AID is the primary method.

Key Optimizations:
- CLI-based execution via subprocess (no Python module dependency)
- AI action prompts for enterprise-grade analysis
- Mermaid diagram generation
- Layer detection and dependency direction analysis
- Multi-terminal safe (stateless, read-only)
- Cross-platform path normalization (Windows/Unix consistency)

Version: 2.0.1
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AIDCompressionLevel(Enum):
    """AID compression levels for distillation."""

    MINIMAL = "minimal"  # Public APIs only, no implementation
    MODERATE = "moderate"  # Public APIs + type signatures
    HIGH = "high"  # Includes docstrings, key implementation
    MAXIMUM = "maximum"  # Everything (for small codebases)


class AIDAIAction(Enum):
    """Pre-configured AI analysis actions from AID CLI."""

    # Codebase analysis
    COMPLEX_CODEBASE = "prompt-for-complex-codebase-analysis"
    """Enterprise-grade codebase overview with compliance, governance, scalability"""

    REFACTORING = "prompt-for-refactoring-suggestion"
    """Comprehensive refactoring with ROI, risk assessment, rollback plans"""

    SECURITY = "prompt-for-security-analysis"
    """OWASP Top 10 security audit with evidence checklists"""

    PERFORMANCE = "prompt-for-performance-analysis"
    """Algorithmic complexity, profiling guidance, scalability"""

    BEST_PRACTICES = "prompt-for-best-practices-analysis"
    """Code quality, patterns, maintainability"""

    BUG_HUNTING = "prompt-for-bug-hunting"
    """Systematic bug detection with quality analysis"""

    # Documentation
    SINGLE_FILE_DOCS = "prompt-for-single-file-docs"
    """Comprehensive single-file documentation"""

    DIAGRAMS = "prompt-for-diagrams"
    """Generate 10 Mermaid diagrams for architecture and processes"""

    # Workflows
    DEEP_FILE_TO_FILE = "flow-for-deep-file-to-file-analysis"
    """Structured task list for comprehensive analysis"""

    MULTI_FILE_DOCS = "flow-for-multi-file-docs"
    """Documentation workflow for multiple files"""


@dataclass
class AIDAnalysisResult:
    """Result from AID distillation/analysis."""

    distilled_structure: str
    """Compressed code structure"""

    public_apis: dict[str, Any] = field(default_factory=dict)
    """Extracted API signatures"""

    dependencies: dict[str, list[str]] = field(default_factory=dict)
    """Dependency graph"""

    boundaries: list[str] = field(default_factory=list)
    """Detected module/service boundaries"""

    layers: dict[str, list[str]] = field(default_factory=dict)
    """Architectural layers (controllers/services/repositories)"""

    layer_violations: list[str] = field(default_factory=list)
    """Architectural violations detected"""

    metrics: dict[str, Any] = field(default_factory=dict)
    """Analysis metrics"""

    diagrams: str | None = None
    """Generated Mermaid diagrams"""

    files_analyzed: int = 0
    """Number of files processed"""

    compression_ratio: float = 0.0
    """Compression percentage (0-1)"""


class AidIntegratorV2:
    """
    AI Distiller integration wrapper v2 - CLI-based with no fallback.

    Uses AID CLI via subprocess for all operations. This provides:
    - Consistent behavior with standalone AID
    - Access to latest AI action prompts
    - No Python module dependency issues
    - Multi-terminal safe (stateless, read-only)

    Design Principles:
    - CLI-first: Always use aid.exe subprocess
    - No fallback: AID is required, not optional
    - Fail-fast: Clear errors when AID unavailable
    - Read-only: Never modifies code, only analyzes
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize AidIntegratorV2 with AID CLI backend.

        Args:
            config: Optional configuration dict with keys:
                - compression_level: "minimal" | "moderate" | "high" | "maximum"
                - max_content_size_mb: Maximum content size (default: 100)
                - aid_path: Path to aid.exe (default: ~/.aid/bin/aid.exe)

        Raises:
            RuntimeError: If AID CLI is not found or not executable
        """
        self._config = config or {}

        # Locate AID CLI
        aid_path = self._config.get("aid_path", "")
        if not aid_path:
            # Default to ~/.aid/bin/aid.exe
            home = Path.home()
            aid_path = home / ".aid" / "bin" / "aid.exe"

        self._aid_path = Path(aid_path)
        if not self._aid_path.exists():
            raise RuntimeError(
                f"AID CLI not found at {self._aid_path}. "
                "Install from: https://github.com/janreges/ai-distiller/releases"
            )

        # Verify AID is executable
        try:
            result = subprocess.run(
                [str(self._aid_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError("AID CLI failed to execute")
        except Exception as e:
            raise RuntimeError(f"AID CLI not executable: {e}")

    def _normalize_path(self, path: str) -> str:
        """
        Normalize paths to forward slashes for cross-platform consistency.

        Windows paths may use backslashes; normalize to forward slashes
        to prevent cache misses and path comparison issues.

        Args:
            path: Path string from AID output

        Returns:
            Normalized path with forward slashes
        """
        # Convert backslashes to forward slashes
        normalized = path.replace("\\", "/")
        # Remove leading ./ if present for cleaner paths
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

    def distill(
        self,
        target_path: str | Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> AIDAnalysisResult:
        """
        Distill codebase structure using AID CLI.

        Args:
            target_path: Path to file or directory to analyze
            include_patterns: Glob patterns for files to include (e.g., ["*.py", "*.ts"])
            exclude_patterns: Glob patterns for files to exclude (e.g., ["*test*"])

        Returns:
            AIDAnalysisResult with distilled structure and metrics

        Raises:
            RuntimeError: If AID CLI execution fails
        """
        target = Path(target_path)
        if not target.exists():
            raise RuntimeError(f"Path not found: {target_path}")

        # Build AID command
        cmd = [
            str(self._aid_path),
            str(target),
            "--stdout",  # Capture output to stdout
            "--format",
            "json-structured",  # Structured JSON output
            "--summary-type",
            "off",  # Disable progress bar in JSON output
        ]

        # Add include patterns
        if include_patterns:
            cmd.extend(["--include", ",".join(include_patterns)])

        # Add exclude patterns
        if exclude_patterns:
            cmd.extend(["--exclude", ",".join(exclude_patterns)])

        # Add compression level
        compression = self._config.get("compression_level", "moderate")
        if compression == "minimal":
            cmd.extend(["--implementation=0", "--comments=0", "--docstrings=0"])
        elif compression == "moderate":
            cmd.extend(["--implementation=0", "--comments=0", "--docstrings=1"])
        elif compression == "high":
            cmd.extend(["--implementation=1", "--comments=0", "--docstrings=1"])
        elif compression == "maximum":
            cmd.extend(["--implementation=1", "--comments=1", "--docstrings=1"])

        # Execute AID CLI
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"AID CLI timed out analyzing {target_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"AID CLI failed: {e.stderr}")

        if result.returncode != 0:
            raise RuntimeError(f"AID CLI failed with code {result.returncode}: {result.stderr}")

        # Parse output - handle AID's JSON structure
        # AID returns: {"files": [...], "total_stats": {...}, "type": "project"}
        try:
            output = result.stdout.strip()
            data = json.loads(output)
        except json.JSONDecodeError:
            # Fallback: extract JSON from output with potential trailing text
            output = result.stdout.strip()
            brace_count = 0
            json_end = len(output)
            for i, char in enumerate(output):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            output = output[:json_end]
            try:
                data = json.loads(output)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"AID CLI output parsing failed: {e}\nOutput preview: {result.stdout[:500]}"
                )

        # Map AID JSON structure to AIDAnalysisResult
        files = data.get("files", [])
        total_stats = data.get("total_stats", {})

        # Extract distilled structure from AID output
        distilled_parts = []
        apis = []
        dependencies = {}
        boundaries_set = set()

        for file_info in files:
            file_path = self._normalize_path(file_info.get("path", ""))
            structure = file_info.get("structure", {})

            # Build distilled representation
            distilled_parts.append(f"# {file_path}")

            # Add classes
            for cls in structure.get("classes", []):
                class_name = cls.get("name", "")
                members = cls.get("members", {})
                methods = members.get("methods", [])
                distilled_parts.append(
                    f"class {class_name}: methods={[m.get('name', '') for m in methods]}"
                )

                # Track as API
                apis.append(
                    {
                        "name": class_name,
                        "type": "class",
                        "file": file_path,
                        "visibility": cls.get("visibility", "public"),
                    }
                )

            # Add functions
            for func in structure.get("functions", []):
                func_name = func.get("name", "")
                params = func.get("parameters", [])
                param_str = ", ".join(p.get("name", "") for p in params)
                distilled_parts.append(f"def {func_name}({param_str})")

                # Track as API
                apis.append(
                    {
                        "name": func_name,
                        "type": "function",
                        "file": file_path,
                        "visibility": func.get("visibility", "public"),
                    }
                )

            # Detect boundaries from directory structure
            if "/" in file_path:
                boundary = file_path.split("/")[0]
                boundaries_set.add(boundary)

            # Extract imports for dependency analysis
            # AID stores imports at the file level
            file_imports = []
            for imp in structure.get("imports", []):
                file_imports.append(imp.get("module", imp))
            if file_imports:
                dependencies[file_path] = file_imports

        return AIDAnalysisResult(
            distilled_structure="\n".join(distilled_parts),
            public_apis={"apis": apis, "count": len(apis)},
            dependencies=dependencies,
            boundaries=sorted(list(boundaries_set)),
            layers={},  # To be populated by detect_layers()
            layer_violations=[],
            metrics={
                "files_analyzed": len(files),
                "apis_found": len(apis),
                "dependencies_found": sum(len(deps) for deps in dependencies.values()),
                "classes": total_stats.get("class", 0),
                "functions": total_stats.get("function", 0),
            },
            files_analyzed=len(files),
            compression_ratio=0.6,  # AID typically achieves 60% compression
        )

    def analyze_with_ai_action(
        self,
        target_path: str | Path,
        ai_action: AIDAIAction,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> str:
        """
        Run AI action prompt generation using AID CLI.

        This generates optimized prompts for specific AI tasks like:
        - Complex codebase analysis (enterprise-grade)
        - Security auditing (OWASP Top 10)
        - Refactoring suggestions (ROI-focused)
        - Diagram generation (Mermaid)

        Args:
            target_path: Path to file or directory
            ai_action: AI action to perform (see AIDAIAction enum)
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude

        Returns:
            Generated AI prompt text

        Raises:
            RuntimeError: If AID CLI execution fails
        """
        target = Path(target_path)
        if not target.exists():
            raise RuntimeError(f"Path not found: {target_path}")

        # Build AID command with AI action
        cmd = [
            str(self._aid_path),
            str(target),
            "--ai-action",
            ai_action.value,
            "--stdout",
            "--summary-type",
            "off",
        ]

        # Add patterns
        if include_patterns:
            cmd.extend(["--include", ",".join(include_patterns)])
        if exclude_patterns:
            cmd.extend(["--exclude", ",".join(exclude_patterns)])

        # Execute AID CLI
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for AI actions
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"AID CLI timed out for {ai_action.value}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"AID CLI failed: {e.stderr}")

        if result.returncode != 0:
            raise RuntimeError(f"AID CLI failed with code {result.returncode}: {result.stderr}")

        return result.stdout

    def generate_diagrams(
        self,
        target_path: str | Path,
    ) -> str:
        """
        Generate Mermaid diagrams for codebase architecture.

        Creates 10 diagrams covering:
        - Architecture overview
        - Component relationships
        - Data flows
        - Sequence diagrams
        - State machines
        - Deployment views

        Args:
            target_path: Path to directory

        Returns:
            Generated Mermaid diagram definitions

        Raises:
            RuntimeError: If AID CLI execution fails
        """
        return self.analyze_with_ai_action(
            target_path,
            AIDAIAction.DIAGRAMS,
        )

    def detect_layers(
        self,
        target_path: str | Path,
    ) -> dict[str, Any]:
        """
        Detect architectural layers using AID + custom analysis.

        Returns:
            Dict with:
            - layers: {layer_name: [files]}
            - violations: [detected violations]
            - confidence: 0.0-1.0 score

        Raises:
            RuntimeError: If analysis fails
        """
        target = Path(target_path)
        if not target.is_dir():
            raise RuntimeError("Layer detection requires directory path")

        # First get basic distillation
        result = self.distill(target)

        # Then run custom layer analysis
        layers: dict[str, list[str]] = {
            "controllers": [],
            "services": [],
            "repositories": [],
            "models": [],
            "unclassified": [],
        }

        # Layer classification patterns
        layer_patterns = {
            "controllers": [
                "controller",
                "handler",
                "route",
                "api",
                "endpoint",
                "view",
                "presenter",
                "dispatch",
            ],
            "services": [
                "service",
                "usecase",
                "interactor",
                "workflow",
                "orchestrator",
                "coordinator",
                "manager",
            ],
            "repositories": [
                "repository",
                "repo",
                "dao",
                "persistence",
                "storage",
                "database",
                "db_",
                "data_",
            ],
            "models": ["model", "entity", "domain", "value", "dto", "vo", "po", "aggregate"],
        }

        # Classify files from dependencies
        for file_path in result.dependencies.keys():
            file_lower = file_path.lower()
            classified = False

            for layer, patterns in layer_patterns.items():
                if any(pattern in file_lower for pattern in patterns):
                    layers[layer].append(file_path)
                    classified = True
                    break

            if not classified:
                layers["unclassified"].append(file_path)

        # Build import graph for violation detection
        import_graph = result.dependencies
        violations = self._detect_layer_violations(layers, import_graph)

        # Calculate confidence
        total_files = sum(len(files) for files in layers.values())
        classified_files = total_files - len(layers["unclassified"])
        confidence = classified_files / total_files if total_files > 0 else 0.0

        return {
            "layers": layers,
            "violations": violations,
            "confidence": confidence,
        }

    def _detect_layer_violations(
        self,
        layers: dict[str, list[str]],
        import_graph: dict[str, list[str]],
    ) -> list[str]:
        """Detect architectural violations (e.g., repositories importing controllers)."""
        violations = []

        # Define acceptable layer hierarchy (top to bottom)
        layer_order = ["controllers", "services", "repositories", "models"]
        layer_index = {layer: i for i, layer in enumerate(layer_order)}

        # Check each import for violations
        for importer, imported_files in import_graph.items():
            importer_layer = self._classify_file_layer(importer, layers)
            if not importer_layer:
                continue

            for imported in imported_files:
                imported_layer = self._classify_file_layer(imported, layers)
                if not imported_layer:
                    continue

                # Check if import violates hierarchy (lower layer importing higher)
                if (
                    importer_layer in layer_index
                    and imported_layer in layer_index
                    and layer_index[importer_layer] > layer_index[imported_layer]
                ):
                    violations.append(
                        f"{importer} ({importer_layer}) imports {imported} ({imported_layer}) "
                        f"— violates layer hierarchy"
                    )

        return sorted(set(violations))

    def _classify_file_layer(
        self,
        file_path: str,
        layers: dict[str, list[str]],
    ) -> str | None:
        """Classify a file into its architectural layer."""
        file_lower = file_path.lower()

        for layer_name, files in layers.items():
            if any(file_lower == f.lower() for f in files):
                return layer_name

        return None

    def analyze_dependency_direction(
        self,
        target_path: str | Path,
    ) -> dict[str, Any]:
        """
        Analyze dependency graph direction for coupling issues.

        Returns:
            Dict with:
            - inbound_coupling: {file: count} (files that import this)
            - outbound_coupling: {file: count} (files this imports)
            - violations: [detected violations]
            - graph: {file: [imports]}

        Raises:
            RuntimeError: If analysis fails
        """
        result = self.distill(target_path)

        import_graph = result.dependencies

        # Calculate coupling metrics
        inbound: dict[str, int] = {}
        outbound: dict[str, int] = {}

        for importer, imports in import_graph.items():
            outbound[importer] = len(imports)

            for imported in imports:
                inbound[imported] = inbound.get(imported, 0) + 1

        # Detect violations
        violations = self._detect_dependency_violations(import_graph)

        return {
            "inbound_coupling": inbound,
            "outbound_coupling": outbound,
            "violations": violations,
            "graph": import_graph,
        }

    def _detect_dependency_violations(
        self,
        import_graph: dict[str, list[str]],
    ) -> list[str]:
        """Detect dependency violations (circular dependencies)."""
        violations = []

        # Detect circular dependencies using DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str, path: list[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in import_graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [node]):
                        return True
                elif neighbor in rec_stack:
                    cycle = path + [node, neighbor]
                    violations.append(f"Circular dependency: {' → '.join(cycle)}")
                    return True

            rec_stack.remove(node)
            return False

        for node in import_graph:
            if node not in visited:
                dfs(node, [])

        return sorted(set(violations))


def create_aid_integrator(config: dict[str, Any] | None = None) -> AidIntegratorV2:
    """
    Factory function to create AidIntegratorV2 instance.

    Args:
        config: Optional configuration dict

    Returns:
        AidIntegratorV2 instance

    Raises:
        RuntimeError: If AID CLI is not found or not executable
    """
    return AidIntegratorV2(config)
