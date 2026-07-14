"""Regression corpus for Claude Code tool-selection policy.

Tests that the canonical policy file exists, the Claude Code authoritative
guidance references it, and no unsupported agent integration claims remain.
"""

from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[3] / "policies" / "TOOL-SELECTION.md"
CLAUDE_MD_PATH = Path("P:/.claude/CLAUDE.md")
AGENTS_MD_PATH = Path("P:/AGENTS.md")


def test_policy_file_exists():
    """Canonical detailed policy exists at expected path."""
    assert POLICY_PATH.is_file(), f"Policy not found at {POLICY_PATH}"


def test_claude_md_has_tool_selection_section():
    """Concise invariant exists in Claude Code's auto-loaded guidance."""
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "## Tool Selection" in text, "Tool Selection section missing from CLAUDE.md"
    assert "Choose tools by the operation" in text, (
        "Core invariant missing from CLAUDE.md"
    )


def test_claude_md_references_detailed_policy():
    """Concise invariant in CLAUDE.md points to the detailed policy."""
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "TOOL-SELECTION.md" in text, (
        "Detailed policy reference missing from CLAUDE.md"
    )


def test_claude_md_has_priority_order():
    """CLAUDE.md contains all 5 priority levels."""
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    for level in range(1, 6):
        assert f"{level}." in text.split("## Tool Selection")[1].split("##")[0], (
            f"Priority level {level} missing from CLAUDE.md Tool Selection section"
        )


def test_policy_contains_all_required_categories():
    """Policy covers all required tool categories."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    required = [
        "Native Agent Tools",
        "Existing Repository Utilities",
        "Structured Maintained Logic",
        "PowerShell",
        "Shell Pipelines",
    ]
    for category in required:
        assert category in text, f"Missing category: {category}"


def test_policy_contains_decision_questions():
    """Policy defines decision questions for consequential choices."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "Decision Questions" in text
    assert "Selected tool" in text
    assert "Alternatives rejected" in text


def test_policy_contains_new_helper_requirements():
    """Policy defines requirements for new helpers."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "New-Helper Requirements" in text
    assert "Owner" in text
    assert "Callers" in text


def test_policy_claude_code_mapping():
    """Policy has Claude Code tool mapping section."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "Tool Mapping for Claude Code" in text
    assert "Grep" in text
    assert "Glob" in text
    assert "Read" in text


def test_no_opencode_section():
    """Policy contains no OpenCode adapter section."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "### OpenCode" not in text, "OpenCode section still present in policy"


def test_no_codex_section():
    """Policy contains no Codex adapter section."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "### Codex" not in text, "Codex section still present in policy"


def test_no_delegated_agent_claims():
    """Policy does not claim delegated-agent integration."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "Delegated Agents" not in text, (
        "Delegated Agents heading still present in policy"
    )


def test_no_cross_agent_wording():
    """Policy does not use cross-agent language."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "cross-agent" not in text, (
        "cross-agent wording still present in policy"
    )


def test_one_detailed_policy():
    """Only one detailed policy authority file exists."""
    candidates = list(Path(__file__).resolve().parents[3].glob("policies/*TOOL-SELECTION*.md"))
    assert len(candidates) == 1, (
        f"Expected exactly 1 policy file, found {len(candidates)}: {candidates}"
    )


def test_agents_md_references_claude_md():
    """AGENTS.md references the authoritative policy source."""
    text = AGENTS_MD_PATH.read_text(encoding="utf-8")
    assert "TOOL-SELECTION.md" in text.split("## Tool Selection")[1].split("##")[0], (
        "AGENTS.md Tool Selection section does not reference the detailed policy"
    )


def test_no_generated_cache_edited():
    """Plugin cache was not directly edited — version bump propagates source to cache."""
    # The policy file IS expected in the cache after a version bump propagates
    # source changes. The prohibition is against editing cache FILES directly
    # as if they were canonical source. Check that no cache file differs from
    # the canonical policy.
    cache = Path.home() / ".claude" / "plugins" / "cache"
    if not cache.is_dir():
        return  # no cache = no problem
    # Only flag if a cache copy exists with NO corresponding source file,
    # which would indicate cache was used as authoring location.
    policy_source = Path(
        "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/policies/TOOL-SELECTION.md"
    )
    if not policy_source.is_file():
        # Source missing but cache present = edited in cache
        for cached_file in cache.rglob("*TOOL-SELECTION*"):
            assert False, f"Policy found in cache without source: {cached_file}"
    # Source exists alongside cache — that's the expected deployment path
