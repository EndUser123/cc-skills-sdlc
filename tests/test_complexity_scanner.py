"""Tests for complexity_scanner."""

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
