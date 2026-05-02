"""Tests for go_safe.py."""

import subprocess
import sys
import tempfile

from skills.go.scripts.go_safe import main


def test_go_safe_importable():
    main is not None


def test_go_safe_exit_1_when_invalid_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-m", "skills.go.scripts.go_safe",
             "--root-dir", tmpdir, "--go-run-id", "test", "--terminal-id", "test"],
            capture_output=True, text=True, cwd=tmpdir,
        )
        assert result.returncode != 0
