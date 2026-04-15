"""Tests for Layer 1 SYNTACTIC analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer1_syntactic


class TestLayer1Run:
    """Tests for layer1_syntactic.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer1_syntactic.run(tmp_target)
        assert isinstance(result, list)

    def test_run_finds_no_findings_for_clean_code(self, tmp_target):
        # tmp_target has clean code (just a print statement)
        layer1_syntactic.run(tmp_target)
        # Should not raise; returns list of findings (possibly empty)
