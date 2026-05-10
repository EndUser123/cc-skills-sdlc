"""
Multi-terminal integration test for config tests.

This test verifies that config tests work correctly when multiple terminals
run tests simultaneously. This is critical because the codebase runs multiple
terminals simultaneously (per CLAUDE.md constraints).

Run with: pytest P:\\\\\\packages/arch/skill/tests/test_multi_terminal_isolation.py -v

Purpose: Verify environment variable isolation between concurrent terminals.
Issue: ARCH_* environment variables may leak between terminals causing test failures.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for importing config module
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_concurrent_terminal_execution():
    """
    Test that config tests can run simultaneously from multiple terminals.

    Given: Multiple terminals run config tests simultaneously
    When: Each terminal executes pytest
    Then: All terminals should pass without environment variable leakage

    This test spawns actual subprocess terminals to verify multi-terminal isolation.
    """
    # Get the tests directory
    tests_dir = Path(__file__).parent

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "terminal_output.txt"

        # Terminal 1: Run thread safety tests
        cmd1 = [
            sys.executable,
            "-m",
            "pytest",
            str(tests_dir / "test_config_thread_safety.py"),
            "-v",
            "--tb=short",
        ]

        # Terminal 2: Run all config tests
        cmd2 = [
            sys.executable,
            "-m",
            "pytest",
            str(tests_dir / "test_config_caching.py"),
            "-v",
            "--tb=short",
        ]

        # Set unique environment for each terminal to simulate different terminals
        env1 = os.environ.copy()
        env1["ARCH_TERMINAL_ID"] = "terminal_1"

        env2 = os.environ.copy()
        env2["ARCH_TERMINAL_ID"] = "terminal_2"

        # Start both processes
        proc1 = subprocess.Popen(
            cmd1, env=env1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        proc2 = subprocess.Popen(
            cmd2, env=env2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Wait for both to complete
        stdout1, stderr1 = proc1.communicate()
        stdout2, stderr2 = proc2.communicate()

        # Write results to output file
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("TERMINAL 1 (test_config_thread_safety.py)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Exit code: {proc1.returncode}\n")
            f.write(f"\nSTDOUT:\n{stdout1}\n")
            f.write(f"\nSTDERR:\n{stderr1}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("TERMINAL 2 (test_config_caching.py)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Exit code: {proc2.returncode}\n")
            f.write(f"\nSTDOUT:\n{stdout2}\n")
            f.write(f"\nSTDERR:\n{stderr2}\n")

        # Assert both terminals succeeded
        assert (
            proc1.returncode == 0
        ), f"Terminal 1 tests failed! Exit code: {proc1.returncode}\nSTDERR:\n{stderr1}"

        assert (
            proc2.returncode == 0
        ), f"Terminal 2 tests failed! Exit code: {proc2.returncode}\nSTDERR:\n{stderr2}"

        # Verify no ARCH_* environment variable leakage
        # Both terminals should have their own unique TERMINAL_ID
        # and should NOT have each other's values

        # Check for evidence of environment variable pollution in stderr
        assert (
            "ARCH_TERMINAL_ID" not in stderr1
        ), f"Terminal 1 detected unexpected ARCH_ environment variable in stderr:\n{stderr1}"
        assert (
            "ARCH_TERMINAL_ID" not in stderr2
        ), f"Terminal 2 detected unexpected ARCH_ environment variable in stderr:\n{stderr2}"

        print(f"\n✅ Multi-terminal test passed! Results written to: {output_file}")
