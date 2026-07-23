"""Tests for the shared settle-poll helper.

``poll_settle`` is the answer to a bug class that showed up three times in this
codebase: a ``QTimer.singleShot(0, …)`` retry chain only drains Qt's queued
layout, so its whole budget elapses in a few event-loop turns and it always
gives up before anything slower (a window landing on another monitor, a
splitter settling) has finished — locking in whatever intermediate size it
last measured.

Driven with ``interval_ms=0`` so the timers fire on ``processEvents`` without
the tests waiting real wall-clock time; the re-arm logic is identical.
"""
from __future__ import annotations

from Imervue.gui.settle_poll import DEFAULT_INTERVAL_MS, poll_settle


def _drain(qapp, passes: int = 20) -> None:
    for _ in range(passes):
        qapp.processEvents()


def test_runs_exactly_the_requested_number_of_passes(qapp):
    calls: list[int] = []
    poll_settle(lambda: calls.append(1), lambda: True, retries=4, interval_ms=0)
    _drain(qapp)
    assert len(calls) == 4


def test_first_pass_is_deferred_not_immediate(qapp):
    calls: list[int] = []
    poll_settle(lambda: calls.append(1), lambda: True, retries=3, interval_ms=0)
    assert calls == []


def test_keeps_going_while_nothing_appears_to_change(qapp):
    # The whole point: unlike a "re-arm only if the measurement moved" chain,
    # this must not stop early — the change is still in flight.
    seen: list[int] = []
    poll_settle(lambda: seen.append(len(seen)), lambda: True,
                retries=5, interval_ms=0)
    _drain(qapp)
    assert seen == [0, 1, 2, 3, 4]


def test_stops_as_soon_as_it_is_superseded(qapp):
    calls: list[int] = []
    current = {"ok": True}

    def _step() -> None:
        calls.append(1)
        current["ok"] = False       # a newer trigger takes over

    poll_settle(_step, lambda: current["ok"], retries=6, interval_ms=0)
    _drain(qapp)
    assert len(calls) == 1


def test_superseded_before_the_first_pass_never_runs_step(qapp):
    calls: list[int] = []
    poll_settle(lambda: calls.append(1), lambda: False, retries=4, interval_ms=0)
    _drain(qapp)
    assert calls == []


def test_zero_retries_schedules_nothing(qapp):
    calls: list[int] = []
    poll_settle(lambda: calls.append(1), lambda: True, retries=0, interval_ms=0)
    _drain(qapp)
    assert calls == []


def test_negative_retries_schedules_nothing(qapp):
    calls: list[int] = []
    poll_settle(lambda: calls.append(1), lambda: True, retries=-3, interval_ms=0)
    _drain(qapp)
    assert calls == []


def test_single_retry_runs_once(qapp):
    calls: list[int] = []
    poll_settle(lambda: calls.append(1), lambda: True, retries=1, interval_ms=0)
    _drain(qapp)
    assert len(calls) == 1


def test_default_interval_is_a_real_delay():
    # A zero default would silently reintroduce the singleShot(0) bug this
    # helper exists to fix.
    assert DEFAULT_INTERVAL_MS > 0
