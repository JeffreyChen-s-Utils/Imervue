"""Tests for the sub-frame signal coalescer.

The coalescer needs Qt's event loop to deliver the timer callback,
so all tests pump ``qapp.processEvents`` after ``schedule()`` to
let the singleShot fire.
"""
from __future__ import annotations

import time

from Imervue.gpu_image_view.signal_coalescer import (
    DEFAULT_INTERVAL_MS,
    SignalCoalescer,
)


def _wait(qapp, predicate, timeout_s: float = 1.0) -> bool:
    """Pump the Qt event loop until ``predicate`` is true or the
    timeout elapses. The coalescer fires via QTimer.singleShot which
    only delivers when the loop is processed."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    qapp.processEvents()
    return predicate()


def test_starts_not_pending(qapp):
    c = SignalCoalescer()
    try:
        assert c.is_pending() is False
    finally:
        c.deleteLater()


def test_first_schedule_arms_pending(qapp):
    c = SignalCoalescer(interval_ms=100)
    try:
        c.schedule()
        assert c.is_pending() is True
    finally:
        c.deleteLater()


def test_n_schedule_calls_produce_one_emit(qapp):
    """The whole point: bursts of schedule() within one window
    collapse into a single flush_requested signal."""
    fired: list[int] = []
    c = SignalCoalescer(interval_ms=10)
    c.flush_requested.connect(lambda: fired.append(1))
    try:
        for _ in range(100):
            c.schedule()
        assert _wait(qapp, lambda: bool(fired))
        assert fired == [1]
    finally:
        c.deleteLater()


def test_after_flush_can_schedule_again(qapp):
    """The coalescer must reset its pending state after each flush
    so the next burst gets its own emit."""
    fired: list[int] = []
    c = SignalCoalescer(interval_ms=5)
    c.flush_requested.connect(lambda: fired.append(1))
    try:
        c.schedule()
        assert _wait(qapp, lambda: len(fired) >= 1)
        assert c.is_pending() is False
        c.schedule()
        assert _wait(qapp, lambda: len(fired) >= 2)
        assert fired == [1, 1]
    finally:
        c.deleteLater()


def test_force_flush_runs_immediately(qapp):
    """End-of-burst case: caller knows the last item arrived
    and wants the user to see the final state without waiting
    for the timer window."""
    fired: list[int] = []
    c = SignalCoalescer(interval_ms=10_000)   # huge window
    c.flush_requested.connect(lambda: fired.append(1))
    try:
        c.schedule()
        c.force_flush()
        assert fired == [1]
        assert c.is_pending() is False
    finally:
        c.deleteLater()


def test_force_flush_when_not_pending_is_noop(qapp):
    """Force-flushing without a pending schedule mustn't emit
    duplicate signals — that would re-do the expensive GUI
    update for no reason."""
    fired: list[int] = []
    c = SignalCoalescer()
    c.flush_requested.connect(lambda: fired.append(1))
    try:
        c.force_flush()
        assert fired == []
    finally:
        c.deleteLater()


def test_timer_after_force_flush_does_not_double_emit(qapp):
    """force_flush clears pending; when the queued QTimer fires
    later, it must observe the cleared state and skip emitting.
    Catches a race where both paths produce a signal."""
    fired: list[int] = []
    c = SignalCoalescer(interval_ms=5)
    c.flush_requested.connect(lambda: fired.append(1))
    try:
        c.schedule()
        c.force_flush()
        assert fired == [1]
        # Wait long enough for the queued timer to fire.
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)
        assert fired == [1]   # still one — no duplicate from the late timer
    finally:
        c.deleteLater()


def test_interval_zero_clamps_to_minimum(qapp):
    """An interval of 0 would mean 'fire immediately', losing the
    coalescing benefit. Clamp to 1 ms so the contract holds
    (bursts still collapse to one emit per loop iteration)."""
    c = SignalCoalescer(interval_ms=0)
    try:
        assert c._interval_ms == 1   # noqa: SLF001
    finally:
        c.deleteLater()


def test_negative_interval_clamps_to_minimum(qapp):
    c = SignalCoalescer(interval_ms=-50)
    try:
        assert c._interval_ms == 1   # noqa: SLF001
    finally:
        c.deleteLater()


def test_default_interval_matches_constant(qapp):
    """Sanity guard: the documented default and the module constant
    must agree."""
    c = SignalCoalescer()
    try:
        assert c._interval_ms == DEFAULT_INTERVAL_MS   # noqa: SLF001
    finally:
        c.deleteLater()
