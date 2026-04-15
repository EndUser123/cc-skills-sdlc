"""Tests for graceful degradation behavior in the SQA orchestrator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


class TestAllowedCommands:
    """Tests for ALLOWED_COMMANDS allowlist enforcement."""

    def test_orchestrator_has_allowed_commands_list(self):
        from orchestrator import ALLOWED_COMMANDS

        assert "ruff" in ALLOWED_COMMANDS
        assert "mypy" in ALLOWED_COMMANDS
        assert "pytest" in ALLOWED_COMMANDS
        assert "aid" in ALLOWED_COMMANDS
        assert "gto" in ALLOWED_COMMANDS
        assert "verify" in ALLOWED_COMMANDS
        assert "hook-audit" in ALLOWED_COMMANDS
        assert "hook-inventory" in ALLOWED_COMMANDS
        assert "adversarial-security" in ALLOWED_COMMANDS
        assert "adversarial-performance" in ALLOWED_COMMANDS
        assert "diagnose" in ALLOWED_COMMANDS

    def test_allowed_commands_blocks_shell_injection(self):
        """Ensure arbitrary commands cannot be injected via the allowlist."""
        from orchestrator import ALLOWED_COMMANDS

        assert "rm" not in ALLOWED_COMMANDS
        assert "curl" not in ALLOWED_COMMANDS
        assert "wget" not in ALLOWED_COMMANDS
        assert "python" not in ALLOWED_COMMANDS


class TestTargetValidation:
    """Tests for target path validation."""

    def test_validate_rejects_nonexistent_path(self):
        from orchestrator import _validate_target

        with pytest.raises(AssertionError):
            _validate_target("/nonexistent/path/xyz")

    def test_validate_rejects_symlink(self, tmp_path):
        import os

        from orchestrator import _validate_target

        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link_dir = tmp_path / "link"
        try:
            os.symlink(str(real_dir), str(link_dir))
            with pytest.raises(AssertionError):
                _validate_target(str(link_dir))
        except (OSError, NotImplementedError):
            # Symlinks may not be supported on Windows in some configs
            pass
