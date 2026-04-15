"""Pytest configuration for sqa-orchestrator tests."""

import sys
from pathlib import Path

import pytest

# Add skill root to path so 'from findings.models import ...' and 'from layers import ...' work
SKILL_ROOT = str(Path(__file__).parent.parent.resolve())
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)


@pytest.fixture
def skill_root():
    """Return the skill root directory."""
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def tmp_target(tmp_path):
    """Create a minimal Python project target for testing."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text('"""Main module."""\nprint("hello")\n')
    return tmp_path


@pytest.fixture
def validated_target(tmp_target, monkeypatch):
    """Patch _validate_target so tmp_target bypasses ALLOWED_ROOTS check.

    Integration tests call run_sqa(tmp_target) which internally validates
    that the target is under Path.cwd(). Since pytest's tmp_path is in the
    Windows temp dir (outside cwd), we mock _validate_target to return
    the resolved path directly.
    """

    def mock_validate(target):
        return Path(target).resolve()

    monkeypatch.setattr("orchestrator._validate_target", mock_validate)
    return tmp_target
