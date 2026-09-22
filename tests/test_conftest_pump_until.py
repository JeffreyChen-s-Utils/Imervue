"""Tests for the shared ``pump_until`` fixture in ``tests/conftest.py``.

Tests wait on queued Qt signals with it instead of a fixed number of
``processEvents()`` passes, so its timeout behaviour has to be right.
"""
from __future__ import annotations

import time


def test_returns_true_as_soon_as_the_predicate_holds(pump_until):
    started = time.monotonic()
    assert pump_until(lambda: True) is True
    assert time.monotonic() - started < 1.0


def test_returns_false_after_the_timeout(pump_until):
    started = time.monotonic()
    assert pump_until(lambda: False, timeout=0.05) is False
    assert time.monotonic() - started >= 0.05


def test_pumps_until_a_later_state_change(pump_until):
    state = {"ready": False}
    deadline = time.monotonic() + 0.05

    def _ready():
        if time.monotonic() >= deadline:
            state["ready"] = True
        return state["ready"]

    assert pump_until(_ready, timeout=5.0) is True


def test_processes_queued_qt_events(qapp, pump_until):
    from PySide6.QtCore import QTimer
    fired: list[int] = []
    QTimer.singleShot(10, lambda: fired.append(1))
    assert pump_until(lambda: bool(fired))
