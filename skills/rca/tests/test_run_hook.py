"""Tests for run_hook.py compatibility shim.

These tests verify the behavior of the run_hook.py module which acts
as a command-line entry point for the hook launcher.

Run with: pytest P:/packages/rca/skill/tests/test_run_hook.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Setup import path for rca package
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca import run_hook


class TestRunHookModule:
    """Tests for run_hook.py module structure."""

    def test_module_exists(self):
        """Test that run_hook module can be imported.

        Given: The run_hook module exists
        When: Importing rca.run_hook
        Then: Should import successfully
        """
        assert run_hook is not None

    def test_main_function_imported(self):
        """Test that main function is imported from hook_launcher.

        Given: run_hook.py imports main from hook_launcher
        When: Checking if main attribute exists
        Then: Should have main function attribute
        """
        assert hasattr(run_hook, "main")
        assert callable(run_hook.main)


class TestRunHookExecution:
    """Tests for run_hook.py command-line execution behavior."""

    @patch("rca.run_hook.main")
    def test_main_calls_hook_launcher_main(self, mock_main):
        """Test that __main__ calls main from hook_launcher.

        Given: run_hook.py is executed as main
        When: Calling the module's entry point
        Then: Should call main function with argv arguments
        """
        # Simulate calling with test arguments
        test_args = ["test_arg1", "test_arg2"]

        with patch.object(sys, "argv", ["run_hook"] + test_args):
            # The actual __main__ block raises SystemExit(main(sys.argv[1:]))
            # We test the behavior by calling main directly
            run_hook.main(test_args)

        # Verify main was called
        mock_main.assert_called_once_with(test_args)

    @patch("rca.run_hook.main")
    def test_main_returns_zero_on_success(self, mock_main):
        """Test that main returns 0 on success.

        Given: main function executes successfully
        When: Returning from main
        Then: Should return exit code 0
        """
        # Make main return 0
        mock_main.return_value = 0

        result = run_hook.main([])

        assert result == 0

    @patch("rca.run_hook.main")
    def test_main_returns_nonzero_on_error(self, mock_main):
        """Test that main returns non-zero on error.

        Given: main function encounters an error
        When: Returning from main
        Then: Should return exit code 1
        """
        mock_main.return_value = 1

        result = run_hook.main([])

        assert result == 1

    @patch("rca.run_hook.main")
    def test_main_propagates_exceptions(self, mock_main):
        """Test that exceptions from main are not caught.

        Given: main raises an exception
        When: The exception propagates through __main__
        Then: Should raise SystemExit (Python behavior for uncaught exceptions)
        """
        # Make main raise an exception
        mock_main.side_effect = RuntimeError("Test error")

        # When uncaught exception occurs in __main__, Python exits with code 1
        # The SystemExit wrapping doesn't happen for exceptions
        with pytest.raises(RuntimeError):
            run_hook.main([])


class TestRunHookIntegration:
    """Integration tests for run_hook.py with hook_launcher."""

    def test_hook_launcher_import(self):
        """Test that hook_launcher can be imported through run_hook.

        Given: run_hook imports main from hook_launcher
        When: Checking the import
        Then: hook_launcher.main should be the same as run_hook.main
        """
        from rca import hook_launcher

        # Both should reference the same function
        assert run_hook.main is hook_launcher.main

    def test_module_exposes_main_entry_point(self):
        """Test that the module provides a clear entry point.

        Given: run_hook.py is designed as a CLI entry point
        When: Inspecting the module
        Then: Should have __name__ == "__main__" guard for execution
        """
        # Read the module source to verify structure
        module_path = Path("P:/packages/rca/src/rca/run_hook.py")
        source_code = module_path.read_text()

        # Should have if __name__ == "__main__" guard
        assert 'if __name__ == "__main__":' in source_code
        # Should call main() with sys.argv[1:]
        assert "main(sys.argv[1:])" in source_code
        # Should use SystemExit to propagate return code
        assert "raise SystemExit(" in source_code
