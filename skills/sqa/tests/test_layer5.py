"""Tests for Layer 5 SECURITY analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer5_security


class TestIsValidatedOpen:
    """Tests for _is_validated_line heuristic."""

    def test_assert_guard(self):
        assert layer5_security._is_validated_line("assert path == realpath(path)") is True

    def test_realpath_validation(self):
        assert layer5_security._is_validated_line("f = open(realpath(user_input))") is True

    def test_is_relative_to_validation(self):
        assert layer5_security._is_validated_line("if p.is_relative_to(base): open(p)") is True

    def test_safepath_validation(self):
        assert layer5_security._is_validated_line("open(safepath(path))") is True

    def test_validate_function(self):
        assert (
            layer5_security._is_validated_line("validated = validate(path); open(validated)")
            is True
        )

    def test_plain_open_is_not_validated(self):
        assert layer5_security._is_validated_line("f = open(user_path)") is False

    def test_string_literal_is_not_validated(self):
        # Literal string path is somewhat safe
        assert layer5_security._is_validated_line("f = open('/tmp/file.txt')") is False


class TestCheckCommand:
    """Tests for _check_command ALLOWED_COMMANDS validation."""

    def test_ruff_allowed(self):
        layer5_security._check_command("ruff")

    def test_mypy_allowed(self):
        layer5_security._check_command("mypy")

    def test_verify_allowed(self):
        layer5_security._check_command("verify --tier=1")

    def test_hook_audit_allowed(self):
        layer5_security._check_command("hook-audit")

    def test_arbitrary_command_rejected(self):
        with pytest.raises(AssertionError):
            layer5_security._check_command("rm -rf /")


class TestLayer5Run:
    """Tests for layer5_security.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer5_security.run(tmp_target)
        assert isinstance(result, list)
