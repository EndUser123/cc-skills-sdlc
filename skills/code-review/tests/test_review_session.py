"""Tests for ReviewSession."""

import shutil

# Import the module under test
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "__lib"))
from review_session import ReviewSession


@pytest.fixture
def temp_base_dir():
    """Create a temporary base directory for tests."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_review_session_initialization(temp_base_dir):
    """Test ReviewSession initializes with correct paths."""
    session = ReviewSession(base_dir=str(temp_base_dir))

    assert session.base_dir == temp_base_dir
    assert len(session.session_id) == 8
    assert session.session_dir == temp_base_dir / session.session_id
    assert session.work_file == session.session_dir / "work.md"


def test_setup_creates_session_dir(temp_base_dir):
    """Test setup() creates the session directory."""
    session = ReviewSession(base_dir=str(temp_base_dir))
    session.setup("")

    assert session.session_dir.exists()
    assert session.work_file.exists()


def test_setup_with_target_空文件(temp_base_dir):
    """Test setup() with a target path."""
    session = ReviewSession(base_dir=str(temp_base_dir))

    # Use a temp file as target
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"# test")
        target = f.name

    try:
        session.setup(target)
        content = session.work_file.read_text()

        assert "Target:" in content
        assert target in content
        assert "Files (1)" in content
    finally:
        Path(target).unlink()


def test_get_session_dir_returns_string(temp_base_dir):
    """Test get_session_dir returns a valid string path."""
    session = ReviewSession(base_dir=str(temp_base_dir))
    session.setup("")

    result = session.get_session_dir()

    assert isinstance(result, str)
    assert session.session_id in result


def test_write_findings(temp_base_dir):
    """Test write_findings() creates findings file."""
    session = ReviewSession(base_dir=str(temp_base_dir))
    session.setup("")

    findings_content = "# Phase 1 Findings\n\n- Test finding"
    session.write_findings(findings_content)

    assert session.findings_file.exists()
    assert session.findings_file.read_text() == findings_content


def test_write_review(temp_base_dir):
    """Test write_review() creates review file."""
    session = ReviewSession(base_dir=str(temp_base_dir))
    session.setup("")

    review_content = "# Code Review Report\n\n## Summary\n\nTest review"
    session.write_review(review_content)

    assert session.review_file.exists()
    assert session.review_file.read_text() == review_content
