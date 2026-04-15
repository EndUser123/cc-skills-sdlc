"""Tests for Layer 3 STRUCTURAL analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer3_structural


class TestLayer3Run:
    """Tests for layer3_structural.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer3_structural.run(tmp_target)
        assert isinstance(result, list)
