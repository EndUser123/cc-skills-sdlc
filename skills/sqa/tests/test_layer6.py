"""Tests for Layer 6 PERFORMANCE analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from layers import layer6_performance


class TestHasNestedExecutor:
    """Tests for _has_nested_executor detection logic."""

    def test_nested_executor_detected(self):
        code = """
from concurrent.futures import ThreadPoolExecutor

def outer():
    with ThreadPoolExecutor() as executor:
        def inner():
            with ThreadPoolExecutor() as inner_executor:
                pass
"""
        assert layer6_performance._has_nested_executor(code) is True

    def test_single_executor_not_flagged(self):
        code = """
from concurrent.futures import ThreadPoolExecutor

def outer():
    with ThreadPoolExecutor() as executor:
        result = executor.submit(do_work)
"""
        assert layer6_performance._has_nested_executor(code) is False

    def test_no_executor(self):
        code = "def foo(): return 1"
        assert layer6_performance._has_nested_executor(code) is False


class TestHasThreadCpuMismatch:
    """Tests for _has_thread_cpu_mismatch detection logic."""

    def test_thread_without_affinity(self):
        code = "import threading; t = threading.Thread(target=foo)"
        assert layer6_performance._has_thread_cpu_mismatch(code) is True

    def test_thread_with_affinity_not_flagged(self):
        code = "import threading; t = threading.Thread(target=foo); t.start(); import cpu_affinity"
        assert layer6_performance._has_thread_cpu_mismatch(code) is False

    def test_executor_without_affinity(self):
        code = "from concurrent.futures import ThreadPoolExecutor; e = ThreadPoolExecutor()"
        assert layer6_performance._has_thread_cpu_mismatch(code) is True

    def test_no_threading_at_all(self):
        code = "x = 1"
        assert layer6_performance._has_thread_cpu_mismatch(code) is False


class TestLayer6Run:
    """Tests for layer6_performance.run()."""

    def test_run_returns_list(self, tmp_target):
        result = layer6_performance.run(tmp_target)
        assert isinstance(result, list)
