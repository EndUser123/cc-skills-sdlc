"""Tests for Layer 2 SEMANTIC analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer2_semantic


class TestLayer2Run:
    """Tests for layer2_semantic.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer2_semantic.run(tmp_target)
        assert isinstance(result, list)

    def test_run_on_clean_target(self, tmp_target):
        layer2_semantic.run(tmp_target)
        # Should not raise; returns list (possibly empty or with test-skip finding)
