"""Library scanner for detecting Python imports and dependencies.

This module provides functionality to:
- Scan Python source files for import statements using AST
- Parse dependency files (requirements.txt, pyproject.toml)
- Combine and deduplicate library information from multiple sources
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# Standard library modules (Python 3.8+)
STANDARD_LIBRARY: Set[str] = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs",
    "codeop", "collections", "colorsys", "compileall", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
    "dis", "distutils", "doctest", "email", "encodings", "enum", "errno", "faulthandler",
    "fcntl", "filecmp", "fileinput", "fnmatch", "formatter", "fractions", "ftplib",
    "functools", "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp",
    "gzip", "hashlib", "heapq", "hmac", "html", "http", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap",
    "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt",
    "multiprocessing", "netrc", "nis", "nntplib", "numbers", "operator", "optparse",
    "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource", "rlcompleter", "runpy",
    "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symbol", "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile",
    "telnetlib", "tempfile", "termios", "test", "textwrap", "threading", "time",
    "timeit", "tkinter", "token", "tokenize", "toml", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "turtledemo", "types", "typing", "typing_extensions", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib",
}

# Constants for requirements.txt parsing
_REQUIREMENT_LINE_PATTERN = r"^([a-zA-Z0-9_-]+)((?:[~><=!]+).*)?$"
_COMMENT_PREFIX = "#"
_EQUALS_OPERATOR = "=="

# Constants for TOML parsing
_TOML_SECTION_PATTERN = r"\[{section}\]"
_TOML_KEY_PATTERN = r"{key}\s*=\s*\["
_TOML_NEXT_SECTION_PATTERN = r"\n\["
_TOML_PROJECT_SECTION = "project"
_TOML_DEPENDENCIES_KEY = "dependencies"
_TOML_OPTIONAL_DEPS_SECTION = "project.optional-dependencies"
_TOML_ARRAY_ASSIGNMENT_PATTERN = r'(\w+)\s*=\s*\['

# Constants for parsing
_FIRST_SEGMENT_INDEX = 0
_ABSOLUTE_IMPORT_LEVEL = 0

# Constants for string processing
_QUOTE_CHARS = ('"', "'")
_BACKSLASH = '\\'
_COMMA = ','
_OPENING_BRACKET = '['
_CLOSING_BRACKET = ']'


class ImportScanner:
    """Scan Python source files for import statements using AST."""

    def __init__(self) -> None:
        """Initialize the ImportScanner."""
        self._imports: Set[str] = set()

    def scan_file(self, file_path: Path, filter_stdlib: bool = False) -> List[str]:
        """
        Scan a single Python file for import statements.

        Args:
            file_path: Path to the Python file to scan
            filter_stdlib: If True, filter out standard library imports

        Returns:
            List of imported module names
        """
        self._imports = set()

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=str(file_path))
            self._visit_tree(tree)
        except (SyntaxError, UnicodeDecodeError, OSError):
            return []

        imports = list(self._imports)

        if filter_stdlib:
            imports = self._filter_standard_library(imports)

        return imports

    def scan_files(
        self, file_paths: List[Path], filter_stdlib: bool = False
    ) -> List[str]:
        """
        Scan multiple Python files for import statements.

        Args:
            file_paths: List of paths to Python files to scan
            filter_stdlib: If True, filter out standard library imports

        Returns:
            Deduplicated list of imported module names across all files
        """
        all_imports: Set[str] = set()

        for file_path in file_paths:
            imports = self.scan_file(file_path, filter_stdlib=False)
            all_imports.update(imports)

        imports = list(all_imports)

        if filter_stdlib:
            imports = self._filter_standard_library(imports)

        return imports

    def _visit_tree(self, tree: ast.AST) -> None:
        """
        Visit AST nodes to extract import statements.

        Args:
            tree: AST tree to traverse
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self._extract_import_modules(node)
            elif isinstance(node, ast.ImportFrom):
                self._extract_from_import_modules(node)

    def _extract_import_modules(self, node: ast.Import) -> None:
        """
        Extract module names from 'import X' statements.

        Args:
            node: AST Import node
        """
        for alias in node.names:
            module_name = alias.name.split(".")[_FIRST_SEGMENT_INDEX]
            self._imports.add(module_name)

    def _extract_from_import_modules(self, node: ast.ImportFrom) -> None:
        """
        Extract module names from 'from X import Y' statements.

        Args:
            node: AST ImportFrom node

        Note:
            Only absolute imports are extracted (relative imports are ignored)
        """
        if node.module and node.level == _ABSOLUTE_IMPORT_LEVEL:
            module_name = node.module.split(".")[_FIRST_SEGMENT_INDEX]
            self._imports.add(module_name)

    def _filter_standard_library(self, imports: List[str]) -> List[str]:
        """
        Filter out standard library modules from import list.

        Args:
            imports: List of imported module names

        Returns:
            Filtered list excluding standard library modules
        """
        return [imp for imp in imports if imp not in STANDARD_LIBRARY]


class DependencyFileParser:
    """Parse dependency files like requirements.txt and pyproject.toml."""

    def __init__(self) -> None:
        """Initialize the DependencyFileParser."""
        pass

    def parse_requirements_txt(self, file_path: Path) -> Dict[str, Optional[str]]:
        """
        Parse a requirements.txt file.

        Args:
            file_path: Path to the requirements.txt file

        Returns:
            Dictionary mapping package names to version specifiers (or None)
        """
        dependencies: Dict[str, Optional[str]] = {}

        if not file_path.exists():
            return dependencies

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped_line = line.strip()

                    if self._should_skip_line(stripped_line):
                        continue

                    pkg, version = self._parse_requirement_line(stripped_line)
                    if pkg:
                        dependencies[pkg] = version
        except (OSError, UnicodeDecodeError):
            return dependencies

        return dependencies

    def parse_pyproject_toml(self, file_path: Path) -> Dict[str, Optional[str]]:
        """
        Parse a pyproject.toml file for dependencies.

        Args:
            file_path: Path to the pyproject.toml file

        Returns:
            Dictionary mapping package names to version specifiers (or None)
        """
        dependencies: Dict[str, Optional[str]] = {}

        if not file_path.exists():
            return dependencies

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse TOML manually (avoiding external dependency)
            deps_from_project = self._extract_toml_array(
                content, _TOML_PROJECT_SECTION, _TOML_DEPENDENCIES_KEY
            )
            deps_from_optional = self._extract_all_optional_deps(content)

            # Combine dependencies (optional deps override project deps)
            dependencies.update(deps_from_project)
            dependencies.update(deps_from_optional)

        except (OSError, UnicodeDecodeError):
            return dependencies

        return dependencies

    def parse_all(
        self,
        requirements_txt: Optional[Path] = None,
        pyproject_toml: Optional[Path] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Parse both requirements.txt and pyproject.toml.

        Args:
            requirements_txt: Path to requirements.txt (optional)
            pyproject_toml: Path to pyproject.toml (optional)

        Returns:
            Combined dictionary of dependencies from both files
        """
        dependencies: Dict[str, Optional[str]] = {}

        if requirements_txt:
            dependencies.update(self.parse_requirements_txt(requirements_txt))

        if pyproject_toml:
            dependencies.update(self.parse_pyproject_toml(pyproject_toml))

        return dependencies

    def _should_skip_line(self, line: str) -> bool:
        """
        Determine if a requirements.txt line should be skipped.

        Args:
            line: Line from requirements.txt

        Returns:
            True if line is empty or a comment
        """
        return not line or line.startswith(_COMMENT_PREFIX)

    def _parse_requirement_line(self, line: str) -> Tuple[str, Optional[str]]:
        """
        Parse a single requirement line.

        Args:
            line: A line from requirements.txt

        Returns:
            Tuple of (package_name, version_specifier)
            Version specifier includes the operator except for == which is stripped
        """
        match = re.match(_REQUIREMENT_LINE_PATTERN, line)

        if match:
            package_name = match.group(1)
            version = match.group(2) if match.group(2) else None
            # Strip == operator but keep others (>=, <=, ~=, etc.)
            if version and version.startswith(_EQUALS_OPERATOR):
                version = version[len(_EQUALS_OPERATOR):]
            return package_name, version

        return "", None

    def _extract_toml_array(
        self, content: str, section: str, key: str
    ) -> Dict[str, Optional[str]]:
        """
        Extract an array from a TOML section.

        Args:
            content: TOML file content
            section: Section name (e.g., "project")
            key: Key name (e.g., "dependencies")

        Returns:
            Dictionary of parsed dependencies
        """
        dependencies: Dict[str, Optional[str]] = {}

        section_content = self._extract_toml_section(content, section)
        if not section_content:
            return dependencies

        key_pattern = _TOML_KEY_PATTERN.format(key=key)
        key_match = re.search(key_pattern, section_content)

        if not key_match:
            return dependencies

        array_content = self._extract_bracketed_content(
            section_content, key_match.end()
        )

        return self._parse_toml_array_entries(array_content)

    def _extract_toml_section(self, content: str, section: str) -> str:
        """
        Extract a TOML section content.

        Args:
            content: Full TOML file content
            section: Section name to extract

        Returns:
            Section content or empty string if not found
        """
        section_pattern = _TOML_SECTION_PATTERN.format(section=section)
        section_match = re.search(section_pattern, content)

        if not section_match:
            return ""

        section_start = section_match.end()
        next_section = re.search(_TOML_NEXT_SECTION_PATTERN, content[section_start:])

        if next_section:
            return content[section_start:section_start + next_section.start()]
        else:
            return content[section_start:]

    def _extract_bracketed_content(
        self, content: str, start_pos: int
    ) -> str:
        """
        Extract content within matching square brackets.

        Args:
            content: String containing bracketed content
            start_pos: Position after opening bracket

        Returns:
            Content within matching brackets
        """
        bracket_count = 1
        array_end = start_pos

        for i, char in enumerate(content[start_pos:]):
            if char == _OPENING_BRACKET:
                bracket_count += 1
            elif char == _CLOSING_BRACKET:
                bracket_count -= 1
                if bracket_count == 0:
                    array_end = start_pos + i
                    break

        return content[start_pos:array_end]

    def _parse_toml_array_entries(
        self, array_content: str
    ) -> Dict[str, Optional[str]]:
        """
        Parse TOML array entries into dependencies.

        Args:
            array_content: Content between square brackets

        Returns:
            Dictionary of parsed dependencies
        """
        dependencies: Dict[str, Optional[str]] = {}

        for line in array_content.split("\n"):
            stripped_line = line.strip().strip('",')

            if stripped_line:
                pkg, version = self._parse_requirement_line(stripped_line)
                if pkg:
                    dependencies[pkg] = version

        return dependencies

    def _extract_all_optional_deps(self, content: str) -> Dict[str, Optional[str]]:
        """
        Extract all optional dependencies from pyproject.toml.

        Args:
            content: TOML file content

        Returns:
            Dictionary of all optional dependencies
        """
        dependencies: Dict[str, Optional[str]] = {}

        match = re.search(_TOML_OPTIONAL_DEPS_SECTION, content)
        if not match:
            return dependencies

        section_content = self._extract_toml_section(
            content[match.end():], _TOML_PROJECT_SECTION
        )
        if not section_content:
            section_content = content[match.end():]

        for array_match in re.finditer(_TOML_ARRAY_ASSIGNMENT_PATTERN, section_content):
            array_start = array_match.end() - 1  # Position of opening bracket
            array_end = self._find_matching_bracket(section_content, array_start)

            if array_end > array_start:
                array_content = section_content[array_start + 1:array_end]
                entries = self._split_toml_array(array_content)
                for entry in entries:
                    entry = entry.strip().strip('"\'')
                    if entry:
                        pkg, version = self._parse_requirement_line(entry)
                        if pkg:
                            dependencies[pkg] = version

        return dependencies

    def _find_matching_bracket(self, content: str, start_pos: int) -> int:
        """
        Find the position of the matching closing bracket.

        Args:
            content: String containing brackets
            start_pos: Position of opening bracket

        Returns:
            Position of matching closing bracket, or start_pos + 1 if not found
        """
        bracket_count = 1

        for i in range(start_pos + 1, len(content)):
            if content[i] == _OPENING_BRACKET:
                bracket_count += 1
            elif content[i] == _CLOSING_BRACKET:
                bracket_count -= 1
                if bracket_count == 0:
                    return i

        return start_pos + 1

    def _split_toml_array(self, array_content: str) -> List[str]:
        """
        Split TOML array content by comma, respecting quotes.

        Args:
            array_content: Content between square brackets

        Returns:
            List of array entries
        """
        entries: List[str] = []
        current: List[str] = []
        in_quotes = False
        quote_char: Optional[str] = None

        for char in array_content:
            if char in _QUOTE_CHARS and (not current or current[-1] != _BACKSLASH):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current.append(char)
            elif char == _COMMA and not in_quotes:
                entries.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

        # Add last entry
        if current:
            entries.append(''.join(current).strip())

        return entries


class LibraryDetector:
    """Orchestrator for detecting libraries from imports and dependency files."""

    def __init__(self) -> None:
        """Initialize the LibraryDetector."""
        self.import_scanner = ImportScanner()
        self.dependency_parser = DependencyFileParser()

    def detect_libraries(
        self,
        python_files: Optional[List[Path]] = None,
        requirements_txt: Optional[Path] = None,
        pyproject_toml: Optional[Path] = None,
        directory: Optional[Path] = None,
        filter_stdlib: bool = True,
    ) -> Dict[str, Optional[str]]:
        """
        Detect libraries from Python files and dependency files.

        Args:
            python_files: List of Python files to scan
            requirements_txt: Path to requirements.txt
            pyproject_toml: Path to pyproject.toml
            directory: Directory to scan recursively for Python files
            filter_stdlib: Whether to filter out standard library imports

        Returns:
            Dictionary mapping library names to version specifiers
        """
        libraries: Dict[str, Optional[str]] = {}

        # Scan Python files
        scanned_files = self._collect_python_files(python_files, directory)
        if scanned_files:
            self._scan_imports(scanned_files, libraries, filter_stdlib)

        # Parse dependency files and merge versions
        self._merge_dependency_versions(
            libraries, requirements_txt, pyproject_toml
        )

        return libraries

    def _collect_python_files(
        self, python_files: Optional[List[Path]], directory: Optional[Path]
    ) -> List[Path]:
        """
        Collect all Python files to scan.

        Args:
            python_files: Explicit list of Python files
            directory: Directory to scan recursively

        Returns:
            Combined list of Python files
        """
        files = python_files[:] if python_files else []

        if directory:
            files.extend(self._find_python_files(directory))

        return files

    def _scan_imports(
        self, python_files: List[Path],
        libraries: Dict[str, Optional[str]],
        filter_stdlib: bool
    ) -> None:
        """
        Scan Python files for imports and update libraries dict.

        Args:
            python_files: List of files to scan
            libraries: Dictionary to update with found imports
            filter_stdlib: Whether to filter standard library
        """
        imports = self.import_scanner.scan_files(python_files, filter_stdlib=False)

        for imp in imports:
            if filter_stdlib and imp in STANDARD_LIBRARY:
                continue
            libraries[imp] = None

    def _merge_dependency_versions(
        self,
        libraries: Dict[str, Optional[str]],
        requirements_txt: Optional[Path],
        pyproject_toml: Optional[Path],
    ) -> None:
        """
        Merge version information from dependency files.

        Args:
            libraries: Dictionary to update with version info
            requirements_txt: Path to requirements.txt
            pyproject_toml: Path to pyproject.toml
        """
        dependencies = self.dependency_parser.parse_all(
            requirements_txt=requirements_txt,
            pyproject_toml=pyproject_toml,
        )

        # Update libraries with versions from dependencies
        for lib, version in dependencies.items():
            libraries[lib] = version

    def _find_python_files(self, directory: Path) -> List[Path]:
        """
        Find all Python files in a directory recursively.

        Args:
            directory: Directory to search

        Returns:
            List of Python file paths
        """
        if not directory.exists() or not directory.is_dir():
            return []

        return [
            path for path in directory.rglob("*.py")
            if path.is_file()
        ]
