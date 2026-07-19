"""Tests for wiki_after_write.py — pure-logic checks (parser, sanitizer, injector, slug filter).

QMD itself is not exercised here; query_qmd() is treated as a boundary and
monkeypatched. The script's own dry-run against a real vault page covers the
QMD boundary live.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import wiki_after_write as waw


# ---------- frontmatter parsing ----------

class TestReadFrontmatter:
    def test_inline_summary(self):
        fm = "---\ntitle: Foo Bar\nsummary: A short summary\n---\nbody"
        out = waw.read_frontmatter(fm)
        assert out.get("title") == "Foo Bar"
        assert out.get("summary") == "A short summary"

    def test_block_summary_gt(self):
        fm = "---\ntitle: Foo\nsummary: >\n  Line one.\n  Line two.\n---\nbody"
        out = waw.read_frontmatter(fm)
        assert out.get("title") == "Foo"
        assert out.get("summary") == "Line one. Line two."

    def test_quoted_title(self):
        fm = '---\ntitle: "Quoted Title"\nsummary: x\n---\n'
        assert waw.read_frontmatter(fm).get("title") == "Quoted Title"

    def test_no_frontmatter(self):
        assert waw.read_frontmatter("no fm here") == {}

    def test_no_closing_fence(self):
        assert waw.read_frontmatter("---\ntitle: x\n") == {}

    def test_block_summary_does_not_leak_gt_into_inline(self):
        # regression: inline regex used to backtrack and capture the '>' indicator
        fm = "---\ntitle: Real\nsummary: >\n  The actual summary.\n---\n"
        out = waw.read_frontmatter(fm)
        assert out.get("summary") == "The actual summary."
        assert ">" not in out.get("summary", "")


# ---------- query sanitization ----------

class TestBuildQuery:
    def test_preserves_punctuation(self):
        # Contract: build_query does NOT strip punctuation. FTS5 operator
        # escaping is handled at the root by the forked qmd.build_fts5_query
        # (see cc-skills-utils/__lib/qmd_fts5_patch.patch). Caller-side
        # sanitization was removed when the patch landed; this test pins the
        # current contract so a revert would be caught.
        q = waw.build_query({
            "title": "Subagent `model:` field (haiku/sonnet/opus)",
            "summary": "TWO levers — not one. /ai-api, /ai-cli work.",
        })
        # Punctuation preserved (FTS5 patch handles escaping downstream)
        assert "`" in q
        assert "/" in q
        assert "(" in q
        assert "—" in q
        # Keywords still present
        assert "model" in q and "haiku" in q and "sonnet" in q

    def test_truncates_to_max(self):
        q = waw.build_query({"title": "x" * (waw.MAX_QUERY_CHARS + 50)})
        assert len(q) <= waw.MAX_QUERY_CHARS

    def test_empty_meta(self):
        assert waw.build_query({}) == ""

    def test_preserves_unicode_letters(self):
        # Regression: ASCII-only sanitizer used to strip CJK/Cyrillic/accented letters.
        q = waw.build_query({"title": "方法论 café résumé", "summary": ""})
        assert "方法" in q
        assert "café" in q
        assert "résumé" in q


# ---------- slug-from-file filter ----------

class TestSlugFromFile:
    def test_concept_path(self):
        assert waw.slug_from_file("wiki/concepts/foo-bar.md") == "foo-bar"

    def test_rejects_sources(self):
        assert waw.slug_from_file("wiki/sources/other/x.md") is None

    def test_rejects_log(self):
        assert waw.slug_from_file("wiki/log.md") is None

    def test_rejects_empty(self):
        assert waw.slug_from_file("") is None

    def test_windows_backslash_path(self):
        assert waw.slug_from_file("wiki\\concepts\\foo.md") == "foo"


# ---------- section injection ----------

class TestInjectSection:
    def test_appends_when_absent(self):
        text = "---\ntitle: x\n---\n\nBody.\n"
        out = waw.inject_section(text, ["alpha", "beta"])
        assert "## Auto-related" in out
        assert "[[alpha]]" in out and "[[beta]]" in out
        assert out.rstrip().endswith("[[beta]]")

    def test_replaces_existing_auto_section(self):
        text = "---\ntitle: x\n---\n\n## Auto-related\n\n- [[old]]\n\n## Other\n\nstuff\n"
        out = waw.inject_section(text, ["new1", "new2"])
        assert "[[old]]" not in out
        assert "[[new1]]" in out and "[[new2]]" in out
        assert "## Other" in out

    def test_preserves_hand_authored_related(self):
        text = "---\ntitle: x\n---\n\n## Related\n\n- [[hand]]\n\nBody.\n"
        out = waw.inject_section(text, ["auto"])
        # hand-authored section untouched; auto section added separately
        assert "## Related" in out and "[[hand]]" in out
        assert "## Auto-related" in out and "[[auto]]" in out


# ---------- end-to-end with qmd monkeypatched ----------

class TestAfterWrite:
    def test_self_excluded(self, tmp_path):
        page = tmp_path / "my-page.md"
        page.write_text(
            "---\ntitle: My Page\nsummary: about subagents\n---\n\nbody\n",
            encoding="utf-8",
        )
        def fake_qmd(query, limit, qmd_bin):
            return [
                {"file": "wiki/concepts/my-page.md", "score": 0.9},
                {"file": "wiki/concepts/real-neighbor.md", "score": 0.05},
                {"file": "wiki/log.md", "score": 0.04},  # filtered (non-concept)
            ]
        orig = waw.query_qmd
        waw.query_qmd = fake_qmd
        try:
            report = waw.after_write(page, limit=5, qmd_bin="qmd", dry_run=True)
        finally:
            waw.query_qmd = orig
        assert report["ok"]
        assert report["links"] == ["real-neighbor"]
        assert not report.get("wrote")  # dry-run

    def test_no_links_no_write(self, tmp_path):
        page = tmp_path / "empty.md"
        page.write_text("---\ntitle: Empty\nsummary: nothing matches\n---\nbody\n",
                        encoding="utf-8")
        orig = waw.query_qmd
        waw.query_qmd = lambda *a, **k: []
        try:
            report = waw.after_write(page, 5, "qmd", dry_run=False)
        finally:
            waw.query_qmd = orig
        assert report["ok"]
        assert report["links"] == []
        assert not report.get("wrote")
        # page unchanged — no auto section written
        assert "## Auto-related" not in page.read_text(encoding="utf-8")
