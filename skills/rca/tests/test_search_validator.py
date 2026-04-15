#!/usr/bin/env python3
"""
Test scenarios for PostToolUse_rca_search_validator.py hook.

Run: python -m pytest tests/test_search_validator.py -v
"""

import sys
from pathlib import Path

# Add hooks directory to path for imports
hooks_dir = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(hooks_dir))

from PostToolUse_rca_search_validator import (
    MECHANISM_ONLY_THRESHOLD,
    classify_search_pattern,
    should_warn_user,
)


def test_classify_mechanism_searches():
    """Test that mechanism searches are correctly classified."""
    mechanism_patterns = [
        "Progress(",
        "class MyProgress",
        "def update_progress",
        "update(",
        "render_frame",
    ]

    for pattern in mechanism_patterns:
        result = classify_search_pattern(pattern)
        assert (
            result == "mechanism"
        ), f"Pattern '{pattern}' classified as {result}, expected 'mechanism'"
        print(f"✓ '{pattern}' → mechanism")


def test_classify_functional_searches():
    """Test that functional searches are correctly classified."""
    functional_patterns = [
        "yt-api:",
        "status: complete",
        'console.log("progress")',
        "error: failed",
        "Exception occurred",
        "54%",
    ]

    for pattern in functional_patterns:
        result = classify_search_pattern(pattern)
        assert (
            result == "functional"
        ), f"Pattern '{pattern}' classified as {result}, expected 'functional'"
        print(f"✓ '{pattern}' → functional")


def test_classify_temporal_searches():
    """Test that temporal searches are correctly classified."""
    temporal_patterns = [
        "git log --oneline",
        "git diff HEAD~1",
        "changed files",
        "recent commits",
    ]

    for pattern in temporal_patterns:
        result = classify_search_pattern(pattern)
        assert (
            result == "temporal"
        ), f"Pattern '{pattern}' classified as {result}, expected 'temporal'"
        print(f"✓ '{pattern}' → temporal")


def test_mechanism_only_triggers_warning():
    """Test that 3+ mechanism searches without functional triggers warning."""
    state = {
        "searches": [
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "class Progress", "type": "mechanism", "timestamp": "2026-02-28T10:01:00"},
            {"pattern": "def update", "type": "mechanism", "timestamp": "2026-02-28T10:02:00"},
        ]
    }

    should_warn, warning = should_warn_user(state)

    assert should_warn, "Expected warning for 3 mechanism-only searches"
    assert "MECHANISM-ONLY SEARCH DETECTED" in warning
    assert "grep(" in warning  # Suggestion included
    assert "3 times" in warning
    print("✓ Mechanism-only detection works")
    print(f"  Warning preview: {warning[:200]}...")


def test_mixed_searches_no_warning():
    """Test that mixed searches don't trigger warning."""
    state = {
        "searches": [
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "yt-api:", "type": "functional", "timestamp": "2026-02-28T10:01:00"},
            {"pattern": "class Progress", "type": "mechanism", "timestamp": "2026-02-28T10:02:00"},
        ]
    }

    should_warn, warning = should_warn_user(state)

    assert not should_warn, "Should NOT warn when functional search present"
    print("✓ Mixed searches don't trigger warning")


def test_insufficient_searches_no_warning():
    """Test that <3 searches don't trigger warning even if all mechanism."""
    state = {
        "searches": [
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "class Progress", "type": "mechanism", "timestamp": "2026-02-28T10:01:00"},
        ]
    }

    should_warn, warning = should_warn_user(state)

    assert not should_warn, f"Should NOT warn with only {len(state['searches'])} searches"
    print(f"✓ Fewer than {MECHANISM_ONLY_THRESHOLD} searches don't trigger warning")


def test_functional_first_no_warning():
    """Test that functional search first prevents false positive."""
    state = {
        "searches": [
            {"pattern": "yt-api:", "type": "functional", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:01:00"},
            {"pattern": "class Progress", "type": "mechanism", "timestamp": "2026-02-28T10:02:00"},
            {"pattern": "def update", "type": "mechanism", "timestamp": "2026-02-28T10:03:00"},
        ]
    }

    should_warn, warning = should_warn_user(state)

    assert not should_warn, "Should NOT warn when functional search done first"
    print("✓ Functional search first prevents false positive")


def test_context_aware_suggestions():
    """Test that suggestions adapt to search context."""
    # Test with Progress context
    state_progress = {
        "searches": [
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "update(", "type": "mechanism", "timestamp": "2026-02-28T10:01:00"},
            {"pattern": "render(", "type": "mechanism", "timestamp": "2026-02-28T10:02:00"},
        ]
    }

    should_warn, warning = should_warn_user(state_progress)
    assert should_warn
    assert "yt-api:" in warning  # Progress context suggests yt-api search
    print("✓ Context-aware suggestion: Progress → yt-api:")

    # Test with class/def context
    state_class = {
        "searches": [
            {"pattern": "class Progress", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "def update", "type": "mechanism", "timestamp": "2026-02-28T10:01:00"},
            {"pattern": "def render", "type": "mechanism", "timestamp": "2026-02-28T10:02:00"},
        ]
    }

    should_warn, warning = should_warn_user(state_class)
    assert should_warn
    assert "error:" in warning  # Class/def context suggests error search
    print("✓ Context-aware suggestion: class/def → error:")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing PostToolUse_rca_search_validator.py")
    print("=" * 60)

    test_classify_mechanism_searches()
    test_classify_functional_searches()
    test_classify_temporal_searches()
    test_mechanism_only_triggers_warning()
    test_mixed_searches_no_warning()
    test_insufficient_searches_no_warning()
    test_functional_first_no_warning()
    test_context_aware_suggestions()

    print("=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
