"""Tests for wiki_manifest.py."""

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from wiki_manifest import build_manifest, classify_tier, make_slug, sha256_first8


class TestClassifyTier:
    def test_safe_below_200k(self):
        assert classify_tier(199_999) == "safe"

    def test_safe_at_200k(self):
        assert classify_tier(200_000) == "safe"

    def test_large_warn_at_200k_plus_1(self):
        assert classify_tier(200_001) == "large_warn"

    def test_large_warn_at_500k(self):
        assert classify_tier(500_000) == "large_warn"

    def test_large_skip_above_500k(self):
        assert classify_tier(500_001) == "large_skip"


class TestMakeSlug:
    def test_basic(self):
        assert make_slug("Video - Part 1.txt") == "video-part-1"

    def test_parentheses_stripped(self):
        assert make_slug("Video - Part 1 (copy).txt") == "video-part-1-copy"

    def test_long_slug_truncated(self):
        long_name = "a" * 100 + ".txt"
        slug = make_slug(long_name)
        assert len(slug) <= 60

    def test_unicode_falls_back_to_untitled(self):
        assert make_slug("日本語タイトル.txt") == "untitled"

    def test_mixed_unicode_preserves_ascii_parts(self):
        # "Café Tutorial.txt" -> NFKD: "e" preserved, accent stripped -> "cafe-tutorial"
        assert make_slug("Café Tutorial.txt") == "cafe-tutorial"

    def test_underscores_converted(self):
        assert make_slug("my_video_file.txt") == "my-video-file"


class TestBuildManifest:
    def _make_tmp_file(self, name: str, content: str = "test") -> Path:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=name)
        f.write(content.encode())
        f.close()
        return Path(f.name)

    def test_manifest_with_one_safe_file(self, tmp_path):
        log_file = tmp_path / "log.md"
        manifest_out = tmp_path / "manifest.json"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        f1 = self._make_tmp_file("test1.txt", "hello")
        f1.rename(src_dir / "test1.txt")

        counts = build_manifest(
            src_dir=src_dir,
            ext=".txt",
            log_file=log_file,
            manifest_path=manifest_out,
        )

        assert counts["total"] == 1
        assert counts["safe"] == 1
        assert counts["pending"] == 1

        manifest = json.loads(manifest_out.read_text())
        assert manifest[0]["status"] == "pending"
        assert manifest[0]["tier"] == "safe"
        assert "hash" in manifest[0]

    def test_manifest_skips_already_logged_hash(self, tmp_path):
        log_file = tmp_path / "log.md"
        manifest_out = tmp_path / "manifest.json"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        f1 = self._make_tmp_file("test1.txt", "hello world")
        f1.rename(src_dir / "test1.txt")
        h = hashlib.sha256((src_dir / "test1.txt").read_bytes()).hexdigest()
        log_file.write_text(f"SHA256:{h}\n")

        counts = build_manifest(
            src_dir=src_dir,
            ext=".txt",
            log_file=log_file,
            manifest_path=manifest_out,
        )

        assert counts["skipped"] == 1
        assert counts["pending"] == 0

    def test_resume_skips_done_entries(self, tmp_path):
        log_file = tmp_path / "log.md"
        manifest_out = tmp_path / "manifest.json"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        f1 = self._make_tmp_file("test1.txt", "hello")
        f1.rename(src_dir / "test1.txt")

        # First run
        build_manifest(src_dir=src_dir, ext=".txt", log_file=log_file, manifest_path=manifest_out)
        # Simulate subagent marking it done
        manifest = json.loads(manifest_out.read_text())
        manifest[0]["status"] = "done"
        manifest_out.write_text(json.dumps(manifest))

        # Second run with --resume
        counts = build_manifest(
            src_dir=src_dir,
            ext=".txt",
            log_file=log_file,
            manifest_path=manifest_out,
            resume=True,
        )

        assert counts["skipped"] == 1
        assert counts["pending"] == 0
