#!/usr/bin/env python3
r"""
Unit tests for Git Bash path normalization in state files.

RED PHASE TESTS - These tests FAIL because scripts/fix_state_paths.py doesn't exist yet.

Tests cover:
- Git Bash path detection (/p/..., /c/..., etc.)
- Normalization to Windows native format (P:\\\\\\..., C:\...)
- JSON file modification in place
- Backup creation and restoration
- Recursive directory scanning
- Batch processing of multiple files
- Path normalization in nested structures
- CLI invocation and dry-run mode
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory with subdirectories for testing."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create nested directory structure
    state_dir = temp_dir / ".claude" / "state"
    state_dir.mkdir(parents=True)

    subdir = state_dir / "subdir"
    subdir.mkdir(parents=True)

    yield state_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_json_file(temp_state_dir):
    """Create a sample JSON file with Git Bash paths."""
    json_file = temp_state_dir / "test_state.json"

    data = {
        "project_root": "/p/.claude/skills/code",
        "script_path": "/p/.claude/skills/code/scripts/test.py",
        "relative_path": "src/utils/helper.py",
        "nested": {
            "deep_path": "/p/.claude/skills/code/utils/evidence.py",
            "array": [
                "/p/.claude/skills/code/tests/test_fix.py",
                "relative/path.txt"
            ]
        }
    }

    json_file.write_text(json.dumps(data, indent=2))
    return json_file


@pytest.fixture
def sample_mixed_paths_file(temp_state_dir):
    """Create JSON file with mixed path formats."""
    json_file = temp_state_dir / "mixed_paths.json"

    data = {
        "git_bash": "/p/.claude/skills/code",
        "windows": "P:\\\\\\\\\.claude\\\\skills\\\\code",
        "relative": "src/main.py",
        "another_drive": "/c/Users/test",
        "nested": {
            "git_path": "/p/.claude/config.json",
            "empty_string": "",
            "null_value": None
        }
    }

    json_file.write_text(json.dumps(data, indent=2))
    return json_file


@pytest.fixture
def empty_json_file(temp_state_dir):
    """Create an empty JSON file."""
    json_file = temp_state_dir / "empty.json"
    json_file.write_text("{}")
    return json_file


@pytest.fixture
def no_paths_file(temp_state_dir):
    """Create JSON file with no path values."""
    json_file = temp_state_dir / "no_paths.json"

    data = {
        "name": "test",
        "count": 42,
        "active": True,
        "tags": ["test", "example"]
    }

    json_file.write_text(json.dumps(data, indent=2))
    return json_file


@pytest.fixture
def multiple_json_files(temp_state_dir):
    """Create multiple JSON files in different directories."""
    files = []

    # File in root state dir
    file1 = temp_state_dir / "state1.json"
    file1.write_text(json.dumps({"path": "/p/.claude/test1"}, indent=2))
    files.append(file1)

    # File in subdirectory
    file2 = temp_state_dir / "subdir" / "state2.json"
    file2.write_text(json.dumps({"path": "/p/.claude/test2"}, indent=2))
    files.append(file2)

    # File with no paths
    file3 = temp_state_dir / "no_paths.json"
    file3.write_text(json.dumps({"name": "test"}, indent=2))
    files.append(file3)

    return files


class TestPathDetection:
    """Test Git Bash path detection in JSON files."""

    def test_fix_paths_detects_git_bash_paths(self, sample_json_file):
        """Should detect Git Bash paths (/p/...) in JSON files."""
        # This import will FAIL - script doesn't exist yet
        from scripts.fix_state_paths import detect_git_bash_paths

        data = json.loads(sample_json_file.read_text())
        git_paths = detect_git_bash_paths(data)

        # Should find all Git Bash paths
        assert len(git_paths) >= 3
        assert "/p/.claude/skills/code" in git_paths
        assert "/p/.claude/skills/code/scripts/test.py" in git_paths
        assert "/p/.claude/skills/code/utils/evidence.py" in git_paths

    def test_fix_paths_detects_multiple_drives(self, sample_mixed_paths_file):
        """Should detect paths from multiple drives (/p/, /c/, /d/, etc.)."""
        from scripts.fix_state_paths import detect_git_bash_paths

        data = json.loads(sample_mixed_paths_file.read_text())
        git_paths = detect_git_bash_paths(data)

        # Should find paths from different drives
        assert any("/p/" in path for path in git_paths)
        assert any("/c/" in path for path in git_paths)

    def test_fix_paths_ignores_windows_paths(self, sample_mixed_paths_file):
        """Should ignore Windows native paths (P:\\\\\\\\\..., C:\\\\...)."""
        from scripts.fix_state_paths import detect_git_bash_paths

        data = json.loads(sample_mixed_paths_file.read_text())
        git_paths = detect_git_bash_paths(data)

        # Should not include Windows paths
        assert not any(":\\\\" in path or ":/" in path for path in git_paths)

    def test_fix_paths_ignores_relative_paths(self, sample_json_file):
        """Should ignore relative paths (no leading slash)."""
        from scripts.fix_state_paths import detect_git_bash_paths

        data = json.loads(sample_json_file.read_text())
        git_paths = detect_git_bash_paths(data)

        # Should not include relative paths
        assert "src/utils/helper.py" not in git_paths
        assert "relative/path.txt" not in git_paths


class TestPathNormalization:
    """Test Git Bash path normalization to Windows format."""

    def test_fix_paths_normalizes_to_windows(self):
        """Should convert Git Bash paths to Windows native format."""
        from scripts.fix_state_paths import normalize_path

        # Test P: drive
        git_bash_path = "/p/.claude/skills/code"
        windows_path = normalize_path(git_bash_path)

        assert windows_path == "P:\\\\\\\\\.claude\\\\skills\\\\code"

    def test_fix_paths_multiple_drives(self):
        """Should handle multiple drive letters (/c/, /d/, /p/, etc.)."""
        from scripts.fix_state_paths import normalize_path

        test_cases = [
            ("/c/Users/test", "C:\\\\Users\\\\test"),
            ("/d/Projects/code", "D:\\\\Projects\\\\code"),
            ("/p/.claude/skills", "P:\\\\\\\\\.claude\\\\skills"),
        ]

        for git_bash, expected_windows in test_cases:
            result = normalize_path(git_bash)
            assert result == expected_windows

    def test_fix_paths_preserves_non_git_bash_paths(self):
        """Should preserve paths that aren't Git Bash format."""
        from scripts.fix_state_paths import normalize_path

        # Windows paths should be preserved
        windows_path = "P:\\\\\\\\\.claude\\\\skills\\\\code"
        assert normalize_path(windows_path) == windows_path

        # Relative paths should be preserved
        relative_path = "src/utils/helper.py"
        assert normalize_path(relative_path) == relative_path

    def test_fix_paths_handles_special_characters(self):
        """Should handle paths with spaces, dashes, dots, etc."""
        from scripts.fix_state_paths import normalize_path

        test_cases = [
            "/p/.claude/skills/code-with-dashes",
            "/p/.claude/skills/code.with.dots",
            "/p/Program Files/project",
        ]

        for path in test_cases:
            result = normalize_path(path)
            # Should convert drive letter and preserve rest
            assert result[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            assert ":\\\\" in result or ":/" in result

    def test_fix_paths_empty_and_null_values(self):
        """Should handle empty strings and None values gracefully."""
        from scripts.fix_state_paths import normalize_path

        assert normalize_path("") == ""
        assert normalize_path(None) is None


class TestJSONModification:
    """Test in-place JSON file modification."""

    def test_fix_paths_updates_json_files(self, temp_state_dir, sample_json_file):
        """Should modify JSON files in place with normalized paths."""
        from scripts.fix_state_paths import fix_paths_in_file

        original_content = sample_json_file.read_text()
        changes = fix_paths_in_file(sample_json_file)

        modified_content = sample_json_file.read_text()

        # Should report changes made
        assert changes > 0

        # Content should be different
        assert modified_content != original_content

        # Should contain Windows paths
        assert "P:\\\\\\\\\" in modified_content
        assert "/p/" not in modified_content

    def test_fix_paths_preserves_non_path_content(self, temp_state_dir, no_paths_file):
        """Should preserve non-path content unchanged."""
        from scripts.fix_state_paths import fix_paths_in_file

        original_content = no_paths_file.read_text()
        changes = fix_paths_in_file(no_paths_file)

        modified_content = no_paths_file.read_text()

        # Should report no changes
        assert changes == 0

        # Content should be identical
        assert modified_content == original_content

    def test_fix_paths_nested_paths(self, temp_state_dir):
        """Should normalize paths in nested objects and arrays."""
        from scripts.fix_state_paths import fix_paths_in_file

        json_file = temp_state_dir / "nested.json"

        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "deep_path": "/p/.claude/deep/file.py"
                    }
                },
                "array": [
                    {"item": "/p/.claude/array/item.py"},
                    "non_path_value"
                ]
            }
        }

        json_file.write_text(json.dumps(data, indent=2))
        changes = fix_paths_in_file(json_file)

        modified_data = json.loads(json_file.read_text())

        # Should find and normalize deep nested path
        assert changes > 0
        assert modified_data["level1"]["level2"]["level3"]["deep_path"] == "P:\\\\\\\\\.claude\\\\deep\\\\file.py"

        # Should normalize path in array
        assert modified_data["level1"]["array"][0]["item"] == "P:\\\\\\\\\.claude\\\\array\\\\item.py"

    def test_fix_paths_valid_json_output(self, temp_state_dir, sample_json_file):
        """Should produce valid JSON after modification."""
        from scripts.fix_state_paths import fix_paths_in_file

        fix_paths_in_file(sample_json_file)

        # Should be parseable as JSON
        modified_content = sample_json_file.read_text()
        data = json.loads(modified_content)

        # Should have expected structure
        assert isinstance(data, dict)
        assert "project_root" in data

    def test_fix_paths_empty_json_file(self, temp_state_dir, empty_json_file):
        """Should handle empty JSON objects gracefully."""
        from scripts.fix_state_paths import fix_paths_in_file

        changes = fix_paths_in_file(empty_json_file)

        # Should handle without error
        assert changes == 0

        # File should still be valid JSON
        data = json.loads(empty_json_file.read_text())
        assert isinstance(data, dict)


class TestBackupBehavior:
    """Test backup creation and restoration."""

    def test_fix_paths_creates_backup(self, temp_state_dir, sample_json_file):
        """Should create .backup file before modifying."""
        from scripts.fix_state_paths import fix_paths_in_file

        original_content = sample_json_file.read_text()

        fix_paths_in_file(sample_json_file, backup=True)

        # Backup file should exist
        backup_file = sample_json_file.with_suffix(".json.backup")
        assert backup_file.exists()

        # Backup should contain original content
        backup_content = backup_file.read_text()
        assert backup_content == original_content

    def test_fix_paths_backup_format(self, temp_state_dir, sample_json_file):
        """Backup should preserve original file exactly."""
        from scripts.fix_state_paths import fix_paths_in_file

        original_content = sample_json_file.read_text()

        fix_paths_in_file(sample_json_file, backup=True)

        backup_file = sample_json_file.with_suffix(".json.backup")

        # Content should be identical
        assert backup_file.read_text() == original_content

        # Should be valid JSON
        json.loads(backup_file.read_text())

    def test_fix_paths_restores_on_error(self, temp_state_dir):
        """Should restore backup if modification fails."""
        from scripts.fix_state_paths import fix_paths_in_file_with_rollback

        json_file = temp_state_dir / "test.json"
        original_data = {"path": "/p/.claude/test"}
        json_file.write_text(json.dumps(original_data, indent=2))

        original_content = json_file.read_text()

        # Simulate error during modification
        # This would need to be implemented in the script
        # For now, test the pattern exists
        try:
            fix_paths_in_file_with_rollback(json_file, simulate_error=True)
        except Exception:
            pass

        # File should be restored from backup
        assert json_file.read_text() == original_content

        # Backup should be cleaned up
        backup_file = json_file.with_suffix(".json.backup")
        assert not backup_file.exists()


class TestScanningAndBatchOperations:
    """Test directory scanning and batch processing."""

    def test_fix_paths_scans_all_state_files(self, temp_state_dir, multiple_json_files):
        """Should find all JSON files in state directory."""
        from scripts.fix_state_paths import find_state_files

        state_files = find_state_files(temp_state_dir)

        # Should find all JSON files
        assert len(state_files) >= 3
        assert any(f.name == "state1.json" for f in state_files)
        assert any(f.name == "state2.json" for f in state_files)
        assert any(f.name == "no_paths.json" for f in state_files)

    def test_fix_paths_recursive_directory_scan(self, temp_state_dir):
        """Should scan subdirectories recursively."""
        from scripts.fix_state_paths import find_state_files

        # Create files in nested directories
        (temp_state_dir / "deep" / "nested").mkdir(parents=True)
        (temp_state_dir / "deep" / "nested" / "deep.json").write_text("{}")

        state_files = find_state_files(temp_state_dir)

        # Should include files from nested directories
        assert any(f.parent.name == "nested" for f in state_files)

    def test_fix_paths_filters_by_pattern(self, temp_state_dir):
        """Should only process .json files."""
        from scripts.fix_state_paths import find_state_files

        # Create various file types
        (temp_state_dir / "test.json").write_text("{}")
        (temp_state_dir / "test.txt").write_text("text")
        (temp_state_dir / "test.md").write_text("# Markdown")

        state_files = find_state_files(temp_state_dir)

        # Should only include JSON files
        assert len(state_files) == 1
        assert state_files[0].name == "test.json"

    def test_fix_paths_handles_multiple_files(self, temp_state_dir, multiple_json_files):
        """Should process multiple files in batch."""
        from scripts.fix_state_paths import fix_paths_in_directory

        results = fix_paths_in_directory(temp_state_dir, backup=False)

        # Should process all files
        assert len(results) >= 3

        # Should report changes for files with Git Bash paths
        total_changes = sum(results.values())
        assert total_changes >= 2

    def test_fix_paths_reports_changes(self, temp_state_dir, sample_json_file):
        """Should report number of paths normalized per file."""
        from scripts.fix_state_paths import fix_paths_in_file

        changes = fix_paths_in_file(sample_json_file)

        # Should return count of normalized paths
        assert isinstance(changes, int)
        assert changes > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_fix_paths_no_paths_found(self, temp_state_dir, no_paths_file):
        """Should report no changes when no Git Bash paths found."""
        from scripts.fix_state_paths import fix_paths_in_file

        changes = fix_paths_in_file(no_paths_file)

        # Should report zero changes
        assert changes == 0

    def test_fix_paths_mixed_path_formats(self, temp_state_dir, sample_mixed_paths_file):
        """Should handle files with Git Bash + Windows + relative paths."""
        from scripts.fix_state_paths import fix_paths_in_file

        original_data = json.loads(sample_mixed_paths_file.read_text())

        fix_paths_in_file(sample_mixed_paths_file)

        modified_data = json.loads(sample_mixed_paths_file.read_text())

        # Should normalize Git Bash paths
        assert modified_data["git_bash"] == "P:\\\\\\\\\.claude\\\\skills\\\\code"

        # Should preserve Windows paths
        assert modified_data["windows"] == original_data["windows"]

        # Should preserve relative paths
        assert modified_data["relative"] == original_data["relative"]

        # Should normalize other Git Bash paths
        assert modified_data["another_drive"] == "C:\\\\Users\\\\test"
        assert modified_data["nested"]["git_path"] == "P:\\\\\\\\\.claude\\\\config.json"

    def test_fix_paths_special_characters(self, temp_state_dir):
        """Should handle paths with spaces, dashes, dots, etc."""
        from scripts.fix_state_paths import fix_paths_in_file

        json_file = temp_state_dir / "special.json"

        data = {
            "spaces": "/p/Program Files/My Project",
            "dashes": "/p/my-project-folder/file.py",
            "dots": "/p/.claude/skills/code",
            "underscores": "/p/my_folder/file.py"
        }

        json_file.write_text(json.dumps(data, indent=2))
        changes = fix_paths_in_file(json_file)

        modified_data = json.loads(json_file.read_text())

        # Should normalize all paths
        assert changes == 4
        assert "Program Files" in modified_data["spaces"]
        assert "my-project-folder" in modified_data["dashes"]


class TestIntegrationTests:
    """Integration tests for complete workflow."""

    def test_fix_paths_integration(self, temp_state_dir):
        """End-to-end test: scan, detect, normalize, backup."""
        # Create test files
        (temp_state_dir / "file1.json").write_text(
            json.dumps({"path": "/p/.claude/test1"}, indent=2)
        )
        (temp_state_dir / "file2.json").write_text(
            json.dumps({"path": "/p/.claude/test2"}, indent=2)
        )

        from scripts.fix_state_paths import fix_paths_main

        # Run main function
        results = fix_paths_main(
            state_dir=temp_state_dir,
            backup=True,
            dry_run=False
        )

        # Should process files
        assert len(results) >= 2

        # Should have created backups
        assert (temp_state_dir / "file1.json.backup").exists()
        assert (temp_state_dir / "file2.json.backup").exists()

        # Should have normalized paths
        file1_data = json.loads((temp_state_dir / "file1.json").read_text())
        assert "P:\\\\\\\\\" in file1_data["path"]

    def test_fix_paths_cli_invocation(self, temp_state_dir):
        """Should be invocable from CLI with correct arguments."""
        import subprocess

        # Create test file
        (temp_state_dir / "test.json").write_text(
            json.dumps({"path": "/p/.claude/test"}, indent=2)
        )

        # Run script via CLI
        result = subprocess.run(
            [sys.executable, "-m", "scripts.fix_state_paths",
             "--state-dir", str(temp_state_dir),
             "--no-backup"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # Should execute successfully
        assert result.returncode == 0

    def test_fix_paths_dry_run_mode(self, temp_state_dir):
        """--dry-run should report changes without executing."""
        # Create test file
        test_file = temp_state_dir / "test.json"
        test_file.write_text(
            json.dumps({"path": "/p/.claude/test"}, indent=2)
        )

        original_content = test_file.read_text()

        from scripts.fix_state_paths import fix_paths_main

        # Run with dry_run=True
        results = fix_paths_main(
            state_dir=temp_state_dir,
            backup=False,
            dry_run=True
        )

        # Should report what would change
        assert len(results) > 0

        # File should be unchanged
        assert test_file.read_text() == original_content

        # No backup should be created
        assert not (temp_state_dir / "test.json.backup").exists()

    def test_fix_paths_preserves_json_structure(self, temp_state_dir, sample_json_file):
        """Should preserve JSON structure, comments, and formatting (if applicable)."""
        from scripts.fix_state_paths import fix_paths_in_file

        fix_paths_in_file(sample_json_file)

        # Should be valid JSON with same structure
        modified_data = json.loads(sample_json_file.read_text())

        # Check structure preserved
        assert "project_root" in modified_data
        assert "script_path" in modified_data
        assert "relative_path" in modified_data
        assert "nested" in modified_data
        assert isinstance(modified_data["nested"]["array"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
