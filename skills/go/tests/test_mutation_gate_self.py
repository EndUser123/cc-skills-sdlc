#!/usr/bin/env python3
"""Self-tests for mutation-gate.py - config loading, module selection, classification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add shared skill lib to path
SKILL_DIR = Path(__file__).resolve().parents[1]  # skills/go/tests -> skills/go
SHARED_LIB = SKILL_DIR.parent / "__lib"
T_MODES = SKILL_DIR.parent / "t" / "modes"
for path in (SHARED_LIB, T_MODES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mutation_config import load_quality_gates, QualityGatesError
from mutation_mode import run_mutation_for_module, MutationResult
