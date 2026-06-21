#!/usr/bin/env python3
"""Tests for mutation_config.py - config loading and module selection."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add shared skill lib to path
SKILL_DIR = Path(__file__).resolve().parents[1]  # skills/go/tests -> skills/go
SHARED_LIB = SKILL_DIR.parent / "__lib"
if str(SHARED_LIB) not in sys.path:
    sys.path.insert(0, str(SHARED_LIB))

from mutation_config import load_quality_gates, ModuleGate, QualityGatesError, QualityGates
