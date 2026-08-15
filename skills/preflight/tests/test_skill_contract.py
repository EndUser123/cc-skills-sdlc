from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CLAUDE = Path(r"P:\.claude\CLAUDE.md")


def test_claude_skill_requires_shared_preflight_audit() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "preflight" in skill
    assert r"P:\.agents\skills\preflight\scripts\discovery_audit.py" in skill
    assert "active plan" in skill.lower()
    assert "needs_review" in skill
    assert "do not implement" in skill.lower()


def test_workspace_constitution_requires_the_preflight_skill() -> None:
    constitution = WORKSPACE_CLAUDE.read_text(encoding="utf-8")

    assert "Mandatory Preflight" in constitution
    assert "preflight" in constitution
    assert "needs_review" in constitution
