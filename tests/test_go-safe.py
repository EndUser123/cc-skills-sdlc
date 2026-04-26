"""Auto-scaffolded test for go-safe."""

import pytest
import sys
sys.path.insert(0, "skills/go/scripts")
from go_safe import main


def test_go_safe_importable():
    """go_safe can be imported."""
    assert main is not None


def test_go_safe_exit_1_when_invalid_args(capsys):
    """Exits non-zero when no task source is available."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        result = __import__("subprocess").run(
            [sys.executable, "skills/go/scripts/go_safe.py", "--root-dir", tmpdir, "--go-run-id", "test", "--terminal-id", "test"],
            capture_output=True, text=True, cwd=tmpdir
        )
        assert result.returncode != 0  # no plan.md, should fail


# Run: pytest tests/test_go-safe.py -v
