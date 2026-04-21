"""
Tests for persistence module - CKS write-back functions.

Covers:
- _find_cks_db: path discovery, found/not-found paths
- _ingest_into_cks: success, DB-missing, sqlite3 exception (silent-failure contract)
- save_arch_decision: verifies _ingest_into_cks is called after successful save

Run with: pytest packages/arch/skill/tests/test_persistence.py -v
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# Add parent directories for package imports
test_dir = Path(__file__).parent
skills_dir = test_dir.parent.parent
sys.path.insert(0, str(skills_dir))

from arch.persistence import (  # noqa: E402
    _find_cks_db,
    _ingest_into_cks,
    save_arch_decision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CKS_SCHEMA = """
    CREATE TABLE entries (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT,
        content TEXT NOT NULL,
        metadata TEXT,
        embedding BLOB,
        source_chunk TEXT,
        usage_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        thumbs_up INTEGER DEFAULT 0,
        thumbs_down INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def _make_cks_db(path: Path) -> None:
    """Create a minimal CKS database at path with the production schema."""
    conn = sqlite3.connect(str(path))
    conn.execute(_CKS_SCHEMA)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# _find_cks_db
# ---------------------------------------------------------------------------


class TestFindCksDb:
    def test_returns_path_when_db_exists(self, tmp_path):
        """Should find cks.db when __csf/data/cks.db exists in a parent dir."""
        db_dir = tmp_path / "__csf" / "data"
        db_dir.mkdir(parents=True)
        db_file = db_dir / "cks.db"
        db_file.write_bytes(b"")

        fake_module = tmp_path / "packages" / "arch" / "skill" / "persistence.py"
        fake_module.parent.mkdir(parents=True, exist_ok=True)

        with patch("arch.persistence.__file__", str(fake_module)):
            result = _find_cks_db()

        assert result == db_file

    def test_returns_none_when_db_missing(self, tmp_path):
        """Should return None if cks.db is not found within 6 parent levels."""
        fake_module = tmp_path / "a" / "b" / "c" / "persistence.py"
        fake_module.parent.mkdir(parents=True, exist_ok=True)

        with patch("arch.persistence.__file__", str(fake_module)):
            result = _find_cks_db()

        assert result is None

    def test_returns_path_type(self, tmp_path):
        """Return type must be Path (not str) when database is found."""
        db_dir = tmp_path / "__csf" / "data"
        db_dir.mkdir(parents=True)
        (db_dir / "cks.db").write_bytes(b"")

        fake_module = tmp_path / "packages" / "arch" / "skill" / "persistence.py"
        fake_module.parent.mkdir(parents=True, exist_ok=True)

        with patch("arch.persistence.__file__", str(fake_module)):
            result = _find_cks_db()

        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# _ingest_into_cks
# ---------------------------------------------------------------------------


class TestIngestIntoCks:
    def test_inserts_row_into_cks_db(self, tmp_path):
        """Row with correct fields must appear in entries table after ingest."""
        db_path = tmp_path / "cks.db"
        _make_cks_db(db_path)

        with patch("arch.persistence._find_cks_db", return_value=db_path):
            _ingest_into_cks(
                query="design a REST API",
                template="deep",
                domain="python",
                output="# Decision\nUse FastAPI..." * 20,
                filename="2026-03-16_deep_design-a-rest-api.md",
            )

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT type, title, content, metadata FROM entries").fetchall()
        conn.close()

        assert len(rows) == 1
        row_type, row_title, row_content, row_metadata = rows[0]
        assert row_type == "arch_decision"
        assert row_title == "deep: design a REST API"
        assert "FastAPI" in row_content
        meta = json.loads(row_metadata)
        assert meta["source"] == "arch_decision"
        assert meta["template"] == "deep"
        assert meta["domain"] == "python"
        assert meta["filename"] == "2026-03-16_deep_design-a-rest-api.md"

    def test_content_truncated_to_2000_chars(self, tmp_path):
        """Output exceeding 2000 chars must be stored truncated to exactly 2000."""
        db_path = tmp_path / "cks.db"
        _make_cks_db(db_path)

        with patch("arch.persistence._find_cks_db", return_value=db_path):
            _ingest_into_cks(
                query="q",
                template="fast",
                domain="generic",
                output="x" * 5000,
                filename="f.md",
            )

        conn = sqlite3.connect(str(db_path))
        content = conn.execute("SELECT content FROM entries").fetchone()[0]
        conn.close()
        assert len(content) == 2000

    def test_title_truncates_query_at_80_chars(self, tmp_path):
        """Query portion of title must be capped at 80 characters."""
        db_path = tmp_path / "cks.db"
        _make_cks_db(db_path)

        with patch("arch.persistence._find_cks_db", return_value=db_path):
            _ingest_into_cks(
                query="q" * 200,
                template="deep",
                domain="generic",
                output="some output",
                filename="f.md",
            )

        conn = sqlite3.connect(str(db_path))
        title = conn.execute("SELECT title FROM entries").fetchone()[0]
        conn.close()
        assert title == "deep: " + "q" * 80

    def test_silent_failure_when_db_not_found(self):
        """Must not raise when _find_cks_db returns None (CKS unavailable)."""
        with patch("arch.persistence._find_cks_db", return_value=None):
            _ingest_into_cks(
                query="test",
                template="fast",
                domain="generic",
                output="output",
                filename="f.md",
            )  # must not raise

    def test_silent_failure_on_corrupt_db(self, tmp_path):
        """Must not raise even when sqlite3.connect receives a corrupt file."""
        db_path = tmp_path / "cks.db"
        db_path.write_bytes(b"not a sqlite database")

        with patch("arch.persistence._find_cks_db", return_value=db_path):
            _ingest_into_cks(
                query="test",
                template="fast",
                domain="generic",
                output="output",
                filename="f.md",
            )  # must not raise

    def test_silent_failure_on_arbitrary_exception(self):
        """Any exception raised inside the function must be swallowed."""
        with patch("arch.persistence._find_cks_db", side_effect=RuntimeError("boom")):
            _ingest_into_cks(
                query="test",
                template="fast",
                domain="generic",
                output="output",
                filename="f.md",
            )  # must not raise

    def test_insert_or_ignore_on_duplicate_id(self, tmp_path):
        """Duplicate UUID (INSERT OR IGNORE) must not raise or double-insert."""
        db_path = tmp_path / "cks.db"
        _make_cks_db(db_path)

        fixed_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO entries (id, type, content) VALUES (?, ?, ?)",
            (fixed_id, "arch_decision", "existing"),
        )
        conn.commit()
        conn.close()

        mock_uuid = MagicMock()
        mock_uuid.__str__ = lambda _: fixed_id

        with (
            patch("arch.persistence._find_cks_db", return_value=db_path),
            patch("arch.persistence.uuid.uuid4", return_value=mock_uuid),
        ):
            _ingest_into_cks(
                query="test",
                template="fast",
                domain="generic",
                output="output",
                filename="f.md",
            )

        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.close()
        assert count == 1  # original row unchanged, no duplicate


# ---------------------------------------------------------------------------
# save_arch_decision - CKS call integration
# ---------------------------------------------------------------------------


class TestSaveArchDecisionCksIntegration:
    def test_ingest_called_after_successful_save(self, tmp_path):
        """_ingest_into_cks must be called once with correct kwargs on success."""
        output = "x" * 3000  # above MIN_OUTPUT_SIZE_TO_SAVE (2048)

        with patch("arch.persistence._ingest_into_cks") as mock_ingest:
            result = save_arch_decision(
                query="design a caching layer",
                template="deep",
                domain="python",
                output=output,
                confidence=80,
                decisions_dir=tmp_path,
            )

        assert result is not None
        mock_ingest.assert_called_once()
        kwargs = mock_ingest.call_args.kwargs
        assert kwargs["query"] == "design a caching layer"
        assert kwargs["template"] == "deep"
        assert kwargs["domain"] == "python"

    def test_ingest_not_called_when_save_skipped(self, tmp_path):
        """_ingest_into_cks must NOT be called when output is too short to save."""
        with patch("arch.persistence._ingest_into_cks") as mock_ingest:
            result = save_arch_decision(
                query="design a system",
                template="fast",
                domain="generic",
                output="x" * 100,  # below MIN_OUTPUT_SIZE_TO_SAVE
                confidence=70,
                decisions_dir=tmp_path,
            )

        assert result is None
        mock_ingest.assert_not_called()

    def test_save_returns_filepath_despite_cks_down(self, tmp_path):
        """save_arch_decision must return the saved filepath even if CKS is down."""
        with patch("arch.persistence._find_cks_db", return_value=None):
            result = save_arch_decision(
                query="design a caching layer",
                template="deep",
                domain="python",
                output="x" * 3000,
                confidence=80,
                decisions_dir=tmp_path,
            )

        assert result is not None
        assert Path(result).exists()
