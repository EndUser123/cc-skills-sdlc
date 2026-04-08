#!/usr/bin/env python3
"""Pytest configuration for /code skill tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to Python path for module imports
sys.path.insert(0, str(Path(__file__).parent))

# Set up mock MCP modules for Context7 tools
# These modules have hyphens in their names which isn't valid Python,
# so we register them in sys.modules for testing purposes
def _setup_context7_mocks():
    """Set up mock Context7 MCP modules in sys.modules for testing."""
    # Create mock modules
    resolve_module = MagicMock()
    query_module = MagicMock()

    # Register in sys.modules
    sys.modules["mcp__plugin_context7_context7__resolve-library-id"] = resolve_module
    sys.modules["mcp__plugin_context7_context7__query-docs"] = query_module

# Setup mocks when conftest is loaded
_setup_context7_mocks()
