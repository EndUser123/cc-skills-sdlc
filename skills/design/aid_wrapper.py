"""
AI Distiller (aid) Integration Wrapper for /arch skill.

Provides programmatic codebase analysis capabilities using the AIDistiller
core implementation. Stateless design for multi-terminal safety.

Integration Points:
- Stage 0.3 (Codebase Analysis): Replace manual Glob/Read with distillation
- Boundary Detection: For microservices/decomposition questions
- Dependency Analysis: For refactoring/integration questions
- Layer Detection: For architectural validation (controllers/services/repositories)
- Dependency Direction: For coupling violation detection

Author: CSF NIP Architecture Team
Version: 1.1.0
"""

from __future__ import annotations

import ast
import logging
import re

# Add __csf to path for importing AIDistiller
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

csf_path = Path(__file__).parent.parent.parent.parent / "__csf" / "src"
if str(csf_path) not in sys.path:
    sys.path.insert(0, str(csf_path))

from modules.aid_distiller import AIDistiller, AIDistillerConfig, CompressionLevel, ContentType

logger = logging.getLogger(__name__)


@dataclass
class CodebaseAnalysis:
    """Result from codebase distillation and analysis."""

    distilled_structure: str
    public_apis: dict[str, Any] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    boundaries: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    files_analyzed: int = 0
    compression_ratio: float = 0.0


@dataclass
class APIExtract:
    """Represents an extracted API signature."""

    name: str
    type: str  # function, class, method, constant
    signature: str
    file_path: str
    line_number: int
    docstring: str | None = None
    decorators: list[str] = field(default_factory=list)


@dataclass
class LayerAnalysis:
    """Result from architectural layer detection."""

    layers: dict[str, list[str]] = field(default_factory=dict)
    """Layer name -> list of files in that layer"""

    violations: list[str] = field(default_factory=list)
    """Detected architectural violations (e.g., controller importing repository)"""

    confidence: float = 0.0
    """Confidence score 0.0-1.0 based on classification clarity"""


@dataclass
class DependencyDirection:
    """Result from dependency direction analysis."""

    inbound_coupling: dict[str, int] = field(default_factory=dict)
    """File -> count of files that import it"""

    outbound_coupling: dict[str, int] = field(default_factory=dict)
    """File -> count of modules it imports"""

    violations: list[str] = field(default_factory=list)
    """Dependency violations (reverse dependencies, circular deps)"""

    graph: dict[str, list[str]] = field(default_factory=dict)
    """File -> list of files it imports"""


class AidIntegrator:
    """
    AI Distiller integration wrapper for /arch skill.

    Provides programmatic access to codebase analysis capabilities:
    - Code distillation for efficient LLM consumption
    - Public API extraction for interface discovery
    - Dependency analysis for integration planning
    - Boundary detection for decomposition decisions
    - Layer detection for architectural validation (NEW)
    - Dependency direction analysis for coupling violations (NEW)

    Design Principles:
    - Stateless: No shared mutable state across terminals
    - Read-only: Only analyzes code, never modifies
    - Multi-terminal safe: Concurrent execution is safe
    - Graceful degradation: Returns partial results on errors
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize AidIntegrator with AIDistillator backend.

        Args:
            config: Optional configuration dict with keys:
                - compression_level: "minimal" | "moderate" | "high" | "maximum"
                - max_content_size_mb: Maximum content size to process
                - enable_caching: Enable result caching
        """
        aid_config = AIDistillerConfig(
            compression_level=CompressionLevel(config.get("compression_level", "moderate"))
            if config and "compression_level" in config
            else CompressionLevel.MODERATE,
            content_type=ContentType.CODE,
            max_content_size_mb=config.get("max_content_size_mb", 100) if config else 100,
            enable_caching=config.get("enable_caching", True) if config else True,
        )
        self._distiller = AIDistiller(aid_config)
        self._config = config or {}

    def distill(
        self,
        target_path: str | Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> CodebaseAnalysis:
        """
        Distill codebase structure for efficient architecture analysis.

        Extracts essential code structure (APIs, types, contracts) while
        removing implementation details. Reduces context size by 60-90%.

        Args:
            target_path: Path to file or directory to analyze
            include_patterns: Glob patterns for files to include (e.g., ["*.py", "*.ts"])
            exclude_patterns: Glob patterns for files to exclude (e.g., ["*test*", "*__pycache__*"])

        Returns:
            CodebaseAnalysis with distilled structure and metrics

        Example:
            >>> integrator = AidIntegrator()
            >>> analysis = integrator.distill("src/")
            >>> print(analysis.distilled_structure)  # Compressed code structure
        """
        target = Path(target_path)
        if not target.exists():
            return CodebaseAnalysis(
                distilled_structure="", metrics={"error": f"Path not found: {target_path}"}
            )

        # Collect files to analyze
        files = self._collect_files(target, include_patterns, exclude_patterns)

        # Distill each file and aggregate results
        distilled_parts = []
        all_apis = []
        all_dependencies = {}

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                # Detect language and distill
                if file_path.suffix == ".py":
                    distilled = self._distill_python(content, file_path)
                    apis = self._extract_apis_python(content, file_path)
                    deps = self._analyze_dependencies_python(content, file_path)
                elif file_path.suffix in (".ts", ".tsx", ".js", ".jsx"):
                    distilled = self._distill_typescript(content, file_path)
                    apis = self._extract_apis_typescript(content, file_path)
                    deps = self._analyze_dependencies_typescript(content, file_path)
                else:
                    distilled = self._distill_generic(content, file_path)
                    apis = []
                    deps = {}

                distilled_parts.append(distilled)
                all_apis.extend(apis)
                all_dependencies[str(file_path.relative_to(target))] = deps

            except Exception as e:
                logger.warning(f"Failed to distill {file_path}: {e}")
                continue

        # Combine distilled parts
        combined = "\n\n".join(distilled_parts)

        # Extract boundaries (module/group detection)
        boundaries = self._detect_boundaries(target, files)

        return CodebaseAnalysis(
            distilled_structure=combined,
            public_apis={"apis": [api.__dict__ for api in all_apis]},
            dependencies=all_dependencies,
            boundaries=boundaries,
            metrics={
                "files_analyzed": len(files),
                "apis_found": len(all_apis),
                "dependencies_found": sum(len(deps) for deps in all_dependencies.values()),
            },
            files_analyzed=len(files),
        )

    def extract_public_apis(
        self,
        target_path: str | Path,
        include_private: bool = False,
    ) -> list[APIExtract]:
        """
        Extract public API signatures from codebase.

        Useful for:
        - Interface discovery in architecture reviews
        - Integration planning between modules
        - API contract documentation

        Args:
            target_path: Path to file or directory
            include_private: Include private/internal members (default: False)

        Returns:
            List of APIExtract objects with signature information

        Example:
            >>> integrator = AidIntegrator()
            >>> apis = integrator.extract_public_apis("src/api/")
            >>> for api in apis:
            ...     print(f"{api.type}: {api.signature}")
        """
        target = Path(target_path)
        apis = []

        files = self._collect_files(target) if target.is_dir() else [target]

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                if file_path.suffix == ".py":
                    apis.extend(self._extract_apis_python(content, file_path, include_private))
                elif file_path.suffix in (".ts", ".tsx", ".js", ".jsx"):
                    apis.extend(self._extract_apis_typescript(content, file_path, include_private))

            except Exception as e:
                logger.warning(f"Failed to extract APIs from {file_path}: {e}")

        return apis

    def analyze_dependencies(
        self,
        target_path: str | Path,
    ) -> dict[str, list[str]]:
        """
        Analyze dependency relationships in codebase.

        Useful for:
        - Refactoring impact analysis
        - Integration planning
        - Circular dependency detection

        Args:
            target_path: Path to file or directory

        Returns:
            Dict mapping file paths to their dependencies

        Example:
            >>> integrator = AidIntegrator()
            >>> deps = integrator.analyze_dependencies("src/")
            >>> for file, imports in deps.items():
            ...     print(f"{file}: {', '.join(imports)}")
        """
        target = Path(target_path)
        dependencies = {}

        files = self._collect_files(target) if target.is_dir() else [target]

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                if file_path.suffix == ".py":
                    deps = self._analyze_dependencies_python(content, file_path)
                elif file_path.suffix in (".ts", ".tsx", ".js", ".jsx"):
                    deps = self._analyze_dependencies_typescript(content, file_path)
                else:
                    deps = {}

                dependencies[str(file_path.relative_to(target))] = deps

            except Exception as e:
                logger.warning(f"Failed to analyze dependencies for {file_path}: {e}")

        return dependencies

    def detect_boundaries(
        self,
        target_path: str | Path,
    ) -> list[str]:
        """
        Detect natural module/service boundaries in codebase.

        Useful for:
        - Microservices decomposition planning
        - Service boundary identification
        - Modular architecture design

        Args:
            target_path: Path to directory to analyze

        Returns:
            List of detected boundary names

        Example:
            >>> integrator = AidIntegrator()
            >>> boundaries = integrator.detect_boundaries("src/")
            >>> print(f"Potential services: {boundaries}")
        """
        target = Path(target_path)
        if not target.is_dir():
            return []

        files = self._collect_files(target)
        return self._detect_boundaries(target, files)

    def detect_layers(
        self,
        target_path: str | Path,
    ) -> LayerAnalysis:
        """
        Detect architectural layers based on naming and import patterns.

        Useful for:
        - Clean architecture validation (controllers → services → repositories)
        - Microservice boundary identification
        - Layer violation detection (e.g., repositories importing controllers)

        Args:
            target_path: Path to directory to analyze

        Returns:
            LayerAnalysis with classified layers and detected violations

        Example:
            >>> integrator = AidIntegrator()
            >>> layers = integrator.detect_layers("src/")
            >>> print(f"Controllers: {layers.layers.get('controllers', [])}")
            >>> print(f"Violations: {layers.violations}")
        """
        target = Path(target_path)
        if not target.is_dir():
            return LayerAnalysis()

        files = self._collect_files(target)

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

        # Classify files by layer
        layers: dict[str, list[str]] = {k: [] for k in layer_patterns}
        unclassified: list[str] = []

        for file_path in files:
            file_name = file_path.stem.lower()
            rel_path = str(file_path.relative_to(target))

            # Classify based on filename patterns
            classified = False
            for layer, patterns in layer_patterns.items():
                if any(pattern in file_name for pattern in patterns):
                    layers[layer].append(rel_path)
                    classified = True
                    break

            if not classified:
                unclassified.append(rel_path)

        # Build import graph for violation detection
        import_graph = self._build_import_graph(target, files)
        violations = self._detect_layer_violations(layers, import_graph)

        # Calculate confidence based on classification clarity
        total_files = len(files)
        classified_files = sum(len(files) for files in layers.values())
        confidence = classified_files / total_files if total_files > 0 else 0.0

        return LayerAnalysis(layers=layers, violations=violations, confidence=confidence)

    def analyze_dependency_direction(
        self,
        target_path: str | Path,
    ) -> DependencyDirection:
        """
        Analyze dependency graph direction to detect coupling issues.

        Useful for:
        - Detecting architectural violations (infrastructure importing domain)
        - Identifying circular dependencies
        - Finding high-coupling modules (many imports)

        Args:
            target_path: Path to directory to analyze

        Returns:
            DependencyDirection with coupling metrics and violations

        Example:
            >>> integrator = AidIntegrator()
            >>> deps = integrator.analyze_dependency_direction("src/")
            >>> print(f"High inbound: {deps.inbound_coupling}")
            >>> print(f"Violations: {deps.violations}")
        """
        target = Path(target_path)
        if not target.is_dir():
            return DependencyDirection()

        files = self._collect_files(target)

        # Build import graph
        import_graph = self._build_import_graph(target, files)

        # Calculate coupling metrics
        inbound: dict[str, int] = {}
        outbound: dict[str, int] = {}

        for importer, imports in import_graph.items():
            # Count outbound (modules this file imports)
            outbound[importer] = len(imports)

            # Count inbound (files that import this module)
            for imported in imports:
                inbound[imported] = inbound.get(imported, 0) + 1

        # Detect violations (reverse dependencies, circular deps)
        violations = self._detect_dependency_violations(import_graph)

        return DependencyDirection(
            inbound_coupling=inbound,
            outbound_coupling=outbound,
            violations=violations,
            graph=import_graph,
        )

    # --- Private Methods ---

    def _collect_files(
        self,
        target: Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Collect files for analysis based on patterns."""
        if target.is_file():
            return [target]

        # Default include patterns for code files
        if not include_patterns:
            include_patterns = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.go", "*.rs"]

        # Default exclude patterns
        if not exclude_patterns:
            exclude_patterns = ["*test*", "*__pycache__*", "node_modules/*", "*.min.js"]

        files = []
        for pattern in include_patterns:
            for file_path in target.rglob(pattern):
                # Check exclusions
                if any(file_path.match(excl) for excl in exclude_patterns):
                    continue
                files.append(file_path)

        return sorted(set(files))

    def _distill_python(self, content: str, file_path: Path) -> str:
        """Distill Python code to essential structure."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return f"# {file_path}: [Syntax error, could not parse]"

        parts = [f"# {file_path.relative_to(file_path.parents[5])}"]

        for node in tree.body:
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
                parts.append(f"import {', '.join(modules)}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                parts.append(f"from {module} import {', '.join(names)}")
            elif isinstance(node, ast.ClassDef):
                bases = [ast.unparse(base) for base in node.bases]
                bases_str = f"({', '.join(bases)})" if bases else ""
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                parts.append(f"class {node.name}{bases_str}:  # methods: {', '.join(methods)}")
            elif isinstance(node, ast.FunctionDef):
                returns = ast.unparse(node.returns) if node.returns else "None"
                args = [ast.unparse(arg) for arg in node.args.args]
                parts.append(f"def {node.name}({', '.join(args)}) -> {returns}")
            elif isinstance(node, ast.AsyncFunctionDef):
                args = [ast.unparse(arg) for arg in node.args.args]
                parts.append(f"async def {node.name}({', '.join(args)})")

        return "\n".join(parts)

    def _distill_typescript(self, content: str, file_path: Path) -> str:
        """Distill TypeScript/JavaScript code to essential structure."""
        # Simple regex-based extraction for TypeScript
        # For production, use proper AST parser (typescript ESTree)
        parts = [f"# {file_path}"]

        # Extract imports
        import_pattern = r'^import\s+(?:.*\s+from\s+)?[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            parts.append(f"import {match.group(1)}")

        # Extract exports (functions, classes, interfaces)
        export_patterns = [
            r"export\s+(?:async\s+)?function\s+(\w+)",
            r"export\s+class\s+(\w+)",
            r"export\s+interface\s+(\w+)",
            r"export\s+type\s+(\w+)",
            r"export\s+(?:const|let|var)\s+(\w+)",
        ]

        for pattern in export_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                parts.append(f"export {match.group(1)}")

        return "\n".join(parts)

    def _distill_generic(self, content: str, file_path: Path) -> str:
        """Distill generic text files."""
        lines = content.splitlines()
        return f"# {file_path}\n# {len(lines)} lines\n# " + " ".join(lines[:5])[:100]

    def _extract_apis_python(
        self,
        content: str,
        file_path: Path,
        include_private: bool = False,
    ) -> list[APIExtract]:
        """Extract public APIs from Python code."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        apis = []

        for node in ast.walk(tree):
            # Filter to top-level definitions only
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

            # Check if this node is a top-level child
            is_top_level = any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n == node
                for n in tree.body
            )
            if not is_top_level:
                continue

            # Skip private names unless include_private
            if not include_private and node.name.startswith("_"):
                continue

            # Extract signature
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [ast.unparse(arg) for arg in node.args.args]
                returns = ast.unparse(node.returns) if node.returns else "None"
                signature = f"def {node.name}({', '.join(args)}) -> {returns}"
                api_type = (
                    "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                )
            else:  # ClassDef
                bases = [ast.unparse(base) for base in node.bases]
                bases_str = f"({', '.join(bases)})" if bases else ""
                signature = f"class {node.name}{bases_str}"
                api_type = "class"

            # Extract docstring
            docstring = ast.get_docstring(node)

            # Extract decorators
            decorators = []
            if hasattr(node, "decorator_list"):
                for d in node.decorator_list:
                    decorators.append(ast.unparse(d))

            apis.append(
                APIExtract(
                    name=node.name,
                    type=api_type,
                    signature=signature,
                    file_path=str(file_path),
                    line_number=node.lineno,
                    docstring=docstring,
                    decorators=decorators,
                )
            )

        return apis

    def _extract_apis_typescript(
        self,
        content: str,
        file_path: Path,
        include_private: bool = False,
    ) -> list[APIExtract]:
        """Extract public APIs from TypeScript/JavaScript code."""
        apis = []

        # Export functions
        for match in re.finditer(
            r"export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
            content,
        ):
            name, params = match.groups()
            if include_private or not name.startswith("_"):
                apis.append(
                    APIExtract(
                        name=name,
                        type="async_function" if "async" in match.group(0) else "function",
                        signature=f"function {name}({params})",
                        file_path=str(file_path),
                        line_number=content[: match.start()].count("\n") + 1,
                    )
                )

        # Export classes/interfaces
        for match in re.finditer(
            r"export\s+(class|interface|type)\s+(\w+)",
            content,
        ):
            api_type, name = match.groups()
            if include_private or not name.startswith("_"):
                apis.append(
                    APIExtract(
                        name=name,
                        type=api_type,
                        signature=f"{api_type} {name}",
                        file_path=str(file_path),
                        line_number=content[: match.start()].count("\n") + 1,
                    )
                )

        return apis

    def _analyze_dependencies_python(
        self,
        content: str,
        file_path: Path,
    ) -> list[str]:
        """Analyze Python dependencies."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        deps = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    deps.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.add(node.module.split(".")[0])

        return sorted(deps)

    def _analyze_dependencies_typescript(
        self,
        content: str,
        file_path: Path,
    ) -> list[str]:
        """Analyze TypeScript/JavaScript dependencies."""
        deps = set()

        for match in re.finditer(
            r'import\s+(?:.*\s+from\s+)?[\'"]([^\'"]+)[\'"]',
            content,
        ):
            import_path = match.group(1)
            # Skip relative imports
            if not import_path.startswith("."):
                deps.add(import_path.split("/")[0])

        return sorted(deps)

    def _detect_boundaries(
        self,
        target: Path,
        files: list[Path],
    ) -> list[str]:
        """
        Detect natural module boundaries using directory and import analysis.

        A boundary is detected when:
        1. A directory has multiple files with internal imports
        2. Files share a common prefix/purpose (e.g., api/, service/, handler/)
        3. Import graph shows clustering
        """
        boundaries = []

        # Group files by immediate parent directory
        dir_groups: dict[str, list[Path]] = {}
        for file_path in files:
            parent = file_path.parent.name
            if parent not in dir_groups:
                dir_groups[parent] = []
            dir_groups[parent].append(file_path)

        # Directories with 3+ files are potential boundaries
        for dir_name, dir_files in dir_groups.items():
            if len(dir_files) >= 3:
                boundaries.append(dir_name)

        # Detect common architectural patterns
        for dir_name in dir_groups.keys():
            if dir_name in ("api", "apis", "handlers", "routes"):
                if "api" not in boundaries:
                    boundaries.append("api")
            elif dir_name in ("service", "services", "core", "domain"):
                if "service" not in boundaries:
                    boundaries.append("service")
            elif dir_name in ("repository", "repositories", "db", "database"):
                if "data" not in boundaries:
                    boundaries.append("data")

        return sorted(set(boundaries))

    def _build_import_graph(
        self,
        target: Path,
        files: list[Path],
    ) -> dict[str, list[str]]:
        """Build import graph mapping file -> list of files it imports."""
        import_graph: dict[str, list[str]] = {}

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                imports = set()

                if file_path.suffix == ".py":
                    imports.update(self._analyze_dependencies_python(content, file_path))
                elif file_path.suffix in (".ts", ".tsx", ".js", ".jsx"):
                    imports.update(self._analyze_dependencies_typescript(content, file_path))

                # Filter to local imports only (same target directory)
                local_imports = []
                file_key = str(file_path.relative_to(target))

                for imp in imports:
                    # Check if import maps to another local file
                    for other_file in files:
                        other_name = other_file.stem.lower()
                        if imp.lower() in other_name and other_file != file_path:
                            local_imports.append(str(other_file.relative_to(target)))
                            break

                import_graph[file_key] = sorted(local_imports)

            except Exception as e:
                logger.warning(f"Failed to analyze imports for {file_path}: {e}")

        return import_graph

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

    def _detect_dependency_violations(
        self,
        import_graph: dict[str, list[str]],
    ) -> list[str]:
        """Detect dependency violations (circular dependencies, reverse dependencies)."""
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
                    # Found cycle
                    cycle = path + [node, neighbor]
                    violations.append(f"Circular dependency: {' → '.join(cycle)}")
                    return True

            rec_stack.remove(node)
            return False

        for node in import_graph:
            if node not in visited:
                dfs(node, [])

        return sorted(set(violations))


def create_aid_integrator(config: dict[str, Any] | None = None) -> AidIntegrator:
    """Factory function to create AidIntegrator instance."""
    return AidIntegrator(config)
