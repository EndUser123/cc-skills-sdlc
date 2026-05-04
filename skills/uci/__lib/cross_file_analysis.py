"""
Cross-File Analysis for Unified Code Inspection

Provides import graph analysis, circular dependency detection, and
taint propagation for security-focused code review.

Inspired by /meta-review patterns for comprehensive cross-file analysis.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class ImportNode:
    """Represents a module/file in the import graph."""
    path: str
    imports: Set[str] = field(default_factory=set)
    imported_by: Set[str] = field(default_factory=set)

    def add_import(self, target: str) -> None:
        """Add an import from this module to target."""
        self.imports.add(target)

    def add_importer(self, source: str) -> None:
        """Add a module that imports this one."""
        self.imported_by.add(source)


@dataclass
class CircularDependency:
    """Represents a circular dependency in the import graph."""
    cycle: List[str]
    severity: str  # "high", "medium", "low"
    description: str


@dataclass
class TaintPath:
    """Represents a taint propagation path from source to sink."""
    source: str  # User input location
    sink: str  # Dangerous operation location
    path: List[str]  # Intermediate functions
    severity: str  # "critical", "high", "medium"
    description: str


class CrossFileAnalyzer:
    """
    Analyzes cross-file relationships and security patterns.

    Provides:
    1. Import graph construction and analysis
    2. Circular dependency detection
    3. Taint propagation analysis for security
    """

    # Patterns for detecting taint sources (user input)
    TAINT_SOURCES = {
        "python": [
            r"input\s*\(",
            r"sys\.argv",
            r"os\.environ",
            r"request\.(get|post|form|json)",
            r"flask\.request",
            r"fastapi\.(Request|Form|Query)",
            r"cgi\.fieldstorage",
            r"raw_input\s*\(",
        ],
        "javascript": [
            r"document\.getElementById",
            r"\.value\s*[;=]",
            r"window\.location",
            r"URLSearchParams",
            r"fetch\s*\(",
            r"axios\.(get|post)",
            r"\$\.(get|post)",
        ],
    }

    # Patterns for detecting taint sinks (dangerous operations)
    TAINT_SINKS = {
        "python": [
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__\s*\(",
            r"os\.system\s*\(",
            r"subprocess\.(call|run|Popen)\s*\(",
            r"sql\.execute\s*\(",
            r"cursor\.execute\s*\(",
            r"shell\s*=\s*True",
            r"open\s*\([^)]*\s*[rw]",
        ],
        "javascript": [
            r"eval\s*\(",
            r"Function\s*\(",
            r"setTimeout\s*\([^,]+,\s*['\"]",
            r"setInterval\s*\([^,]+,\s*['\"]",
            r"\.innerHTML\s*[=]",
            r"\.outerHTML\s*[=]",
            r"document\.write\s*\(",
        ],
    }

    # Sanitizer patterns (functions that clean user input)
    SANITIZERS = {
        "python": [
            r"escape\s*\(",
            r"sanitize\s*\(",
            r"html\.escape",
            r"bleach\.clean",
            r"werkzeug\.escape",
            r"\.strip\s*\(",
        ],
        "javascript": [
            r"escape\s*\(",
            r"sanitize\s*\(",
            r"DOMPurify\.sanitize",
            r"\.textContent\s*[=]",
        ],
    }

    def __init__(self, project_root: Path):
        """
        Initialize the cross-file analyzer.

        Args:
            project_root: Root directory of the project to analyze
        """
        self.project_root = Path(project_root)
        self.import_graph: Dict[str, ImportNode] = {}
        self.language = self._detect_language()

    def _detect_language(self) -> str:
        """Detect the primary language of the project."""
        python_files = len(list(self.project_root.rglob("*.py")))
        js_files = len(list(self.project_root.rglob("*.js")))
        ts_files = len(list(self.project_root.rglob("*.ts")))

        if python_files >= js_files + ts_files:
            return "python"
        return "javascript"

    def build_import_graph(
        self,
        file_list: List[str],
        max_files: int = 50
    ) -> Dict[str, ImportNode]:
        """
        Build import graph from a list of files.

        Args:
            file_list: List of file paths to analyze
            max_files: Maximum number of files to process (prevent bloat)

        Returns:
            Dict mapping file path to ImportNode
        """
        self.import_graph = {}

        # Limit files to prevent excessive processing
        files_to_process = file_list[:max_files] if len(file_list) > max_files else file_list

        for file_path in files_to_process:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            # Initialize node
            if file_path not in self.import_graph:
                self.import_graph[file_path] = ImportNode(path=file_path)

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                imports = self._extract_imports(content, file_path)

                for imp in imports:
                    # Add import relationship
                    self.import_graph[file_path].add_import(imp)

                    # Create reverse relationship
                    if imp not in self.import_graph:
                        self.import_graph[imp] = ImportNode(path=imp)
                    self.import_graph[imp].add_importer(file_path)

            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")

        return self.import_graph

    def _extract_imports(self, content: str, file_path: str) -> Set[str]:
        """Extract import statements from file content."""
        imports = set()

        if self.language == "python":
            # Python imports: import X, from X import Y
            patterns = [
                r"^import\s+([a-zA-Z_][a-zA-Z0-9_.]*)",
                r"^from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    imp = match.group(1)
                    # Convert to potential file path
                    imp_path = imp.replace(".", "/")
                    imports.add(imp_path)

        elif self.language in ("javascript", "typescript"):
            # JS/TS imports: import X from 'Y', require('Y')
            patterns = [
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    imports.add(match.group(1))

        return imports

    def detect_circular_dependencies(
        self,
        max_depth: int = 10
    ) -> List[CircularDependency]:
        """
        Detect circular dependencies in the import graph.

        Args:
            max_depth: Maximum search depth for cycle detection

        Returns:
            List of CircularDependency objects
        """
        cycles = []

        for start_node in self.import_graph.values():
            visited = set()
            path = []

            def dfs(node: ImportNode, depth: int) -> bool:
                if depth > max_depth:
                    return False

                if node.path in visited:
                    # Found a cycle
                    cycle_start = path.index(node.path)
                    cycle_path = path[cycle_start:] + [node.path]

                    # Determine severity based on cycle length
                    cycle_len = len(cycle_path)
                    if cycle_len <= 2:
                        severity = "high"
                        desc = "Direct circular import between two modules"
                    elif cycle_len <= 4:
                        severity = "medium"
                        desc = f"Circular dependency involving {cycle_len} modules"
                    else:
                        severity = "low"
                        desc = f"Large circular dependency ({cycle_len} modules)"

                    cycles.append(CircularDependency(
                        cycle=cycle_path,
                        severity=severity,
                        description=desc
                    ))
                    return True

                visited.add(node.path)
                path.append(node.path)

                # Recursively check imports
                for imp_path in node.imports:
                    if imp_path in self.import_graph:
                        if dfs(self.import_graph[imp_path], depth + 1):
                            return True

                path.pop()
                return False

            dfs(start_node, 0)

        # Deduplicate cycles
        seen = set()
        unique_cycles = []
        for cycle in cycles:
            cycle_key = tuple(cycle.cycle)
            if cycle_key not in seen:
                seen.add(cycle_key)
                unique_cycles.append(cycle)

        return unique_cycles

    def analyze_taint_propagation(
        self,
        file_list: List[str],
        max_files: int = 30
    ) -> List[TaintPath]:
        """
        Analyze taint propagation from user input to dangerous operations.

        Args:
            file_list: List of file paths to analyze
            max_files: Maximum number of files to process

        Returns:
            List of TaintPath objects representing potential vulnerabilities
        """
        taint_paths = []
        files_to_process = file_list[:max_files] if len(file_list) > max_files else file_list

        for file_path in files_to_process:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                line_number = 0

                for line in content.splitlines():
                    line_number += 1
                    line_stripped = line.strip()

                    # Check for taint sources (user input)
                    sources = self._find_matches(line_stripped, self.TAINT_SOURCES.get(self.language, []))

                    if not sources:
                        continue

                    # Check if the line uses a taint sink (dangerous operation)
                    sinks = self._find_matches(line_stripped, self.TAINT_SINKS.get(self.language, []))

                    if sinks:
                        # Check for sanitization
                        sanitizers = self._find_matches(line_stripped, self.SANITIZERS.get(self.language, []))

                        if not sanitizers:
                            # Direct flow from source to sink (same line)
                            location = f"{file_path}:{line_number}"
                            taint_paths.append(TaintPath(
                                source=location,
                                sink=location,
                                path=[],
                                severity="critical",
                                description=f"Direct {sources[0]} to {sinks[0]} without sanitization"
                            ))

            except Exception as e:
                logger.warning(f"Failed to analyze taint in {file_path}: {e}")

        return taint_paths

    def _find_matches(self, text: str, patterns: List[str]) -> List[str]:
        """Find all regex patterns that match the text."""
        matches = []
        for pattern in patterns:
            if re.search(pattern, text):
                matches.append(pattern)
        return matches

    def generate_cross_file_findings(
        self,
        file_list: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate cross-file analysis findings for UCI.

        Args:
            file_list: List of files to analyze

        Returns:
            List of finding dicts compatible with UCI format
        """
        findings = []

        # Build import graph
        self.build_import_graph(file_list)

        # Check for circular dependencies
        cycles = self.detect_circular_dependencies()
        for cycle in cycles:
            findings.append({
                "id": f"CIRC-{cycle.severity.upper()[:4]}-001",
                "severity": cycle.severity,
                "location": " -> ".join(cycle.cycle),
                "problem": cycle.description,
                "impact": "Can cause initialization issues, tight coupling, or runtime errors",
                "recommendation": "Refactor to break the cycle using dependency injection or module restructuring",
                "category": "cross-file",
                "analysis_type": "circular_dependency",
            })

        # Check for taint propagation
        taint_paths = self.analyze_taint_propagation(file_list)
        for taint in taint_paths:
            findings.append({
                "id": "TAINT-001",
                "severity": taint.severity,
                "location": f"{taint.source}",
                "problem": taint.description,
                "impact": "Unsanitized user input flows to dangerous operation - potential security vulnerability",
                "recommendation": "Add input validation and sanitization before using data in sensitive operations",
                "category": "security",
                "analysis_type": "taint_propagation",
            })

        # Import complexity findings
        complexity_issues = self._analyze_import_complexity()
        findings.extend(complexity_issues)

        return findings

    def _analyze_import_complexity(self) -> List[Dict[str, Any]]:
        """Analyze import graph for complexity issues."""
        findings = []

        for node in self.import_graph.values():
            # Check for excessive imports (coupling)
            if len(node.imports) > 15:
                findings.append({
                    "id": "COUPL-001",
                    "severity": "medium",
                    "location": node.path,
                    "problem": f"High coupling: {len(node.imports)} imports from single module",
                    "impact": "Module is tightly coupled to many other modules, making changes difficult",
                    "recommendation": "Consider refactoring into smaller, more focused modules",
                    "category": "architecture",
                    "analysis_type": "import_complexity",
                })

            # Check for highly imported modules (hot spots)
            if len(node.imported_by) > 10:
                findings.append({
                    "id": "HOTSP-001",
                    "severity": "low",
                    "location": node.path,
                    "problem": f"Hot spot module: imported by {len(node.imported_by)} other modules",
                    "impact": "Changes to this module have wide ripple effects",
                    "recommendation": "Consider splitting into smaller modules or using interfaces",
                    "category": "architecture",
                    "analysis_type": "import_complexity",
                })

        return findings

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the import graph."""
        total_nodes = len(self.import_graph)
        total_edges = sum(len(node.imports) for node in self.import_graph.values())

        # Calculate average imports per module
        avg_imports = total_edges / total_nodes if total_nodes > 0 else 0

        # Find most connected nodes
        most_imports = max(self.import_graph.values(),
                          key=lambda n: len(n.imports),
                          default=ImportNode(path=""))
        most_imported = max(self.import_graph.values(),
                            key=lambda n: len(n.imported_by),
                            default=ImportNode(path=""))

        return {
            "total_modules": total_nodes,
            "total_imports": total_edges,
            "avg_imports_per_module": round(avg_imports, 2),
            "most_imports_module": most_imports.path,
            "most_imports_count": len(most_imports.imports),
            "most_imported_module": most_imported.path,
            "most_imported_count": len(most_imported.imported_by),
            "language": self.language,
        }
