"""Tests for complexity_scanner."""

import subprocess
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "refactor"))

from scripts.complexity_scanner import scan_complexity, _cc_to_risk


class TestCcToRisk:
    def test_low_cc(self) -> None:
        assert _cc_to_risk(1) == (1, "low", "low")
        assert _cc_to_risk(5) == (1, "low", "low")

    def test_medium_cc(self) -> None:
        assert _cc_to_risk(6) == (2, "medium", "medium")
        assert _cc_to_risk(10) == (2, "medium", "medium")

    def test_high_cc(self) -> None:
        assert _cc_to_risk(11) == (3, "medium", "medium")
        assert _cc_to_risk(20) == (3, "medium", "medium")

    def test_very_high_cc(self) -> None:
        assert _cc_to_risk(21) == (4, "high", "high")
        assert _cc_to_risk(100) == (4, "high", "high")


class TestScanComplexity:
    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        results = scan_complexity([f], min_cc=1)
        assert results == []

    def test_single_low_cc_function(self, tmp_path: Path) -> None:
        f = tmp_path / "simple.py"
        f.write_text("def foo():\n    return 1\n", encoding="utf-8")
        results = scan_complexity([f], min_cc=5)
        assert len(results) == 0

    def test_high_cc_function_found(self, tmp_path: Path) -> None:
        src = (
            "def complex(x):\n"
            "    if x > 0:\n"
            "        if x > 10:\n"
            "            if x > 20:\n"
            "                while True:\n"
            "                    pass\n"
            "    return x\n"
        )
        f = tmp_path / "complex.py"
        f.write_text(src, encoding="utf-8")
        results = scan_complexity([f], min_cc=3)
        assert len(results) == 1
        assert results[0]["type"] == "HIGH_CC"
        assert results[0]["complexity"] >= 3
        assert "complex" in results[0]["description"]

    def test_method_high_cc(self, tmp_path: Path) -> None:
        src = (
            "class C:\n"
            "    def method(self, x):\n"
            "        if x > 0:\n"
            "            if x > 10:\n"
            "                return x\n"
            "        return 0\n"
        )
        f = tmp_path / "method.py"
        f.write_text(src, encoding="utf-8")
        results = scan_complexity([f], min_cc=3)
        assert len(results) == 1
        assert "method" in results[0]["description"]
        assert "class C" in results[0]["description"]

    def test_skips_non_python_files(self, tmp_path: Path) -> None:
        f = tmp_path / "data.txt"
        f.write_text("def foo():\n    pass\n", encoding="utf-8")
        results = scan_complexity([f], min_cc=1)
        assert results == []

    def test_skips_nonexistent_file(self) -> None:
        results = scan_complexity(["nonexistent.py"], min_cc=1)
        assert results == []

class TestRankHotspots:
    @staticmethod
    def _init_repo(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        for a in (["git", "init", "-q"],
                  ["git", "config", "user.email", "t@t"],
                  ["git", "config", "user.name", "t"]):
            subprocess.run(a, cwd=path, check=True)

    def test_rank_hotspots_surfaces_churn_and_complexity(self, tmp_path: Path) -> None:
        from scripts.complexity_scanner import rank_hotspots

        self._init_repo(tmp_path)
        hot = tmp_path / "hot.py"
        hot.write_text(
            "def f(x):\n if x:\n  if x+1:\n   if x+2:\n    return 1\n return 0\n",
            encoding="utf-8",
        )
        for i in range(3):  # plant churn: 3 commits touching hot.py
            hot.write_text(hot.read_text(encoding="utf-8") + f"\n# edit {i}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
            subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", f"c{i}"], check=True)
        cold = tmp_path / "cold.py"
        cold.write_text("def g():\n return 1\n", encoding="utf-8")  # low CC
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "cold"], check=True)

        rows = rank_hotspots([hot, cold], since_days=90, min_cc=3, min_churn=1, top_n=10)
        files = {r["file_path"] for r in rows}
        assert str(hot) in files
        assert str(cold) not in files  # low CC -> filtered
        hot_row = next(r for r in rows if r["file_path"] == str(hot))
        assert hot_row["churn"] >= 3
        assert hot_row["max_cc"] >= 3
        assert hot_row["hotspot_score"] == hot_row["complexity_rank"] * hot_row["churn_rank"]

    def test_rank_hotspots_filtered_by_min_churn(self, tmp_path: Path) -> None:
        from scripts.complexity_scanner import rank_hotspots

        self._init_repo(tmp_path)
        f = tmp_path / "f.py"
        f.write_text("def f(x):\n if x:\n  if x+1:\n   return 1\n return 0\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "i"], check=True)
        # require 5 churn -> single commit filtered out -> empty
        assert rank_hotspots([f], since_days=90, min_churn=5) == []

    def test_is_vendored(self) -> None:
        from scripts.complexity_scanner import _is_vendored

        assert _is_vendored(Path("a/site-packages/x.py"))
        assert _is_vendored(Path("proj/node_modules/y.py"))
        assert not _is_vendored(Path("a/src/x.py"))
