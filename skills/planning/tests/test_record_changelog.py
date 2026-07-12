from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_changelog.py"
spec = spec_from_file_location("record_changelog_under_test", SCRIPT)
assert spec is not None and spec.loader is not None
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_append_entry_is_dated_and_idempotence_guarded(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    when = datetime(2026, 7, 11, 18, 42, tzinfo=UTC)

    entry_id = module.append_entry(
        changelog,
        summary="Record a design validation",
        sources="/wiki, /check",
        claims="shared registry contract",
        evidence="plan.md and check output",
        timestamp=when,
    )
    text = changelog.read_text(encoding="utf-8")
    assert entry_id == "PROV-20260711T184200Z-design"
    assert "2026-07-11T18:42:00Z" in text
    assert entry_id in text

    try:
        module.append_entry(
            changelog,
            summary="duplicate",
            sources="/wiki",
            claims="claim",
            evidence="evidence",
            entry_id=entry_id,
            timestamp=when,
        )
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate entry must be rejected")
