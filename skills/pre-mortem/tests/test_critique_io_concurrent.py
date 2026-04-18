"""Concurrent write test for premortem_io — verifies sessions.json integrity under parallel _save_registry calls."""

import json
import multiprocessing
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))


def _worker_save_registry(args: tuple[str, str, str]) -> None:
    """Worker: write a registry entry and return. Runs in separate process.

    Each worker overrides _get_terminal_id via sys.modules so its synthetic ID
    is used instead of the parent process's real terminal_id from skill_guard.
    """
    terminal_id, session_dir, staging_root_str = args
    staging_root = Path(staging_root_str)

    # Patch the module-level _get_terminal_id before the module is imported
    # by replacing it in sys.modules. This avoids the module-object patch issue
    # with spawn-context multiprocessing.
    import premortem_io as ci_module

    original_get_terminal_id = ci_module._get_terminal_id

    def _fake_terminal_id() -> str:
        return terminal_id

    try:
        ci_module._get_terminal_id = _fake_terminal_id
        from premortem_io import PreMortemSession

        session = PreMortemSession(staging_root=staging_root)
        session.session_dir = Path(session_dir)
        session.timestamp = terminal_id.split("_")[1] if "_" in terminal_id else terminal_id
        session._save_registry(staging_root)
    finally:
        ci_module._get_terminal_id = original_get_terminal_id


def test_concurrent_save_registry_integrity(tmp_path: Path) -> None:
    """RISK-001: Two processes writing sessions.json concurrently must not corrupt it.

    Before the _atomic_write_json fix, concurrent write interleaving could leave
    sessions.json truncated or as invalid JSON. After the fix (os.fsync before rename),
    the file should always be valid JSON with both entries intact.
    """
    staging_root = tmp_path / "critique_staging"
    staging_root.mkdir()

    # Create two terminal IDs that simulate concurrent terminals
    terminal_a = f"concurrent_terminal_A_{time.time_ns()}"
    terminal_b = f"concurrent_terminal_B_{time.time_ns()}"
    session_a = staging_root / f"critique-A-{time.time_ns()}"
    session_b = staging_root / f"critique-B-{time.time_ns()}"
    session_a.mkdir()
    session_b.mkdir()

    # Launch two processes that write to sessions.json at the same time
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(2) as pool:
        pool.map(
            _worker_save_registry,
            [
                (terminal_a, str(session_a), str(staging_root)),
                (terminal_b, str(session_b), str(staging_root)),
            ],
        )

    # Registry must be valid JSON — no truncation, no corruption
    sessions_file = staging_root / "sessions.json"
    assert sessions_file.exists(), "sessions.json was not created"

    with open(sessions_file, encoding="utf-8") as f:
        content = f.read()

    try:
        registry = json.loads(content)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"sessions.json is not valid JSON after concurrent writes — "
            f"atomic write fix may not be working: {e}"
        ) from e

    # Both terminal entries must be present
    assert terminal_a in registry, f"Terminal A entry missing from registry: {registry}"
    assert terminal_b in registry, f"Terminal B entry missing from registry: {registry}"

    # Each entry must have required fields
    assert "session_dir" in registry[terminal_a]
    assert "timestamp" in registry[terminal_a]
    assert "last_used" in registry[terminal_a], "last_used field missing — RISK-005 fix not applied"
    assert "session_dir" in registry[terminal_b]
    assert "timestamp" in registry[terminal_b]
    assert "last_used" in registry[terminal_b], "last_used field missing — RISK-005 fix not applied"


def test_atomic_write_json_produces_valid_json(tmp_path: Path) -> None:
    """Unit test: _atomic_write_json must always produce valid JSON."""
    from premortem_io import PreMortemSession

    path = tmp_path / "test_atomic.json"
    data = {"key": "value", "nested": {"a": 1, "b": 2}}

    PreMortemSession._atomic_write_json(path, data)

    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_atomic_write_json_overwrites(tmp_path: Path) -> None:
    """Unit test: _atomic_write_json must atomically overwrite existing file."""
    from premortem_io import PreMortemSession

    path = tmp_path / "test_overwrite.json"

    PreMortemSession._atomic_write_json(path, {"v": 1})
    PreMortemSession._atomic_write_json(path, {"v": 2})

    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == {"v": 2}
