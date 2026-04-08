#!/usr/bin/env python3
"""Pytest configuration and fixtures for TDD tests."""

import time
from datetime import datetime, timedelta, timezone

import pytest

try:
    from freezegun import freeze_time

    FREEZEGUN_AVAILABLE = True
except ImportError:
    FREEZEGUN_AVAILABLE = False
    freeze_time = None


@pytest.fixture
def mock_time():
    """
    Fixture that mocks time-related functions for deterministic testing.

    Uses freezegun if available, otherwise falls back to basic mocking.
    This fixture freezes time and allows time travel for testing TOCTOU scenarios
    without real delays.

    Usage:
        def test_with_mock_time(mock_time):
            mock_time.move_to("2026-03-15 12:00:00")
            assert time.time() returns frozen timestamp

    Yields:
        TimeController object with methods:
        - move_to(datetime_or_str): Move time to specific point
        - tick(delta): Advance time by timedelta
        - rewind(delta): Move time backward by timedelta
    """
    if not FREEZEGUN_AVAILABLE:
        pytest.skip("freezegun not installed - pip install freezegun")

    class TimeController:
        """Controller for frozen time during tests."""

        def __init__(self):
            self._freezer = None

        def move_to(self, target):
            """Move time to specific datetime."""
            if isinstance(target, str):
                target = datetime.fromisoformat(target)
            self._freezer = freeze_time(target)
            self._freezer.start()

        def tick(self, delta=None, **kwargs):
            """Advance time by timedelta."""
            if delta is None:
                delta = timedelta(**kwargs)
            if self._freezer:
                self._freezer.tick(delta=delta)

        def rewind(self, delta=None, **kwargs):
            """Move time backward by timedelta."""
            if delta is None:
                delta = timedelta(**kwargs)
            if self._freezer:
                self._freezer.tick(delta=-delta)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            if self._freezer:
                self._freezer.stop()

    controller = TimeController()
    controller.move_to(datetime.now(timezone.utc))  # Start at current time
    yield controller


@pytest.fixture
def frozen_time():
    """
    Fixture that freezes time at the current moment for test isolation.

    Simpler version of mock_time that just freezes time without time travel capabilities.
    Use this when tests don't need to manipulate time, just prevent it from advancing.

    Usage:
        def test_with_frozen_time(frozen_time):
            time.sleep(1000)  # Returns instantly, no real delay
            assert time.time() == frozen_timestamp
    """
    if not FREEZEGUN_AVAILABLE:
        pytest.skip("freezegun not installed - pip install freezegun")

    with freeze_time(datetime.now(timezone.utc)) as freezer:
        yield freezer


@pytest.fixture(autouse=True)
def fast_time():
    """
    Auto-applied fixture that replaces time.sleep() with instant mock.

    This fixture automatically applies to all tests in the suite,
    making tests that use time.sleep() execute instantly without real delays.

    Critical for TOCTOU (Time-OfCheck-TimeOfUse) tests that verify
    file state changes without waiting for actual timeouts.

    Acceptance criteria: Test suite completes in <10 seconds
    """
    if not FREEZEGUN_AVAILABLE:
        pytest.skip("freezegun not installed - pip install freezegun")

    with freeze_time(datetime.now(timezone.utc)) as freezer:
        # Replace time.sleep with mock that does nothing
        original_sleep = time.sleep

        def mock_sleep(seconds):
            """Mock sleep that returns instantly."""
            pass

        time.sleep = mock_sleep
        yield
        time.sleep = original_sleep


@pytest.fixture
def fast_datetime():
    """
    Fixture that provides fast datetime.now() calls using frozen time.

    For tests that need datetime operations without real time passing.
    Automatically syncs with frozen_time fixture.
    """
    if not FREEZEGUN_AVAILABLE:
        pytest.skip("freezegun not installed - pip install freezegun")

    with freeze_time(datetime.now(timezone.utc)) as freezer:
        yield freezer
