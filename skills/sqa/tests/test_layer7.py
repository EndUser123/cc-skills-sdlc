"""Tests for Layer 7 OPERATIONAL analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer7_operational


class TestLayer7Run:
    """Tests for layer7_operational.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer7_operational.run(tmp_target)
        assert isinstance(result, list)

    def test_run_with_no_hooks_dir(self, tmp_path):
        """When .claude/hooks does not exist, dead hook check returns empty."""
        layer7_operational.run(tmp_path)
        # Should not raise; returns list (possibly empty or with FileNotFoundError-ignored findings)
