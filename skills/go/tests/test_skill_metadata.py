from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"


def _frontmatter() -> dict[str, str]:
    text = SKILL_MD.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith("  "):
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def test_description_is_trigger_oriented_not_workflow_summary():
    description = _frontmatter()["description"]

    assert description.startswith("Use when ")
    assert "Defaults to" not in description
    assert "drive it to PR-ready" not in description
