#!/usr/bin/env python3
"""Run pytest tests directly."""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

if __name__ == "__main__":
    # Run pytest
    exit_code = pytest.main([
        str(Path(__file__).parent / "test_hook_checklist.py"),
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure
    ])

    sys.exit(exit_code)
