from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CLAUDE = Path(r"P:\.claude\CLAUDE.md")


def test_claude_skill_requires_shared_source_authority_audit() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "source-authority-discovery" in skill
    assert r"P:\.agents\skills\source-authority-discovery\scripts\discovery_audit.py" in skill
    assert "active plan" in skill.lower()
    assert "needs_review" in skill
    assert "do not implement" in skill.lower()


def test_workspace_constitution_requires_the_claude_discovery_skill() -> None:
    constitution = WORKSPACE_CLAUDE.read_text(encoding="utf-8")

    assert "Mandatory Source-Authority Discovery" in constitution
    assert "source-authority-discovery" in constitution
    assert "needs_review" in constitution
