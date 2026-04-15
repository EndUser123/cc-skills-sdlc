"""Tests for hook authority and registered hook root handling in rca."""

import json
from pathlib import Path


def _iter_string_values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_string_values(item)
    elif isinstance(value, str):
        yield value


def test_settings_json_uses_project_scoped_hook_paths():
    """Registered hook commands should point at the project-scoped hook tree."""
    settings_path = Path("P:/.claude/settings.json")
    assert settings_path.exists(), f"settings.json not found at {settings_path}"

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    all_strings = "\n".join(_iter_string_values(settings))

    assert "P:/.claude/hooks" in all_strings, "Expected project-scoped hook paths in settings.json"
    assert "~/.claude/hooks" not in all_strings, "settings.json should not point hooks at the home-directory path"


def test_rca_docs_state_hook_authority_explicitly():
    """RCA docs should tell investigators which hook path is authoritative."""
    skill_md = Path("P:/.claude/skills/rca/SKILL.md").read_text(encoding="utf-8")
    specialization_md = Path("P:/.claude/skills/rca/HOOKS_SKILLS_SPECIALIZATION.md").read_text(
        encoding="utf-8"
    )
    protocol_md = Path(
        "P:/.claude/skills/rca/references/investigation-protocol.md"
    ).read_text(encoding="utf-8")
    output_format_md = Path("P:/.claude/skills/rca/references/output-format.md").read_text(
        encoding="utf-8"
    )

    for text in (skill_md, specialization_md, protocol_md, output_format_md):
        assert "P:/.claude/settings.json" in text, "RCA docs should name settings.json as the hook authority"
        assert "P:/.claude/hooks" in text, "RCA docs should reference the actual hook implementation tree"

    assert "Do not use `~/.claude/hooks`" in skill_md
    assert "Do not infer hook absence from `~/.claude/hooks`" in specialization_md
    assert "### Hook Authority" in output_format_md
    assert "Registered hook authority" in output_format_md
