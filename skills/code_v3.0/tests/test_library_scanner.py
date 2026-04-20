#!/usr/bin/env python3
"""Unit tests for library_scanner.py module.

This test suite verifies the library scanning functionality which detects
import statements from Python source code and parses dependency files.

Run with: pytest P:/\\.claude/skills/code/tests/test_library_scanner.py -v
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.library_scanner import (
    ImportScanner,
    DependencyFileParser,
    LibraryDetector,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup happens automatically via tempfile


class TestImportScanner:
    """Test ImportScanner class for AST-based import detection."""

    def test_detects_simple_import(self, temp_dir):
        """
        Test that ImportScanner detects simple import statements.

        Given: A Python file with simple imports (import X)
        When: The file is scanned
        Then: All imported modules are detected
        """
        # Arrange
        test_file = temp_dir / "test_simple.py"
        test_file.write_text("""
import os
import sys
import json

def main():
    pass
""")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_file(test_file)

        # Assert
        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports
        assert len(imports) == 3

    def test_detects_from_import(self, temp_dir):
        """
        Test that ImportScanner detects 'from' import statements.

        Given: A Python file with 'from X import Y' statements
        When: The file is scanned
        Then: The module names (X) are detected
        """
        # Arrange
        test_file = temp_dir / "test_from.py"
        test_file.write_text("""
from pathlib import Path
from collections import defaultdict
from typing import List, Dict
""")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_file(test_file)

        # Assert
        assert "pathlib" in imports
        assert "collections" in imports
        assert "typing" in imports

    def test_detects_mixed_imports(self, temp_dir):
        """
        Test that ImportScanner handles mixed import styles.

        Given: A Python file with both 'import X' and 'from X import Y'
        When: The file is scanned
        Then: All modules are detected without duplication
        """
        # Arrange
        test_file = temp_dir / "test_mixed.py"
        test_file.write_text("""
import os
from pathlib import Path
import sys
from typing import List
import json
""")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_file(test_file)

        # Assert
        assert "os" in imports
        assert "pathlib" in imports
        assert "sys" in imports
        assert "typing" in imports
        assert "json" in imports
        assert len(imports) == 5

    def test_ignores_local_imports(self, temp_dir):
        """
        Test that ImportScanner can distinguish external from local imports.

        Given: A Python file with relative/local imports
        When: The file is scanned
        Then: Local imports are excluded from results
        """
        # Arrange
        test_file = temp_dir / "test_local.py"
        test_file.write_text("""
import os
from .local_module import LocalClass
from ..sibling import SiblingClass
from .subpackage import helper
import sys
""")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_file(test_file)

        # Assert
        assert "os" in imports
        assert "sys" in imports
        # Local imports should be excluded
        assert "local_module" not in imports
        assert "sibling" not in imports
        assert "subpackage" not in imports

    def test_handles_empty_file(self, temp_dir):
        """
        Test that ImportScanner handles files with no imports.

        Given: An empty Python file or file with no imports
        When: The file is scanned
        Then: Empty list is returned
        """
        # Arrange
        test_file = temp_dir / "test_empty.py"
        test_file.write_text("""
# Just a comment
def main():
    pass
""")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_file(test_file)

        # Assert
        assert imports == []

    def test_scans_multiple_files(self, temp_dir):
        """
        Test that ImportScanner can scan multiple files.

        Given: Multiple Python files with different imports
        When: All files are scanned
        Then: Imports from all files are combined
        """
        # Arrange
        file1 = temp_dir / "file1.py"
        file1.write_text("import os\nimport sys\n")

        file2 = temp_dir / "file2.py"
        file2.write_text("import json\nfrom pathlib import Path\n")

        file3 = temp_dir / "file3.py"
        file3.write_text("import re\n")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_files([file1, file2, file3])

        # Assert
        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports
        assert "pathlib" in imports
        assert "re" in imports
        assert len(imports) == 5

    def test_deduplicates_imports(self, temp_dir):
        """
        Test that ImportScanner deduplicates imports across files.

        Given: Multiple files importing the same module
        When: All files are scanned
        Then: Each module appears only once in results
        """
        # Arrange
        file1 = temp_dir / "file1.py"
        file1.write_text("import os\nimport sys\n")

        file2 = temp_dir / "file2.py"
        file2.write_text("import os\nimport json\n")

        file3 = temp_dir / "file3.py"
        file3.write_text("import sys\nimport re\n")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_files([file1, file2, file3])

        # Assert
        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports
        assert "re" in imports
        # No duplicates
        assert len(imports) == 4

    def test_filters_standard_library(self, temp_dir):
        """
        Test that ImportScanner can filter standard library modules.

        Given: A file with both stdlib and external imports
        When: scan_file is called with filter_stdlib=True
        Then: Only external packages are returned
        """
        # Arrange
        test_file = temp_dir / "test_filter.py"
        test_file.write_text("""
import os
import sys
import requests
import numpy
from pathlib import Path
from pandas import DataFrame
""")

        # Act
        scanner = ImportScanner()
        imports = scanner.scan_file(test_file, filter_stdlib=True)

        # Assert
        # Standard library should be filtered out
        assert "os" not in imports
        assert "sys" not in imports
        assert "pathlib" not in imports
        # External packages should remain
        assert "requests" in imports
        assert "numpy" in imports
        assert "pandas" in imports


class TestDependencyFileParser:
    """Test DependencyFileParser class for parsing dependency files."""

    def test_parses_requirements_txt_simple(self, temp_dir):
        """
        Test parsing requirements.txt with simple package names.

        Given: A requirements.txt with package names only
        When: The file is parsed
        Then: Dictionary with package names and None versions is returned
        """
        # Arrange
        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("""
requests
numpy
pandas
""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_requirements_txt(requirements_file)

        # Assert
        assert "requests" in deps
        assert "numpy" in deps
        assert "pandas" in deps
        assert deps["requests"] is None
        assert deps["numpy"] is None
        assert deps["pandas"] is None

    def test_parses_requirements_txt_with_versions(self, temp_dir):
        """
        Test parsing requirements.txt with version specifiers.

        Given: A requirements.txt with package==version
        When: The file is parsed
        Then: Versions are correctly extracted
        """
        # Arrange
        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("""
requests==2.28.0
numpy>=1.21.0
pandas~=1.4.0
django>=3.2,<4.0
flask==2.0.1
""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_requirements_txt(requirements_file)

        # Assert
        assert deps["requests"] == "2.28.0"
        assert deps["numpy"] == ">=1.21.0"
        assert deps["pandas"] == "~=1.4.0"
        assert deps["django"] == ">=3.2,<4.0"
        assert deps["flask"] == "2.0.1"

    def test_parses_requirements_txt_with_comments_and_blank_lines(self, temp_dir):
        """
        Test parsing requirements.txt with comments and blank lines.

        Given: A requirements.txt with comments (#) and blank lines
        When: The file is parsed
        Then: Comments and blank lines are ignored
        """
        # Arrange
        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("""
# This is a comment
requests==2.28.0

numpy>=1.21.0
# Another comment

pandas~=1.4.0

""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_requirements_txt(requirements_file)

        # Assert
        assert len(deps) == 3
        assert "requests" in deps
        assert "numpy" in deps
        assert "pandas" in deps

    def test_handles_missing_requirements_txt(self, temp_dir):
        """
        Test graceful handling of missing requirements.txt.

        Given: A path to a non-existent requirements.txt
        When: The file is parsed
        Then: Empty dictionary is returned (no exception)
        """
        # Arrange
        missing_file = temp_dir / "nonexistent_requirements.txt"

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_requirements_txt(missing_file)

        # Assert
        assert deps == {}

    def test_parses_pyproject_toml_dependencies(self, temp_dir):
        """
        Test parsing pyproject.toml dependencies.

        Given: A pyproject.toml with dependencies section
        When: The file is parsed
        Then: Dependencies are extracted with versions
        """
        # Arrange
        pyproject_file = temp_dir / "pyproject.toml"
        pyproject_file.write_text("""
[project]
name = "myproject"
dependencies = [
    "requests==2.28.0",
    "numpy>=1.21.0",
    "pandas~=1.4.0",
]
""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_pyproject_toml(pyproject_file)

        # Assert
        assert "requests" in deps
        assert "numpy" in deps
        assert "pandas" in deps
        assert deps["requests"] == "2.28.0"
        assert deps["numpy"] == ">=1.21.0"
        assert deps["pandas"] == "~=1.4.0"

    def test_parses_pyproject_toml_optional_dependencies(self, temp_dir):
        """
        Test parsing pyproject.toml optional dependencies.

        Given: A pyproject.toml with optional-dependencies sections
        When: The file is parsed
        Then: All optional dependencies are extracted
        """
        # Arrange
        pyproject_file = temp_dir / "pyproject.toml"
        pyproject_file.write_text("""
[project.optional-dependencies]
dev = ["pytest>=7.0", "black>=22.0"]
docs = ["sphinx>=4.0", "sphinx-rtd-theme>=1.0"]
test = ["pytest-cov>=3.0"]
""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_pyproject_toml(pyproject_file)

        # Assert
        assert "pytest" in deps
        assert "black" in deps
        assert "sphinx" in deps
        assert "sphinx-rtd-theme" in deps
        assert "pytest-cov" in deps

    def test_handles_missing_pyproject_toml(self, temp_dir):
        """
        Test graceful handling of missing pyproject.toml.

        Given: A path to a non-existent pyproject.toml
        When: The file is parsed
        Then: Empty dictionary is returned (no exception)
        """
        # Arrange
        missing_file = temp_dir / "nonexistent_pyproject.toml"

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_pyproject_toml(missing_file)

        # Assert
        assert deps == {}

    def test_handles_malformed_pyproject_toml(self, temp_dir):
        """
        Test graceful handling of malformed pyproject.toml.

        Given: A pyproject.toml with invalid TOML syntax
        When: The file is parsed
        Then: Empty dictionary is returned (no exception)
        """
        # Arrange
        malformed_file = temp_dir / "malformed.toml"
        malformed_file.write_text("""
[project
dependencies = [
    "requests==2.28.0"
    invalid syntax here
""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_pyproject_toml(malformed_file)

        # Assert
        assert deps == {}

    def test_parses_all_sources(self, temp_dir):
        """
        Test parsing both requirements.txt and pyproject.toml.

        Given: Both requirements.txt and pyproject.toml exist
        When: parse_all is called
        Then: Dependencies from both files are combined
        """
        # Arrange
        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("""
requests==2.28.0
numpy>=1.21.0
""")

        pyproject_file = temp_dir / "pyproject.toml"
        pyproject_file.write_text("""
[project]
dependencies = [
    "pandas~=1.4.0",
    "django>=3.2",
]
""")

        # Act
        parser = DependencyFileParser()
        deps = parser.parse_all(
            requirements_txt=requirements_file,
            pyproject_toml=pyproject_file
        )

        # Assert
        assert "requests" in deps
        assert "numpy" in deps
        assert "pandas" in deps
        assert "django" in deps
        assert len(deps) == 4


class TestLibraryDetector:
    """Test LibraryDetector orchestrator class."""

    def test_combines_imports_and_dependencies(self, temp_dir):
        """
        Test that LibraryDetector combines imports and declared dependencies.

        Given: Python files with imports and requirements.txt with deps
        When: detect_libraries is called
        Then: Unified list with versions from dependencies is returned
        """
        # Arrange
        test_file = temp_dir / "main.py"
        test_file.write_text("""
import requests
import numpy
import pandas
import json  # stdlib
import os  # stdlib
""")

        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("""
requests==2.28.0
numpy>=1.21.0
pandas~=1.4.0
""")

        # Act
        detector = LibraryDetector()
        libraries = detector.detect_libraries(
            python_files=[test_file],
            requirements_txt=requirements_file
        )

        # Assert
        # Should have external packages with versions
        assert "requests" in libraries
        assert "numpy" in libraries
        assert "pandas" in libraries
        assert libraries["requests"] == "2.28.0"
        assert libraries["numpy"] == ">=1.21.0"
        assert libraries["pandas"] == "~=1.4.0"
        # Should filter out stdlib
        assert "json" not in libraries
        assert "os" not in libraries

    def test_handles_imports_without_versions(self, temp_dir):
        """
        Test that imports without declared versions are included.

        Given: Python file imports a package not in requirements.txt
        When: detect_libraries is called
        Then: Package is included with version=None
        """
        # Arrange
        test_file = temp_dir / "main.py"
        test_file.write_text("""
import requests
import unknown_package
""")

        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("""
requests==2.28.0
""")

        # Act
        detector = LibraryDetector()
        libraries = detector.detect_libraries(
            python_files=[test_file],
            requirements_txt=requirements_file
        )

        # Assert
        assert "requests" in libraries
        assert libraries["requests"] == "2.28.0"
        assert "unknown_package" in libraries
        assert libraries["unknown_package"] is None

    def test_scans_directory_recursively(self, temp_dir):
        """
        Test that LibraryDetector can scan a directory recursively.

        Given: A directory structure with multiple Python files
        When: detect_libraries is called with directory path
        Then: All Python files in the directory are scanned
        """
        # Arrange
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "nested").mkdir()

        (temp_dir / "main.py").write_text("import os\nimport requests\n")
        (temp_dir / "subdir" / "helper.py").write_text("import sys\nimport numpy\n")
        (temp_dir / "subdir" / "nested" / "util.py").write_text("import json\nimport pandas\n")

        # Act
        detector = LibraryDetector()
        libraries = detector.detect_libraries(directory=temp_dir)

        # Assert
        # Should find all imports from all files
        assert "requests" in libraries
        assert "numpy" in libraries
        assert "pandas" in libraries
        # Should filter stdlib
        assert "os" not in libraries
        assert "sys" not in libraries
        assert "json" not in libraries

    def test_handles_missing_files_gracefully(self, temp_dir):
        """
        Test that LibraryDetector handles missing dependency files gracefully.

        Given: Python files exist but no requirements.txt/pyproject.toml
        When: detect_libraries is called
        Then: Imports are detected without versions (no exception)
        """
        # Arrange
        test_file = temp_dir / "main.py"
        test_file.write_text("""
import requests
import numpy
""")

        missing_requirements = temp_dir / "nonexistent_requirements.txt"

        # Act
        detector = LibraryDetector()
        libraries = detector.detect_libraries(
            python_files=[test_file],
            requirements_txt=missing_requirements
        )

        # Assert
        assert "requests" in libraries
        assert "numpy" in libraries
        assert libraries["requests"] is None
        assert libraries["numpy"] is None

    def test_returns_empty_dict_for_no_inputs(self, temp_dir):
        """
        Test that LibraryDetector returns empty dict when no inputs provided.

        Given: No Python files or dependency files
        When: detect_libraries is called
        Then: Empty dictionary is returned
        """
        # Arrange & Act
        detector = LibraryDetector()
        libraries = detector.detect_libraries()

        # Assert
        assert libraries == {}

    def test_deduplicates_across_sources(self, temp_dir):
        """
        Test that LibraryDetector deduplicates libraries across sources.

        Given: Same package in imports and requirements.txt
        When: detect_libraries is called
        Then: Package appears once with version from requirements.txt
        """
        # Arrange
        test_file = temp_dir / "main.py"
        test_file.write_text("import requests\n")

        requirements_file = temp_dir / "requirements.txt"
        requirements_file.write_text("requests==2.28.0\n")

        pyproject_file = temp_dir / "pyproject.toml"
        pyproject_file.write_text("""
[project]
dependencies = ["requests==2.28.0"]
""")

        # Act
        detector = LibraryDetector()
        libraries = detector.detect_libraries(
            python_files=[test_file],
            requirements_txt=requirements_file,
            pyproject_toml=pyproject_file
        )

        # Assert
        assert len([lib for lib in libraries if lib == "requests"]) == 1
        assert libraries["requests"] == "2.28.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
