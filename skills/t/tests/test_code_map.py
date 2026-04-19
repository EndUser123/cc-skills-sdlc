#!/usr/bin/env python3
"""Test code map visualization wrapper."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from code_map import CodeMapVisualizer


def test_generate_layer_view():
    """Test layer extraction and formatting from codemap."""
    # Mock codemap with file structure
    codemap = {
        "file_structure": {
            "main_files": [
                "src/ui/view.py",
                "src/business/service.py",
                "src/data/repository.py",
                "src/util/config.py",
            ],
            "test_files": [
                "tests/test_view.py",
                "tests/test_service.py",
            ],
            "help_files": [
                "docs/interface.md",
            ],
        },
        "relationships": {},
    }

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_layer_view()

    # Verify markdown structure
    assert "## Layer Architecture View" in output
    assert "### Presentation Layer" in output
    assert "### Business Layer" in output
    assert "### Data Layer" in output
    assert "### Infrastructure Layer" in output

    # Verify file categorization
    assert "src/ui/view.py" in output
    assert "src/business/service.py" in output
    assert "src/data/repository.py" in output
    assert "src/util/config.py" in output


def test_generate_layer_view_empty_codemap():
    """Test layer view with empty codemap."""
    codemap = {"file_structure": {}, "relationships": {}}

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_layer_view()

    # Should still have structure but no files
    assert "## Layer Architecture View" in output
    # All layers should be empty (no file listings)


def test_generate_dependency_graph():
    """Test dependency graph generation from relationships."""
    codemap = {
        "file_structure": {},
        "relationships": {
            "python_imports": {
                "src/router.py": ["src/auth.py", "src/validator.py", "src/handler.py"],
                "src/auth.py": ["src/database.py"],
            }
        },
    }

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_dependency_graph()

    # Verify mermaid graph structure
    assert "## Dependency Graph" in output
    assert "```mermaid" in output
    assert "graph TD" in output

    # Verify node names (slashes and dots replaced with underscores)
    assert "src_router_py --> src_auth_py" in output
    assert "src_auth_py --> src_database_py" in output


def test_generate_dependency_graph_empty_relationships():
    """Test dependency graph with no relationships."""
    codemap = {"file_structure": {}, "relationships": {}}

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_dependency_graph()

    # Should have structure but no edges
    assert "## Dependency Graph" in output
    assert "```mermaid" in output
    assert "graph TD" in output


def test_generate_test_heatmap():
    """Test test coverage heatmap generation."""
    codemap = {
        "file_structure": {
            "main_files": [
                "src/module_a.py",
                "src/module_b.py",
                "src/module_c.py",
            ]
        },
        "relationships": {},
    }

    test_results = {
        "src/module_a.py": {"coverage_percent": 92.0},
        "src/module_b.py": {"coverage_percent": 67.0},
        "src/module_c.py": {"coverage_percent": 45.0},
    }

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_test_heatmap(test_results)

    # Verify heatmap structure
    assert "## Test Coverage Heatmap" in output

    # Verify emoji indicators
    assert "🟢 src/module_a.py: 92.0%" in output  # >= 80%
    assert "🟡 src/module_b.py: 67.0%" in output  # >= 50
    assert "🔴 src/module_c.py: 45.0%" in output  # < 50


def test_generate_test_heatmap_missing_results():
    """Test heatmap with missing test results."""
    codemap = {
        "file_structure": {
            "main_files": ["src/missing.py"]
        },
        "relationships": {},
    }

    test_results = {}  # No results

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_test_heatmap(test_results)

    # Missing file should default to 0%
    assert "🔴 src/missing.py: 0.0%" in output


def test_extract_layers_keyword_matching():
    """Test layer extraction based on path keywords."""
    codemap = {
        "file_structure": {
            "main_files": [
                "src/ui_components/view.py",  # presentation
                "src/services/business_logic.py",  # business
                "src/models/data_model.py",  # data
                "src/infra/config.py",  # infrastructure
                "src/other/unknown.py",  # no match (should not be categorized)
            ],
            "test_files": [],
            "help_files": [],
        },
        "relationships": {},
    }

    visualizer = CodeMapVisualizer(codemap)
    layers = visualizer._extract_layers()

    # Verify categorization
    assert "src/ui_components/view.py" in layers["presentation"]
    assert "src/services/business_logic.py" in layers["business"]
    assert "src/models/data_model.py" in layers["data"]
    assert "src/infra/config.py" in layers["infrastructure"]

    # File without matching keyword should not appear in any layer
    assert "src/other/unknown.py" not in layers["presentation"]
    assert "src/other/unknown.py" not in layers["business"]
    assert "src/other/unknown.py" not in layers["data"]
    assert "src/other/unknown.py" not in layers["infrastructure"]


def test_format_dependencies_limit():
    """Test that dependency graph limits to 5 imports per module."""
    codemap = {
        "file_structure": {},
        "relationships": {
            "python_imports": {
                "src/big_module.py": [
                    "src/dep1.py",
                    "src/dep2.py",
                    "src/dep3.py",
                    "src/dep4.py",
                    "src/dep5.py",
                    "src/dep6.py",  # Should be excluded (6th dependency)
                    "src/dep7.py",  # Should be excluded (7th dependency)
                ]
            }
        },
    }

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_dependency_graph()

    # Should have first 5 dependencies
    assert "src_big_module_py --> src_dep1_py" in output
    assert "src_big_module_py --> src_dep5_py" in output

    # Should NOT have 6th and 7th dependencies
    assert "src_big_module_py --> src_dep6_py" not in output
    assert "src_big_module_py --> src_dep7_py" not in output


def test_format_layers_limit():
    """Test that layer view limits to 5 files per layer."""
    codemap = {
        "file_structure": {
            "main_files": [
                "src/presentation/file1.py",
                "src/presentation/file2.py",
                "src/presentation/file3.py",
                "src/presentation/file4.py",
                "src/presentation/file5.py",
                "src/presentation/file6.py",  # Should show "X more"
            ],
        },
        "relationships": {},
    }

    visualizer = CodeMapVisualizer(codemap)
    output = visualizer.generate_layer_view()

    # Should list first 5 files
    assert "- src/presentation/file1.py" in output
    assert "- src/presentation/file5.py" in output

    # Should show "... and 1 more" (6 files - 5 shown = 1 more)
    assert "... and 1 more" in output


if __name__ == "__main__":
    test_generate_layer_view()
    print("✅ test_generate_layer_view passed")

    test_generate_layer_view_empty_codemap()
    print("✅ test_generate_layer_view_empty_codemap passed")

    test_generate_dependency_graph()
    print("✅ test_generate_dependency_graph passed")

    test_generate_dependency_graph_empty_relationships()
    print("✅ test_generate_dependency_graph_empty_relationships passed")

    test_generate_test_heatmap()
    print("✅ test_generate_test_heatmap passed")

    test_generate_test_heatmap_missing_results()
    print("✅ test_generate_test_heatmap_missing_results passed")

    test_extract_layers_keyword_matching()
    print("✅ test_extract_layers_keyword_matching passed")

    test_format_dependencies_limit()
    print("✅ test_format_dependencies_limit passed")

    test_format_layers_limit()
    print("✅ test_format_layers_limit passed")

    print("\nAll code_map tests passed!")
